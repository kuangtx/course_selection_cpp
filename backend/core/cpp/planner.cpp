#include "planner.hpp"

#include <algorithm>
#include <cmath>
#include <functional>
#include <limits>
#include <stdexcept>
#include <tuple>
#include <unordered_map>

namespace course_selection {
namespace {

using Mask = std::vector<std::uint64_t>;

bool overlaps(const Mask& a, const Mask& b) {
    const auto count = std::min(a.size(), b.size());
    for (std::size_t i = 0; i < count; ++i) {
        if ((a[i] & b[i]) != 0) return true;
    }
    return false;
}

Mask merged(const Mask& a, const Mask& b) {
    Mask result(std::max(a.size(), b.size()), 0);
    for (std::size_t i = 0; i < a.size(); ++i) result[i] |= a[i];
    for (std::size_t i = 0; i < b.size(); ++i) result[i] |= b[i];
    return result;
}

int count_bits(std::uint64_t value) {
#if defined(__GNUC__) || defined(__clang__)
    return __builtin_popcountll(value);
#else
    int count = 0;
    while (value) {
        value &= value - 1;
        ++count;
    }
    return count;
#endif
}

std::vector<std::string> sorted_ids(const std::vector<std::string>& ids) {
    auto result = ids;
    std::sort(result.begin(), result.end());
    return result;
}

struct RankKey {
    std::size_t missing_required;
    double optional_gap;
    double negative_preference;
    std::vector<std::string> sorted_sections;
};

RankKey rank_key(const Plan& plan) {
    return {plan.unmet_required_course_ids.size(), plan.optional.gap,
            -plan.preference_score.total, sorted_ids(plan.section_ids)};
}

bool rank_less(const Plan& a, const Plan& b) {
    const auto ka = rank_key(a);
    const auto kb = rank_key(b);
    if (ka.missing_required != kb.missing_required) return ka.missing_required < kb.missing_required;
    if (ka.optional_gap != kb.optional_gap) return ka.optional_gap < kb.optional_gap;
    if (ka.negative_preference != kb.negative_preference) return ka.negative_preference < kb.negative_preference;
    return ka.sorted_sections < kb.sorted_sections;
}

}  // namespace

SearchResult plan_courses(
    const Student& student,
    const std::map<std::string, Course>& courses,
    const std::map<std::string, Section>& sections,
    const Calendar& calendar,
    const Scoring& scoring,
    const SearchOptions& options) {
    if (options.candidate_limit == 0 || options.max_search_nodes == 0)
        throw std::invalid_argument("candidate_limit and max_search_nodes must be non-zero");
    if (calendar.total_weeks < 1 || calendar.days_per_week < 1 || calendar.periods_per_day < 1)
        throw std::invalid_argument("calendar values must be positive");
    if (student.optional_mode != "count" && student.optional_mode != "credits")
        throw std::invalid_argument("optional_mode must be 'count' or 'credits'");
    if (!std::isfinite(student.optional_target) || student.optional_target < 0)
        throw std::invalid_argument("optional_target must be finite and non-negative");
    if (!std::isfinite(scoring.course_weight) || !std::isfinite(scoring.time_weight) ||
        scoring.course_weight + scoring.time_weight <= 0)
        throw std::invalid_argument("scoring weights must be finite and have a positive sum");

    std::set<std::string> required(student.required_course_ids.begin(), student.required_course_ids.end());
    std::set<std::string> optional(student.optional_course_ids.begin(), student.optional_course_ids.end());
    if (required.size() != student.required_course_ids.size() || optional.size() != student.optional_course_ids.size())
        throw std::invalid_argument("course ID lists must not contain duplicates");
    for (const auto& id : required) if (optional.count(id))
        throw std::invalid_argument("required and optional courses must not overlap");
    for (const auto& id : required) if (!courses.count(id))
        throw std::invalid_argument("unknown required course: " + id);
    for (const auto& id : optional) if (!courses.count(id))
        throw std::invalid_argument("unknown optional course: " + id);

    const std::set<std::string> needed = [&] {
        auto result = required;
        result.insert(optional.begin(), optional.end());
        return result;
    }();
    for (const auto& id : options.excluded_section_ids)
        if (!sections.count(id)) throw std::invalid_argument("unknown excluded section: " + id);
    if (options.use_allowed_whitelist) for (const auto& id : options.allowed_section_ids)
        if (!sections.count(id)) throw std::invalid_argument("unknown allowed section: " + id);

    std::vector<std::string> selected = options.fixed_section_ids;
    std::set<std::string> fixed_courses;
    Mask taken;
    double optional_achieved = 0.0;
    for (const auto& id : options.fixed_section_ids) {
        const auto it = sections.find(id);
        if (it == sections.end()) throw std::invalid_argument("unknown fixed section: " + id);
        const auto& section = it->second;
        if (!needed.count(section.course_id)) throw std::invalid_argument("fixed section is outside requirements: " + id);
        if (options.excluded_section_ids.count(id)) throw std::invalid_argument("fixed section is excluded: " + id);
        if (!fixed_courses.insert(section.course_id).second) throw std::invalid_argument("duplicate fixed course: " + section.course_id);
        if (overlaps(taken, section.time_mask)) throw std::invalid_argument("fixed sections have a time conflict: " + id);
        taken = merged(taken, section.time_mask);
        if (optional.count(section.course_id))
            optional_achieved += student.optional_mode == "count" ? 1.0 : courses.at(section.course_id).credits;
    }

    std::vector<std::string> remaining_required, remaining_optional;
    for (const auto& id : student.required_course_ids) if (!fixed_courses.count(id)) remaining_required.push_back(id);
    for (const auto& id : student.optional_course_ids) if (!fixed_courses.count(id)) remaining_optional.push_back(id);

    std::map<std::string, std::vector<std::string>> sections_by_course;
    for (const auto& course_id : needed) {
        if (fixed_courses.count(course_id)) continue;
        auto& matches = sections_by_course[course_id];
        for (const auto& pair : sections) {
            const auto& id = pair.first;
            const auto& section = pair.second;
            if (section.course_id != course_id || options.excluded_section_ids.count(id)) continue;
            if (options.use_allowed_whitelist && !options.allowed_section_ids.count(id)) continue;
            matches.push_back(id);
        }
        // std::map iteration is already lexicographic, matching Python sorting.
    }

    Mask early_mask;
    for (int day = 0; day < calendar.total_weeks * calendar.days_per_week; ++day) {
        const auto slot = static_cast<std::size_t>(day) * calendar.periods_per_day;
        const auto word = slot / 64;
        if (early_mask.size() <= word) early_mask.resize(word + 1, 0);
        early_mask[word] |= (std::uint64_t{1} << (slot % 64));
    }

    const double total_weight = scoring.course_weight + scoring.time_weight;
    const double early_penalty = student.early_penalty_per_week;
    SearchResult result;
    std::vector<Plan> plans;
    bool limit_reached = false;

    auto enter_node = [&]() {
        if (options.max_search_nodes >= 0 && result.searched_nodes >= options.max_search_nodes) {
            limit_reached = true;
            return false;
        }
        ++result.searched_nodes;
        return true;
    };

    auto save_plan = [&]() {
        Plan plan;
        plan.section_ids = selected;
        plan.optional.mode = student.optional_mode;
        plan.optional.target = student.optional_target;
        std::set<std::string> selected_courses;
        for (const auto& sid : selected) selected_courses.insert(sections.at(sid).course_id);
        for (const auto& id : student.required_course_ids) if (!selected_courses.count(id))
            plan.unmet_required_course_ids.push_back(id);
        std::set<std::string> selected_optional;
        for (const auto& id : student.optional_course_ids) if (selected_courses.count(id)) selected_optional.insert(id);
        if (student.optional_mode == "count") {
            plan.optional.achieved = static_cast<double>(selected_optional.size());
        } else {
            for (const auto& id : selected_optional) plan.optional.achieved += courses.at(id).credits;
        }
        plan.optional.gap = std::max(0.0, plan.optional.target - plan.optional.achieved);
        plan.is_complete = plan.unmet_required_course_ids.empty() && plan.optional.gap == 0.0;

        double course_total = 0.0;
        for (const auto& id : selected_optional) {
            const auto pref = student.course_scores.find(id);
            course_total += pref == student.course_scores.end() ? scoring.default_course_score : pref->second;
        }
        if (!selected_optional.empty()) course_total /= selected_optional.size();
        Mask occupied;
        for (const auto& sid : selected) occupied = merged(occupied, sections.at(sid).time_mask);
        int early_count = 0;
        for (std::size_t i = 0; i < early_mask.size(); ++i) {
            const auto word = i < occupied.size() ? occupied[i] : 0;
            early_count += count_bits(word & early_mask[i]);
        }
        const double average_early = static_cast<double>(early_count) / calendar.total_weeks;
        const double time_score = std::max(0.0, 100.0 - average_early * early_penalty);
        plan.preference_score.course_preference = course_total;
        plan.preference_score.total_early_days = early_count;
        plan.preference_score.average_early_days_per_week = average_early;
        plan.preference_score.time_score = time_score;
        plan.preference_score.total = course_total * scoring.course_weight / total_weight +
                                      time_score * scoring.time_weight / total_weight;
        plans.push_back(std::move(plan));
        std::stable_sort(plans.begin(), plans.end(), rank_less);
        if (options.candidate_limit >= 0 && plans.size() > static_cast<std::size_t>(options.candidate_limit))
            plans.pop_back();
    };

    // Each branch owns its occupied mask; selection and credit counters are
    // pushed before recursion and restored afterward to keep sibling branches independent.
    std::function<void(std::size_t, const Mask&)> search_optional;
    std::function<void(std::size_t, const Mask&)> search_required;
    search_optional = [&](std::size_t index, const Mask& occupied) {
        if (!enter_node()) return;
        if (optional_achieved >= student.optional_target) { save_plan(); return; }
        if (index == remaining_optional.size()) {
            if (options.allow_partial) save_plan();
            return;
        }
        const auto& course_id = remaining_optional[index];
        const double increment = student.optional_mode == "count" ? 1.0 : courses.at(course_id).credits;
        for (const auto& sid : sections_by_course[course_id]) {
            const auto& mask = sections.at(sid).time_mask;
            if (overlaps(mask, occupied)) continue;
            selected.push_back(sid);
            optional_achieved += increment;
            search_optional(index + 1, merged(occupied, mask));
            optional_achieved -= increment;
            selected.pop_back();
            if (limit_reached) return;
        }
        // Skipping an optional course is always explored, even for full plans.
        search_optional(index + 1, occupied);
    };
    search_required = [&](std::size_t index, const Mask& occupied) {
        if (!enter_node()) return;
        if (index == remaining_required.size()) { search_optional(0, occupied); return; }
        const auto& course_id = remaining_required[index];
        for (const auto& sid : sections_by_course[course_id]) {
            const auto& mask = sections.at(sid).time_mask;
            if (overlaps(mask, occupied)) continue;
            selected.push_back(sid);
            search_required(index + 1, merged(occupied, mask));
            selected.pop_back();
            if (limit_reached) return;
        }
        if (options.allow_partial) search_required(index + 1, occupied);
    };

    search_required(0, taken);
    const bool has_complete = std::any_of(plans.begin(), plans.end(), [](const Plan& p) { return p.is_complete; });
    // A bounded traversal cannot claim infeasibility, even if no plan was saved.
    result.search_status = limit_reached ? "LIMIT_REACHED" : (has_complete ? "FOUND" : "INFEASIBLE");
    result.plans = std::move(plans);
    return result;
}

}  // namespace course_selection
