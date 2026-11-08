"""Single-plan evaluation and preference reuse across old/new plans."""

from copy import deepcopy
from importlib import import_module
from unittest.mock import Mock

import pytest

from backend.core.evaluate_plan import evaluate_plan
from backend.tests.task2_helpers import task2_case


def evaluate(case, section_ids=None, **kwargs):
    plan = kwargs.pop("plan", {"section_ids": section_ids if section_ids is not None else case["snapshot"]["current_application"]})
    return evaluate_plan(plan=plan, **case, **kwargs)


def test_evaluation_combines_actual_preference_risk_and_coverage(task2_case):
    before = deepcopy(task2_case)
    result = evaluate(task2_case)
    assert result["preference_score"]["total"] == pytest.approx(90)
    assert result["risk"]["first_round_all_win_probability"] == pytest.approx(0.008)
    assert result["fallback"]["coverage_lower_bound"] == 1
    assert result["recommendation_score"] == pytest.approx(0.6524)
    assert result["unmet_requirements"]["optional"] == {
        "mode": "count", "target": 1, "achieved": 1, "gap": 0,
    }
    assert task2_case == before


def test_old_preference_is_recalculated_even_if_score_exists(task2_case):
    plan = {"section_ids": list(task2_case["snapshot"]["current_application"]),
            "preference_score": {"total": 999}}
    before = deepcopy(plan)
    result = evaluate(task2_case, plan=plan, recalculate_preference=True)
    assert result["preference_score"]["total"] == pytest.approx(90)
    task2_case["student"]["preferences"]["course_scores"]["ART"] = 60
    updated = evaluate(task2_case, plan=plan, recalculate_preference=True)
    assert updated["preference_score"]["total"] == pytest.approx(69)
    assert plan == before


def test_new_candidate_reuses_current_planner_score(task2_case, monkeypatch):
    from backend.core.call_planner import call_planner
    case = task2_case
    result = call_planner(case["student"], case["courses"], case["sections"],
                          case["section_masks"], case["config"],
                          fixed=[], allowed=None, excluded=set(), allow_partial=False)
    candidate = result["plans"][0]
    score = deepcopy(candidate["preference_score"])
    module = import_module("backend.core.evaluate_plan")
    spy = Mock(side_effect=AssertionError("New candidates must not be rescored"))
    monkeypatch.setattr(module, "preference", spy)
    evaluated = evaluate(case, plan=candidate, recalculate_preference=False)
    assert evaluated["preference_score"] == score
    spy.assert_not_called()


def test_missing_preference_is_calculated_even_when_reuse_requested(task2_case, monkeypatch):
    module = import_module("backend.core.evaluate_plan")
    spy = Mock(wraps=module.preference)
    monkeypatch.setattr(module, "preference", spy)
    result = evaluate(task2_case, recalculate_preference=False)
    spy.assert_called_once()
    assert result["preference_score"]["total"] == pytest.approx(90)


@pytest.mark.parametrize("section_ids", [
    ["MATH_A", "ART_A"],
    ["MATH_A", "MATH_B", "PHYS_A", "ART_A"],
    ["MATH_A", "MATH_A", "PHYS_A", "ART_A"],
])
def test_incomplete_or_duplicate_course_plan_is_rejected(task2_case, section_ids):
    with pytest.raises(ValueError):
        evaluate(task2_case, section_ids)


def test_time_conflict_is_rejected(task2_case):
    task2_case["section_masks"]["PHYS_A"] = task2_case["section_masks"]["MATH_A"]
    with pytest.raises(ValueError, match="Time conflict"):
        evaluate(task2_case)


def test_course_outside_student_requirements_is_rejected(task2_case):
    task2_case["student"]["optional_course_ids"] = ["HISTORY"]
    with pytest.raises(ValueError):
        evaluate(task2_case)


def test_credit_requirement_reports_overshoot(task2_case):
    task2_case["student"]["optional_requirement"] = {"mode": "credits", "target": 2.5}
    result = evaluate(task2_case, ["MATH_A", "PHYS_A", "HISTORY_A"])
    assert result["unmet_requirements"]["optional"] == {
        "mode": "credits", "target": 2.5, "achieved": 3, "gap": 0,
    }


def test_empty_complete_plan(task2_case):
    task2_case["student"].update(required_course_ids=[], optional_course_ids=[],
                                  optional_requirement={"mode": "count", "target": 0})
    result = evaluate(task2_case, [])
    assert result["is_complete"]
    assert result["preference_score"]["total"] == 0
    assert result["risk"]["first_round_all_win_probability"] == 1
    assert result["fallback"]["total"] == result["fallback"]["covered"] == 1
