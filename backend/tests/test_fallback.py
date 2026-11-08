"""Structural fallback coverage, budget accounting and configuration errors."""

from copy import deepcopy
from importlib import import_module

import pytest

from backend.core.fallback import analyze_fallback
from backend.tests.task2_helpers import task2_case, fallback_args, two_required_case


def test_two_sections_have_four_scenarios_and_complete_paths(task2_case):
    case = two_required_case(task2_case)
    before = deepcopy(case)
    result = analyze_fallback(**fallback_args(case))
    assert (result["total"], result["covered"], result["uncovered"], result["unknown"]) == (4, 4, 0, 0)
    assert result["coverage_lower_bound"] == result["coverage_upper_bound"] == 1
    assert result["evaluated"] == 4 and result["skipped_scenarios"] == 0
    for example in result["examples"]:
        assert example["lost_section_ids"]
        completion = set(example["completion_section_ids"])
        assert set(example["won_section_ids"]) <= completion
        assert not completion & set(example["lost_section_ids"])
        assert set(example["added_section_ids"]) == completion - set(example["won_section_ids"])
        assert {case["sections"][sid]["course_id"] for sid in completion} == {"MATH", "PHYS"}
    assert case == before


def test_lost_original_section_cannot_be_reused(task2_case):
    case = two_required_case(task2_case)
    case["sections"]["MATH_B"]["capacity"] = 0
    case["sections"]["PHYS_B"]["capacity"] = 0
    result = analyze_fallback(**fallback_args(case))
    assert (result["covered"], result["uncovered"], result["unknown"]) == (1, 3, 0)


def test_individually_available_alternatives_must_be_jointly_compatible(task2_case):
    case = two_required_case(task2_case)
    # Each alternative fits the other original section, but both alternatives overlap.
    case["section_masks"]["PHYS_B"] = case["section_masks"]["MATH_B"]
    result = analyze_fallback(**fallback_args(case))
    assert (result["covered"], result["uncovered"], result["unknown"]) == (3, 1, 0)


def test_empty_complete_plan_has_one_covered_scenario(task2_case):
    case = two_required_case(task2_case)
    case["student"]["required_course_ids"] = []
    result = analyze_fallback(**fallback_args(case, []))
    assert result["total"] == result["covered"] == result["evaluated"] == 1
    assert result["searched_nodes"] == result["unknown"] == 0


def test_scenario_limit_keeps_original_denominator(task2_case):
    case = two_required_case(task2_case)
    case["config"]["fallback"]["max_scenarios"] = 1
    result = analyze_fallback(**fallback_args(case))
    assert (result["total"], result["covered"], result["unknown"]) == (4, 1, 3)
    assert result["skipped_scenarios"] == 3
    assert result["coverage_lower_bound"] == 0.25
    assert result["coverage_upper_bound"] == 1


def test_exhausted_total_budget_leaves_unknown_scenarios(task2_case):
    case = two_required_case(task2_case)
    case["config"]["fallback"]["max_total_nodes"] = 1
    result = analyze_fallback(**fallback_args(case))
    assert (result["covered"], result["uncovered"], result["unknown"]) == (1, 0, 3)
    assert result["searched_nodes"] == 1
    assert result["limited_scenarios"] == 1
    assert result["skipped_scenarios"] == 2


def test_complete_evidence_counts_as_covered_even_when_search_is_limited(task2_case, monkeypatch):
    case = two_required_case(task2_case)
    case["config"]["fallback"]["max_total_nodes"] = 1
    def limited_solution(*args, **kwargs):
        return {"search_status": "LIMIT_REACHED", "searched_nodes": 1,
                "plans": [{"is_complete": True, "section_ids": ["MATH_A", "PHYS_B"]}]}
    monkeypatch.setattr(import_module("backend.core.fallback"), "call_planner", limited_solution)
    result = analyze_fallback(**fallback_args(case))
    assert (result["covered"], result["uncovered"], result["unknown"]) == (2, 0, 2)
    assert result["limited_scenarios"] == 1


def test_inconsistent_planner_result_is_an_error(task2_case, monkeypatch):
    monkeypatch.setattr(import_module("backend.core.fallback"), "call_planner", lambda *a, **k: {
        "search_status": "FOUND", "searched_nodes": 1, "plans": [],
    })
    with pytest.raises(ValueError, match="inconsistent"):
        analyze_fallback(**fallback_args(two_required_case(task2_case)))


def test_fixed_elective_counts_toward_original_goal(task2_case):
    args = fallback_args(task2_case)
    result = analyze_fallback(**args)
    assert result["total"] == result["covered"] == 8
    for example in result["examples"]:
        if "ART_A" in example["won_section_ids"]:
            assert "HISTORY_A" not in example["completion_section_ids"]


@pytest.mark.parametrize("max_examples", [0, 1, -1])
def test_example_limits(task2_case, max_examples):
    case = two_required_case(task2_case)
    case["config"]["fallback"]["max_examples"] = max_examples
    result = analyze_fallback(**fallback_args(case))
    assert len(result["examples"]) == (3 if max_examples < 0 else max_examples)


def test_rejects_partial_input_plan(task2_case):
    args = fallback_args(task2_case)
    args["plan"]["is_complete"] = False
    with pytest.raises(ValueError, match="complete"):
        analyze_fallback(**args)


@pytest.mark.parametrize("config", [None, [], {}, {"fallback": None}, {"fallback": {}}])
def test_configuration_structure_errors_are_value_errors(task2_case, config):
    args = fallback_args(task2_case)
    args["config"] = config
    with pytest.raises(ValueError):
        analyze_fallback(**args)


@pytest.mark.parametrize("field", ["max_scenarios", "max_total_nodes", "max_examples"])
def test_missing_configuration_field(task2_case, field):
    del task2_case["config"]["fallback"][field]
    with pytest.raises(ValueError, match=field):
        analyze_fallback(**fallback_args(task2_case))


@pytest.mark.parametrize("value", [0, True, 2.5, "100"])
def test_invalid_total_budget(task2_case, value):
    task2_case["config"]["fallback"]["max_total_nodes"] = value
    with pytest.raises(ValueError, match="max_total_nodes"):
        analyze_fallback(**fallback_args(task2_case))


def test_negative_limits_and_input_order_are_supported(task2_case):
    case = two_required_case(task2_case)
    case["config"]["fallback"].update(max_scenarios=-1, max_total_nodes=-1)
    result = analyze_fallback(**fallback_args(case))
    other = deepcopy(case)
    other["snapshot"]["current_application"].reverse()
    other["sections"] = dict(reversed(list(other["sections"].items())))
    assert result == analyze_fallback(**fallback_args(other))
