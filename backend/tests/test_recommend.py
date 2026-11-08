"""Public recommendation routing and real task-1/task-2 integration."""

from copy import deepcopy
from importlib import import_module

import pytest

from backend.core.recommend import compare_plans
from backend.tests.task2_helpers import task2_case, call_recommend


@pytest.mark.parametrize("old_ids,new_ids,count,added,removed,switched", [
    (["MATH_A", "ART_A"], ["MATH_B", "HISTORY_A"], 2, ["HISTORY"], ["ART"], ["MATH"]),
    (["ART_A", "MATH_A"], ["MATH_A", "ART_A"], 0, [], [], []),
    ([], ["MATH_A", "PHYS_A"], 2, ["MATH", "PHYS"], [], []),
    (["MATH_A"], [], 1, [], ["MATH"], []),
    ([], [], 0, [], [], []),
])
def test_compare_plans(task2_case, old_ids, new_ids, count, added, removed, switched):
    old, new = {"section_ids": old_ids}, {"section_ids": new_ids}
    before = deepcopy((old, new))
    result = compare_plans(old, new, sections=task2_case["sections"])
    assert result["changed_course_count"] == count
    assert result["added_course_ids"] == added
    assert result["removed_course_ids"] == removed
    assert [item["course_id"] for item in result["switched_sections"]] == switched
    for item in result["switched_sections"]:
        assert item["old_section_id"] in old_ids
        assert item["new_section_id"] in new_ids
    assert (old, new) == before


def test_initial_ranks_by_overall_score_not_just_preference(task2_case):
    before = deepcopy(task2_case)
    result = call_recommend(task2_case, purpose="initial", limit=-1)
    assert result["purpose"] == "initial" and result["decision"] == "SHOW_PLANS"
    assert result["current_plan"] is None
    assert result["state_version"] == 12 and result["plan_revision"] == 2
    plans = result["plans"]
    assert len(plans) == 8
    assert set(plans[0]["section_ids"]) == {"MATH_B", "PHYS_B", "HISTORY_A"}
    assert plans[0]["recommendation_score"] == pytest.approx(0.895)
    assert plans[0]["preference_score"]["total"] < max(p["preference_score"]["total"] for p in plans)
    assert all(p["is_complete"] and p["comparison"] is None for p in plans)
    assert len({tuple(p["section_ids"]) for p in plans}) == len(plans)
    assert task2_case == before


def test_initial_excludes_zero_capacity_sections(task2_case):
    task2_case["sections"]["MATH_B"]["capacity"] = 0
    result = call_recommend(task2_case, purpose="initial", limit=-1)
    assert all("MATH_B" not in p["section_ids"] for p in result["plans"])


@pytest.mark.parametrize("purpose", ["initial", "adjustment", "supplement"])
def test_positive_and_negative_display_limits(task2_case, purpose):
    if purpose == "supplement":
        task2_case["snapshot"]["phase"] = "ROUND2_OPEN"
    all_plans = call_recommend(task2_case, purpose=purpose, limit=-1)["plans"]
    assert len(all_plans) > 1
    assert call_recommend(task2_case, purpose=purpose, limit=1)["plans"] == all_plans[:1]
    assert call_recommend(task2_case, purpose=purpose, limit=-5)["plans"] == all_plans


def test_adjustment_swaps_one_crowded_course_and_preserves_other_courses(task2_case):
    before = deepcopy(task2_case)
    result = call_recommend(task2_case, purpose="adjustment", limit=-1)
    assert result["purpose"] == "adjustment" and result["decision"] == "SHOW_PLANS"
    assert result["current_plan"]["recommendation_score"] == pytest.approx(0.6524)
    plans = result["plans"]
    changes = [p["comparison"]["changed_course_count"] for p in plans]
    assert changes == sorted(changes)
    assert changes and all(count == 1 for count in changes)
    current = set(before["snapshot"]["current_application"])
    crowded = {sid for sid in current
               if len(before["snapshot"]["applicants"][sid]) > before["sections"][sid]["capacity"]}
    for plan in plans:
        removed = current - set(plan["section_ids"])
        assert len(removed) == 1 and removed <= crowded
        assert len(current & set(plan["section_ids"])) == len(current) - 1
    assert all(set(p["section_ids"]) != set(before["snapshot"]["current_application"]) for p in plans)
    first = plans[0]["comparison"]
    assert first["change_ratio"] == pytest.approx(1 / 3)
    assert first["risk_improvement"] > 0
    assert task2_case == before


def test_adjustment_does_not_filter_alternatives_by_legacy_improvement_threshold(task2_case):
    task2_case["config"]["adjustment"]["min_score_improvement"] = 1
    result = call_recommend(task2_case, purpose="adjustment")
    assert result["decision"] == "SHOW_PLANS" and result["plans"]
    assert all(plan["comparison"]["score_improvement"] < 1 for plan in result["plans"])
    assert result["current_plan"]["is_complete"]


def test_adjustment_reevaluates_old_plan_after_preference_change(task2_case):
    task2_case["student"]["preferences"]["course_scores"]["ART"] = 60
    result = call_recommend(task2_case, purpose="adjustment")
    assert result["current_plan"]["preference_score"]["total"] == pytest.approx(69)


def test_round_two_preserves_full_enrolled_sections_and_skips_first_round_evaluation(task2_case, monkeypatch):
    snapshot = task2_case["snapshot"]
    snapshot.update(phase="ROUND2_OPEN", enrolled_section_ids=["MATH_A"])
    snapshot["remaining"]["MATH_A"] = 0
    def unexpected(*args, **kwargs):
        raise AssertionError("Supplement must not evaluate first-round risk/fallback")
    monkeypatch.setattr(import_module("backend.core.evaluate_plan"), "evaluate_plan", unexpected)
    monkeypatch.setattr(import_module("backend.core.fallback"), "analyze_fallback", unexpected)
    result = call_recommend(task2_case, purpose="supplement", limit=-1)
    assert result["plans"][0]["is_complete"]
    for plan in result["plans"]:
        assert "MATH_A" in plan["section_ids"]
        assert "MATH_A" not in plan["new_section_ids"]
        assert set(plan["new_section_ids"]) == set(plan["section_ids"]) - {"MATH_A"}
        assert plan["risk"] is plan["fallback"] is plan["recommendation_score"] is None


def test_round_two_returns_partial_plans_even_if_infeasible(task2_case):
    snapshot = task2_case["snapshot"]
    snapshot.update(phase="ROUND2_OPEN", enrolled_section_ids=["MATH_A"])
    snapshot["remaining"] = dict.fromkeys(task2_case["sections"], 0)
    snapshot["remaining"]["PHYS_A"] = 1
    result = call_recommend(task2_case, purpose="supplement")
    assert result["search_status"] == "INFEASIBLE"
    assert result["decision"] == "SHOW_PLANS"
    plan = result["plans"][0]
    assert not plan["is_complete"] and plan["new_section_ids"] == ["PHYS_A"]
    assert plan["unmet_requirements"]["optional"]["gap"] == 1


def test_round_two_empty_whitelist_adds_nothing(task2_case):
    task2_case["snapshot"].update(phase="ROUND2_OPEN", enrolled_section_ids=["MATH_A"],
                                  remaining=dict.fromkeys(task2_case["sections"], 0))
    result = call_recommend(task2_case, purpose="supplement")
    assert result["plans"][0]["section_ids"] == ["MATH_A"]
    assert result["plans"][0]["new_section_ids"] == []
    assert not result["plans"][0]["is_complete"]


def test_round_two_already_complete_enrollment(task2_case):
    task2_case["snapshot"].update(phase="ROUND2_OPEN", enrolled_section_ids=["MATH_A", "PHYS_A", "ART_A"],
                                  remaining=dict.fromkeys(task2_case["sections"], 0))
    plan = call_recommend(task2_case, purpose="supplement")["plans"][0]
    assert plan["is_complete"] and plan["new_section_ids"] == []


@pytest.mark.parametrize("purpose", ["initial", "adjustment", "supplement"])
def test_search_limit_is_not_reported_as_proven_infeasibility(task2_case, purpose):
    task2_case["config"]["search"]["max_search_nodes"] = 1
    if purpose == "supplement":
        task2_case["snapshot"]["phase"] = "ROUND2_OPEN"
    result = call_recommend(task2_case, purpose=purpose)
    assert result["search_status"] == "LIMIT_REACHED"
    assert result["plans"] == []
    assert result["decision"] == ("KEEP_CURRENT" if purpose == "adjustment" else "NO_PLAN")
    assert result["limitations"]


def test_fallback_limits_do_not_replace_main_search_status(task2_case):
    task2_case["config"]["fallback"]["max_scenarios"] = 1
    result = call_recommend(task2_case, purpose="initial")
    assert result["search_status"] == "FOUND"
    assert all(plan["fallback"]["unknown"] > 0 for plan in result["plans"])


@pytest.mark.parametrize("limit", [0, True, 1.5, "3"])
def test_public_entry_rejects_invalid_limit(task2_case, limit):
    with pytest.raises(ValueError, match="limit"):
        call_recommend(task2_case, purpose="initial", limit=limit)


@pytest.mark.parametrize("purpose", ["bad", "", None])
def test_public_entry_rejects_unknown_purpose(task2_case, purpose):
    with pytest.raises(ValueError):
        call_recommend(task2_case, purpose=purpose)


@pytest.mark.parametrize("purpose,phase", [
    ("initial", "ROUND2_OPEN"), ("adjustment", "ROUND2_OPEN"),
    ("supplement", "ROUND1_OPEN"),
])
def test_public_entry_rejects_wrong_phase(task2_case, purpose, phase):
    task2_case["snapshot"]["phase"] = phase
    with pytest.raises(ValueError):
        call_recommend(task2_case, purpose=purpose)


@pytest.mark.parametrize("field,purpose", [
    ("state_version", "initial"), ("plan_revision", "initial"),
    ("applicants", "initial"), ("current_application", "adjustment"),
])
def test_missing_snapshot_fields_are_errors(task2_case, field, purpose):
    del task2_case["snapshot"][field]
    with pytest.raises(ValueError):
        call_recommend(task2_case, purpose=purpose)


@pytest.mark.parametrize("remaining", [{}, {"MATH_A": True}])
def test_second_round_rejects_missing_or_invalid_remaining(task2_case, remaining):
    task2_case["snapshot"].update(phase="ROUND2_OPEN", remaining=remaining)
    with pytest.raises(ValueError):
        call_recommend(task2_case, purpose="supplement")


@pytest.mark.parametrize("purpose", ["initial", "adjustment", "supplement"])
def test_valid_empty_requirement_plan(task2_case, purpose):
    task2_case["student"].update(required_course_ids=[], optional_course_ids=[],
                                  optional_requirement={"mode": "count", "target": 0})
    task2_case["snapshot"]["current_application"] = []
    if purpose == "supplement":
        task2_case["snapshot"]["phase"] = "ROUND2_OPEN"
    result = call_recommend(task2_case, purpose=purpose)
    if purpose == "adjustment":
        assert result["decision"] == "KEEP_CURRENT"
        assert result["current_plan"]["section_ids"] == []
    else:
        assert result["decision"] == "SHOW_PLANS"
        assert result["plans"][0]["section_ids"] == []
        assert result["plans"][0]["is_complete"]


@pytest.mark.parametrize("purpose", ["initial", "adjustment", "supplement"])
def test_results_are_stable_and_inputs_unchanged(task2_case, purpose):
    if purpose == "supplement":
        task2_case["snapshot"]["phase"] = "ROUND2_OPEN"
    before = deepcopy(task2_case)
    result = call_recommend(task2_case, purpose=purpose, limit=-1)
    assert task2_case == before
    reordered = deepcopy(task2_case)
    reordered["sections"] = dict(reversed(list(reordered["sections"].items())))
    reordered["snapshot"]["current_application"].reverse()
    assert call_recommend(reordered, purpose=purpose, limit=-1) == result
