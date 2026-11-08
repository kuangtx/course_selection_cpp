"""Search acceptance tests with the real mask and preference functions."""

from copy import deepcopy
from itertools import combinations

import pytest


def plan_keys(result):
    return {frozenset(plan["section_ids"]) for plan in result["plans"]}


def assert_legal(result, student, catalog, fixed=()):
    """Check plan constraints independently of the search implementation."""
    courses, sections, masks = catalog
    required = set(student["required_course_ids"])
    optional = set(student["optional_course_ids"])
    requirement = student["optional_requirement"]
    for plan in result["plans"]:
        ids = plan["section_ids"]
        course_ids = [sections[sid]["course_id"] for sid in ids]
        assert len(ids) == len(set(ids))
        assert len(course_ids) == len(set(course_ids))
        assert set(course_ids) <= required | optional
        assert set(fixed) <= set(ids)
        for first, second in combinations(ids, 2):
            assert masks[first] & masks[second] == 0
        missing = required - set(course_ids)
        chosen_optional = optional & set(course_ids)
        achieved = (len(chosen_optional) if requirement["mode"] == "count"
                    else sum(courses[cid]["credits"] for cid in chosen_optional))
        gap = max(0, requirement["target"] - achieved)
        assert plan["unmet_requirements"]["required_course_ids"] == sorted(missing)
        assert plan["unmet_requirements"]["optional"]["achieved"] == pytest.approx(achieved)
        assert plan["unmet_requirements"]["optional"]["gap"] == pytest.approx(gap)
        assert plan["is_complete"] == (not missing and gap == 0)


def test_T05_backtracks_required_section(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART"], target=1)
    result = run_search(student)
    assert result["search_status"] == "FOUND"
    assert plan_keys(result) == {frozenset(["MATH_B", "ART_A"])}
    assert_legal(result, student, catalog)


def test_required_search_backtracks_across_multiple_courses(make_student, run_search, catalog):
    student = make_student(required=["MATH", "PHYS"])
    result = run_search(student)
    assert plan_keys(result) == {frozenset(["MATH_A", "PHYS_A"])}
    assert_legal(result, student, catalog)


def test_exhaustive_conflict_is_infeasible(make_student, run_search):
    student = make_student(required=["MATH"], optional=["ART"], target=1)
    result = run_search(student, allowed_section_ids={"MATH_A", "ART_A"})
    assert result["search_status"] == "INFEASIBLE"
    assert result["plans"] == []


def test_all_small_count_solutions_are_found_without_extra_courses(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART", "HISTORY"], target=1)
    result = run_search(student)
    assert plan_keys(result) == {
        frozenset(["MATH_A", "HISTORY_A"]),
        frozenset(["MATH_B", "ART_A"]),
        frozenset(["MATH_B", "HISTORY_A"]),
    }
    assert len(result["plans"]) == 3
    assert_legal(result, student, catalog)


def test_credit_goal_can_be_exceeded_by_final_course(make_student, run_search, catalog):
    student = make_student(optional=["ART", "HISTORY"], mode="credits", target=4)
    result = run_search(student)
    assert result["search_status"] == "FOUND"
    assert plan_keys(result) == {frozenset(["ART_A", "HISTORY_A"])}
    assert result["plans"][0]["unmet_requirements"]["optional"]["achieved"] == 5
    assert_legal(result, student, catalog)


def test_credit_search_stops_after_goal_is_met(make_student, run_search):
    student = make_student(optional=["ART", "HISTORY", "MUSIC"], mode="credits", target=2)
    result = run_search(student)
    assert plan_keys(result) == {frozenset(["ART_A"]), frozenset(["HISTORY_A"])}


def test_zero_optional_target_does_not_add_courses(make_student, run_search):
    result = run_search(make_student(optional=["ART", "HISTORY"], target=0))
    assert result["search_status"] == "FOUND"
    assert plan_keys(result) == {frozenset()}


def test_fixed_course_is_kept_and_counted(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART", "HISTORY"], target=1)
    result = run_search(student, fixed_section_ids=["MATH_B", "HISTORY_A"],
                        allowed_section_ids=set())
    assert result["search_status"] == "FOUND"
    assert plan_keys(result) == {frozenset(["MATH_B", "HISTORY_A"])}
    assert_legal(result, student, catalog, fixed=["MATH_B", "HISTORY_A"])


def test_fixed_optional_credits_count_toward_goal(make_student, run_search, catalog):
    student = make_student(optional=["ART", "HISTORY"], mode="credits", target=4)
    result = run_search(student, fixed_section_ids=["HISTORY_A"], allowed_section_ids={"ART_A"})
    assert result["search_status"] == "FOUND"
    assert plan_keys(result) == {frozenset(["HISTORY_A", "ART_A"])}
    assert_legal(result, student, catalog, fixed=["HISTORY_A"])


def test_fixed_course_is_not_swapped_to_complete_plan(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART"], target=1)
    result = run_search(student, fixed_section_ids=["MATH_A"], allow_partial=True)
    assert result["search_status"] == "INFEASIBLE"
    assert plan_keys(result) == {frozenset(["MATH_A"])}
    assert_legal(result, student, catalog, fixed=["MATH_A"])


def test_allowed_and_excluded_sections_filter_new_choices(make_student, run_search):
    student = make_student(optional=["ART", "HISTORY", "MUSIC"], target=1)
    result = run_search(student, allowed_section_ids={"ART_A", "HISTORY_A"},
                        excluded_section_ids={"ART_A"})
    assert plan_keys(result) == {frozenset(["HISTORY_A"])}


def test_empty_allowed_set_prevents_new_enrollment(make_student, run_search):
    result = run_search(make_student(optional=["ART"], target=1), allowed_section_ids=set())
    assert result["search_status"] == "INFEASIBLE"
    assert result["plans"] == []


def test_no_complete_plan_returns_no_first_round_candidates(make_student, run_search):
    result = run_search(make_student(optional=["ART"], target=2))
    assert result["search_status"] == "INFEASIBLE"
    assert result["plans"] == []


def test_partial_search_prioritizes_required_completion(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART"], target=1)
    result = run_search(student, allowed_section_ids={"MATH_A", "ART_A"}, allow_partial=True)
    assert result["search_status"] == "INFEASIBLE"
    assert [p["section_ids"] for p in result["plans"]] == [["MATH_A"], ["ART_A"], []]
    assert_legal(result, student, catalog)


def test_partial_search_prioritizes_optional_gap_before_preference(make_student, run_search, catalog):
    student = make_student(optional=["ART", "HISTORY"], target=3,
                           preferences={"course_scores": {"ART": 0, "HISTORY": 100}})
    result = run_search(student, allow_partial=True)
    assert set(result["plans"][0]["section_ids"]) == {"ART_A", "HISTORY_A"}
    assert result["plans"][0]["unmet_requirements"]["optional"]["gap"] == 1
    assert_legal(result, student, catalog)


def test_partial_credit_gap_is_reported_in_credits(make_student, run_search, catalog):
    student = make_student(optional=["ART", "HISTORY"], mode="credits", target=6)
    result = run_search(student, allow_partial=True)
    assert result["search_status"] == "INFEASIBLE"
    assert result["plans"][0]["unmet_requirements"]["optional"] == {
        "mode": "credits", "target": 6, "achieved": 5, "gap": 1,
    }
    assert_legal(result, student, catalog)


def test_T06_budget_exhaustion_is_not_infeasibility(make_student, run_search):
    result = run_search(make_student(required=["MATH"]), max_search_nodes=1)
    assert result["search_status"] == "LIMIT_REACHED"
    assert result["searched_nodes"] == 1
    assert result["plans"] == []


def test_budget_exhaustion_keeps_solutions_already_found(make_student, run_search):
    student = make_student(required=["MATH"])
    full = run_search(student)
    saw_partial_result = False
    for budget in range(1, full["searched_nodes"]):
        result = run_search(student, max_search_nodes=budget)
        assert result["searched_nodes"] <= budget
        if result["plans"]:
            saw_partial_result = True
            assert result["search_status"] == "LIMIT_REACHED"
            assert plan_keys(result) <= plan_keys(full)
    assert saw_partial_result


def test_candidate_limit_keeps_best_candidate_not_first_seen(make_student, run_search):
    student = make_student(required=["MATH"], optional=["HISTORY"], target=1)
    result = run_search(student, candidate_limit=1)
    assert result["search_status"] == "FOUND"
    assert len(result["plans"]) == 1
    assert set(result["plans"][0]["section_ids"]) == {"MATH_B", "HISTORY_A"}
    assert result["plans"][0]["preference_score"]["total"] == pytest.approx(86)


def test_repeated_search_and_catalog_insertion_order_are_stable(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART", "HISTORY"], target=1)
    expected = run_search(student)
    assert run_search(student) == expected
    sections = catalog[1]
    reordered = dict(reversed(list(sections.items())))
    sections.clear()
    sections.update(reordered)
    assert run_search(student) == expected


def test_search_does_not_mutate_inputs(make_student, run_search, catalog):
    student = make_student(required=["MATH"], optional=["ART", "HISTORY"], target=1)
    fixed = ["MATH_B"]
    allowed = {"ART_A", "HISTORY_A"}
    excluded = {"ART_A"}
    before = deepcopy((student, catalog, fixed, allowed, excluded))
    run_search(student, fixed_section_ids=fixed, allowed_section_ids=allowed,
               excluded_section_ids=excluded, allow_partial=True)
    assert (student, catalog, fixed, allowed, excluded) == before


@pytest.mark.parametrize("fixed", [
    ["MATH_A", "MATH_B"],
    ["MATH_A", "ART_A"],
    ["MATH_A", "MATH_A"],
    ["UNKNOWN"],
])
def test_invalid_fixed_classes_are_rejected(make_student, run_search, fixed):
    student = make_student(required=["MATH"], optional=["ART"], target=1)
    with pytest.raises(ValueError):
        run_search(student, fixed_section_ids=fixed)


def test_excluded_fixed_section_is_rejected(make_student, run_search):
    with pytest.raises(ValueError):
        run_search(make_student(required=["MATH"]), fixed_section_ids=["MATH_A"],
                   excluded_section_ids={"MATH_A"})


@pytest.mark.parametrize("field,value", [
    ("required_course_ids", ["MATH", "MATH"]),
    ("required_course_ids", ["UNKNOWN"]),
    ("optional_course_ids", ["MATH"]),
    ("optional_requirement", {"mode": "count", "target": 1.5}),
    ("optional_requirement", {"mode": "credits", "target": float("nan")}),
    ("optional_requirement", {"mode": "unknown", "target": 1}),
])
def test_invalid_requirements_are_rejected(make_student, run_search, field, value):
    student = make_student(required=["MATH"])
    student[field] = value
    with pytest.raises(ValueError):
        run_search(student)


@pytest.mark.parametrize("name,value", [
    ("candidate_limit", 0), ("max_search_nodes", 0),
    ("max_search_nodes", True), ("allow_partial", "yes"),
])
def test_invalid_search_controls_are_rejected(make_student, run_search, name, value):
    with pytest.raises(ValueError):
        run_search(make_student(required=["MATH"]), **{name: value})


def test_missing_candidate_mask_is_rejected(make_student, run_search):
    with pytest.raises(ValueError):
        run_search(make_student(required=["MATH"]), section_masks={})
