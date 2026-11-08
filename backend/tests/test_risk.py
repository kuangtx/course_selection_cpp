"""Risk and alert contracts. Threshold decisions deliberately use no tolerance.

Float results use approx for representation, not for triggering alerts.
Invalid-input tests require ValueError; missing implementation is a real failure.
"""

from copy import deepcopy

import pytest

from backend.core.risk import calculate_all_win_probability, should_alert


@pytest.mark.parametrize("capacity,members,expected", [
    (40, {f"S{i}" for i in range(50)}, 0.8),
    (40, {f"T{i}" for i in range(50)}, 40 / 51),
    (40, set(), 1.0),
    (0, set(), 0.0),
    (40, {"S0", "S1"}, 1.0),
])
def test_single_section_probability(capacity, members, expected):
    sections = {"A": {"capacity": capacity}}
    applicants = {"A": members}
    before = deepcopy((sections, applicants))
    result = calculate_all_win_probability("S0", ["A"], sections=sections, applicants=applicants)
    assert result["section_probabilities"]["A"] == pytest.approx(expected)
    assert result["first_round_all_win_probability"] == pytest.approx(expected)
    assert result["first_round_failure_risk"] == pytest.approx(1 - expected)
    assert (sections, applicants) == before


def test_multiple_sections_and_stable_order():
    sections = {"B": {"capacity": 1}, "A": {"capacity": 4}}
    applicants = {"A": {"S", "T", "U", "V", "W"}, "B": {"S", "T"}}
    result = calculate_all_win_probability("S", ["B", "A"], sections=sections, applicants=applicants)
    assert result["section_probabilities"] == {"A": 0.8, "B": 0.5}
    assert list(result["section_probabilities"]) == ["A", "B"]
    assert result["first_round_all_win_probability"] == pytest.approx(0.4)
    assert result["first_round_failure_risk"] == pytest.approx(0.6)
    assert result == calculate_all_win_probability("S", ["A", "B"], sections=sections, applicants=applicants)


def test_empty_plan():
    assert calculate_all_win_probability("S", [], sections={}, applicants={}) == {
        "section_probabilities": {}, "first_round_all_win_probability": 1.0,
        "first_round_failure_risk": 0.0,
    }


@pytest.mark.parametrize("baseline,current,threshold,expected", [
    (0.8, 0.5, 0.15, True),
    (0.8, 0.7, 0.15, False),
    (0.75, 0.5, 0.25, True),
    (0.149, 0.0, 0.15, False),
    (0.5, 0.5, 0.15, False),
    (0.5, 0.75, 0.15, False),
    # Explicitly documents the user's no-tolerance policy.
    (0.3, 0.2, 0.1, False),
])
def test_alert_threshold_without_tolerance(baseline, current, threshold, expected):
    result = should_alert({"A": baseline}, {"A": current}, threshold=threshold)
    assert result["should_alert"] is expected
    assert result["details"]["A"]["triggered"] is expected
    assert result["details"]["A"]["drop"] == pytest.approx(baseline - current)
    assert result["triggered_section_ids"] == (["A"] if expected else [])


def test_alert_uses_unchanged_baseline_for_cumulative_drop():
    baseline = {"A": 0.8}
    assert not should_alert(baseline, {"A": 0.7})["should_alert"]
    assert should_alert(baseline, {"A": 0.6})["should_alert"]
    assert baseline == {"A": 0.8}


def test_alert_preserves_all_details_and_sorts_triggers():
    baseline = {"Z": 0.8, "B": 0.2, "A": 0.9}
    current = {"Z": 0.5, "B": 0.7, "A": 0.5}
    before = deepcopy((baseline, current))
    result = should_alert(baseline, current)
    assert result["triggered_section_ids"] == ["A", "Z"]
    assert list(result["details"]) == ["A", "B", "Z"]
    assert result["details"]["B"]["drop"] == pytest.approx(-0.5)
    assert (baseline, current) == before


def test_empty_alert():
    assert should_alert({}, {}) == {
        "threshold": 0.15, "should_alert": False,
        "triggered_section_ids": [], "details": {},
    }


@pytest.mark.parametrize("value", [True, "0.5", float("nan"), float("inf"), -0.1, 1.1])
@pytest.mark.parametrize("field", ["baseline", "current"])
def test_rejects_invalid_probabilities(value, field):
    baseline, current = {"A": 0.8}, {"A": 0.5}
    (baseline if field == "baseline" else current)["A"] = value
    with pytest.raises(ValueError):
        should_alert(baseline, current)


@pytest.mark.parametrize("threshold", [0, -0.1, 1.1, True, "0.15", float("nan"), float("inf")])
def test_rejects_invalid_threshold(threshold):
    with pytest.raises(ValueError):
        should_alert({"A": 0.8}, {"A": 0.5}, threshold=threshold)


@pytest.mark.parametrize("current", [{}, {"A": 0.5, "B": 0.3}])
def test_rejects_mismatched_section_ids(current):
    with pytest.raises(ValueError):
        should_alert({"A": 0.8}, current)


@pytest.mark.parametrize("capacity", [-1, 1.5, True])
def test_rejects_invalid_capacity(capacity):
    with pytest.raises(ValueError):
        calculate_all_win_probability("S", ["A"], sections={"A": {"capacity": capacity}}, applicants={"A": set()})


def test_rejects_duplicate_sections():
    with pytest.raises(ValueError):
        calculate_all_win_probability("S", ["A", "A"], sections={"A": {"capacity": 1}}, applicants={"A": set()})


def test_rejects_missing_applicant_data():
    with pytest.raises(ValueError):
        calculate_all_win_probability("S", ["A"], sections={"A": {"capacity": 1}}, applicants={})
