#pragma once

#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace course_selection {

struct Course {
    std::string id;
    double credits = 0.0;
};

// The Python adapter can convert each Python integer time mask into little-endian
// 64-bit words. Word 0 contains semester slot 0 through slot 63.
struct Section {
    std::string id;
    std::string course_id;
    int capacity = 0;
    std::vector<std::uint64_t> time_mask;
};

struct Student {
    std::string id;
    std::vector<std::string> required_course_ids;  // Input order is preserved.
    std::vector<std::string> optional_course_ids;  // Input order is preserved.
    std::string optional_mode = "count";           // "count" or "credits".
    double optional_target = 0.0;
    std::map<std::string, double> course_scores;
    double early_penalty_per_week = 0.0;
};

struct Calendar {
    int total_weeks = 18;
    int days_per_week = 7;
    int periods_per_day = 13;
};

struct Scoring {
    double default_course_score = 80.0;
    double course_weight = 0.7;
    double time_weight = 0.3;
    double default_early_penalty = 10.0;
};

struct SearchOptions {
    std::vector<std::string> fixed_section_ids;
    bool use_allowed_whitelist = false;
    std::set<std::string> allowed_section_ids;
    std::set<std::string> excluded_section_ids;
    bool allow_partial = false;
    int candidate_limit = 20;  // Negative means unlimited; zero is invalid.
    int max_search_nodes = 10000;  // Negative means unlimited; zero is invalid.
};

struct PreferenceScore {
    double total = 0.0;
    double course_preference = 0.0;
    int total_early_days = 0;
    double average_early_days_per_week = 0.0;
    double time_score = 0.0;
};

struct OptionalGap {
    std::string mode;
    double target = 0.0;
    double achieved = 0.0;
    double gap = 0.0;
};

struct Plan {
    std::vector<std::string> section_ids;  // Fixed selections followed by search picks.
    PreferenceScore preference_score;
    bool is_complete = false;
    std::vector<std::string> unmet_required_course_ids;
    OptionalGap optional;
};

struct SearchResult {
    std::string search_status;  // FOUND, INFEASIBLE, or LIMIT_REACHED.
    int searched_nodes = 0;
    std::vector<Plan> plans;
};

// Throws std::invalid_argument for malformed inputs, as the Python planner does.
SearchResult plan_courses(
    const Student& student,
    const std::map<std::string, Course>& courses,
    const std::map<std::string, Section>& sections,
    const Calendar& calendar,
    const Scoring& scoring,
    const SearchOptions& options);

}  // namespace course_selection
