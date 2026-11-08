#include "planner.hpp"

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;
using namespace course_selection;

namespace {

py::object apply_number_operation(
    binaryfunc operation,
    const py::handle& left,
    const py::handle& right) {
    PyObject* result = operation(left.ptr(), right.ptr());
    if (result == nullptr) throw py::error_already_set();
    return py::reinterpret_steal<py::object>(result);
}

// Use Python integer operations here so semester masks wider than 64 bits survive.
std::vector<std::uint64_t> mask_to_words(const py::int_& value) {
    const py::int_ zero(0);
    const int is_negative = PyObject_RichCompareBool(value.ptr(), zero.ptr(), Py_LT);
    if (is_negative < 0) throw py::error_already_set();
    if (is_negative == 1) throw std::invalid_argument("time_mask must be non-negative");

    const py::int_ one(1);
    const py::int_ shift(64);
    const py::int_ word_mask = apply_number_operation(
        PyNumber_Subtract,
        apply_number_operation(PyNumber_Lshift, one, shift),
        one).cast<py::int_>();
    py::int_ remaining(value);
    std::vector<std::uint64_t> words;
    while (true) {
        const int is_positive = PyObject_RichCompareBool(remaining.ptr(), zero.ptr(), Py_GT);
        if (is_positive < 0) throw py::error_already_set();
        if (is_positive == 0) break;
        const py::object low_word = apply_number_operation(PyNumber_And, remaining, word_mask);
        words.push_back(low_word.cast<std::uint64_t>());
        remaining = apply_number_operation(PyNumber_Rshift, remaining, shift).cast<py::int_>();
    }
    return words;
}

py::int_ words_to_mask(const std::vector<std::uint64_t>& words) {
    py::int_ value(0);
    const py::int_ shift(64);
    for (auto it = words.rbegin(); it != words.rend(); ++it) {
        value = apply_number_operation(PyNumber_Lshift, value, shift).cast<py::int_>();
        value = apply_number_operation(PyNumber_Or, value, py::int_(*it)).cast<py::int_>();
    }
    return value;
}

}  // namespace

// Executed when Python imports the compiled module, not during compilation.
PYBIND11_MODULE(_planner, module) {
    module.doc() = "Python bindings for the course selection C++ planner";

    py::class_<Course>(module, "Course")
        .def(py::init<>())
        .def_readwrite("id", &Course::id)
        .def_readwrite("credits", &Course::credits);

    py::class_<Section>(module, "Section")
        .def(py::init<>())
        .def(py::init([](std::string id, std::string course_id, int capacity, py::int_ time_mask) {
            return Section{std::move(id), std::move(course_id), capacity, mask_to_words(time_mask)};
        }), py::arg("id"), py::arg("course_id"), py::arg("capacity"), py::arg("time_mask"))
        .def_readwrite("id", &Section::id)
        .def_readwrite("course_id", &Section::course_id)
        .def_readwrite("capacity", &Section::capacity)
        .def_property("time_mask", [](const Section& section) {
            return words_to_mask(section.time_mask);
        }, [](Section& section, py::int_ value) {
            section.time_mask = mask_to_words(value);
        });

    py::class_<Student>(module, "Student")
        .def(py::init<>())
        .def_readwrite("id", &Student::id)
        .def_readwrite("required_course_ids", &Student::required_course_ids)
        .def_readwrite("optional_course_ids", &Student::optional_course_ids)
        .def_readwrite("optional_mode", &Student::optional_mode)
        .def_readwrite("optional_target", &Student::optional_target)
        .def_readwrite("course_scores", &Student::course_scores)
        .def_readwrite("early_penalty_per_week", &Student::early_penalty_per_week);

    py::class_<Calendar>(module, "Calendar")
        .def(py::init<>())
        .def_readwrite("total_weeks", &Calendar::total_weeks)
        .def_readwrite("days_per_week", &Calendar::days_per_week)
        .def_readwrite("periods_per_day", &Calendar::periods_per_day);

    py::class_<Scoring>(module, "Scoring")
        .def(py::init<>())
        .def_readwrite("default_course_score", &Scoring::default_course_score)
        .def_readwrite("course_weight", &Scoring::course_weight)
        .def_readwrite("time_weight", &Scoring::time_weight)
        .def_readwrite("default_early_penalty", &Scoring::default_early_penalty);

    py::class_<SearchOptions>(module, "SearchOptions")
        .def(py::init<>())
        .def_readwrite("fixed_section_ids", &SearchOptions::fixed_section_ids)
        .def_readwrite("use_allowed_whitelist", &SearchOptions::use_allowed_whitelist)
        .def_readwrite("allowed_section_ids", &SearchOptions::allowed_section_ids)
        .def_readwrite("excluded_section_ids", &SearchOptions::excluded_section_ids)
        .def_readwrite("allow_partial", &SearchOptions::allow_partial)
        .def_readwrite("candidate_limit", &SearchOptions::candidate_limit)
        .def_readwrite("max_search_nodes", &SearchOptions::max_search_nodes);

    py::class_<PreferenceScore>(module, "PreferenceScore")
        .def_readonly("total", &PreferenceScore::total)
        .def_readonly("course_preference", &PreferenceScore::course_preference)
        .def_readonly("total_early_days", &PreferenceScore::total_early_days)
        .def_readonly("average_early_days_per_week", &PreferenceScore::average_early_days_per_week)
        .def_readonly("time_score", &PreferenceScore::time_score);

    py::class_<OptionalGap>(module, "OptionalGap")
        .def_readonly("mode", &OptionalGap::mode)
        .def_readonly("target", &OptionalGap::target)
        .def_readonly("achieved", &OptionalGap::achieved)
        .def_readonly("gap", &OptionalGap::gap);

    py::class_<Plan>(module, "Plan")
        .def_readonly("section_ids", &Plan::section_ids)
        .def_readonly("preference_score", &Plan::preference_score)
        .def_readonly("is_complete", &Plan::is_complete)
        .def_readonly("unmet_required_course_ids", &Plan::unmet_required_course_ids)
        .def_readonly("optional", &Plan::optional);

    py::class_<SearchResult>(module, "SearchResult")
        .def_readonly("search_status", &SearchResult::search_status)
        .def_readonly("searched_nodes", &SearchResult::searched_nodes)
        .def_readonly("plans", &SearchResult::plans);

    module.def("plan_courses", &plan_courses,
               py::arg("student"), py::arg("courses"), py::arg("sections"),
               py::arg("calendar"), py::arg("scoring"), py::arg("options"),
               "Search course-section combinations and return ranked plans.",
               // Input objects are converted before the call; the search itself is pure C++.
               py::call_guard<py::gil_scoped_release>());
}
