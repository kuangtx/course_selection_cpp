"""Test the agreed optional-only preference policy and score details."""

from copy import deepcopy

import pytest

from backend.core.time_mask import build_mask


def test_empty_plan_returns_zero_total_and_details(make_student, score_plan):
    result = score_plan([], make_student())
    assert result == {
        "total": 0.0,
        "details": {
            "course_preference": 0.0,
            "total_early_days": 0,
            "average_early_days_per_week": 0.0,
            "time_score": 0.0,
        },
    }


def test_missing_preferences_use_default_values(make_student, score_plan):
    result = score_plan(["ART_A"], make_student(optional=["ART"], target=1))
    assert result["total"] == pytest.approx(83)
    assert result["details"] == {
        "course_preference": 80.0,
        "total_early_days": 18,
        "average_early_days_per_week": 1.0,
        "time_score": 90.0,
    }


def test_missing_one_course_score_uses_default(make_student, score_plan):
    student = make_student(optional=["ART", "HISTORY"], target=2,
                           preferences={"course_scores": {"ART": 100}})
    result = score_plan(["ART_A", "HISTORY_A"], student)
    assert result["details"]["course_preference"] == pytest.approx(90)
    assert result["total"] == pytest.approx(90)


def test_explicit_zero_course_score_is_not_replaced(make_student, score_plan):
    student = make_student(optional=["HISTORY"], target=1,
                           preferences={"course_scores": {"HISTORY": 0}})
    result = score_plan(["HISTORY_A"], student)
    assert result["details"]["course_preference"] == 0
    assert result["total"] == pytest.approx(30)


@pytest.mark.parametrize("penalty,time_score,total", [
    (0, 100, 86), (20, 80, 80), (200, 0, 56),
])
def test_student_early_penalty_overrides_default(make_student, score_plan, penalty, time_score, total):
    student = make_student(optional=["ART"], target=1,
                           preferences={"early_penalty_per_week": penalty})
    result = score_plan(["ART_A"], student)
    assert result["details"]["time_score"] == pytest.approx(time_score)
    assert result["total"] == pytest.approx(total)


def test_custom_defaults_and_weights_are_used(make_student, score_plan):
    result = score_plan(["ART_A"], make_student(optional=["ART"], target=1),
                        default_course_score=60, default_early_penalty=20,
                        course_weight=0.5, time_weight=0.5)
    assert result["details"]["course_preference"] == 60
    assert result["details"]["time_score"] == 80
    assert result["total"] == pytest.approx(70)


def test_no_early_classes_receive_full_time_score(make_student, score_plan):
    result = score_plan(["HISTORY_A"], make_student(optional=["HISTORY"], target=1))
    assert result["details"]["total_early_days"] == 0
    assert result["details"]["time_score"] == 100
    assert result["total"] == pytest.approx(86)


def test_two_consecutive_periods_count_as_one_early_day(make_student, score_plan):
    result = score_plan(["ART_A"], make_student(optional=["ART"], target=1))
    assert result["details"]["total_early_days"] == 18


def test_two_early_days_each_week_are_counted(make_student, score_plan):
    student = make_student(optional=["ART", "MUSIC"], target=2)
    result = score_plan(["ART_A", "MUSIC_A"], student)
    assert result["details"]["total_early_days"] == 36
    assert result["details"]["average_early_days_per_week"] == 2
    assert result["details"]["time_score"] == 80


def test_odd_week_classes_are_averaged_over_whole_semester(make_student, score_plan, calendar_config):
    masks = {"ART_A": build_mask([
        {"weeks": list(range(1, 19, 2)), "day": 1, "start": 1, "length": 2}
    ], **calendar_config)}
    result = score_plan(["ART_A"], make_student(optional=["ART"], target=1), section_masks=masks)
    assert result["details"]["total_early_days"] == 9
    assert result["details"]["average_early_days_per_week"] == 0.5
    assert result["total"] == pytest.approx(84.5)


def test_required_courses_affect_time_but_not_optional_preference(make_student, score_plan):
    student = make_student(required=["MATH"], optional=["HISTORY"], target=1,
                           preferences={"course_scores": {"MATH": 0, "HISTORY": 90}})
    result = score_plan(["MATH_A", "HISTORY_A"], student)
    assert result["details"]["course_preference"] == 90
    assert result["details"]["total_early_days"] == 18
    assert result["total"] == pytest.approx(90)


def test_required_only_plan_does_not_divide_by_zero(make_student, score_plan):
    result = score_plan(["MATH_A"], make_student(required=["MATH"]))
    assert result["details"]["course_preference"] == 0
    assert result["total"] == pytest.approx(27)


def test_configurable_calendar_counts_sunday_period_one(make_student, score_plan):
    config = {"total_weeks": 2, "days_per_week": 7, "periods_per_day": 13}
    mask = build_mask([{"weeks": [1, 2], "day": 7, "start": 1, "length": 2}], **config)
    result = score_plan(["ART_A"], make_student(optional=["ART"], target=1),
                        section_masks={"ART_A": mask}, **config)
    assert result["details"]["total_early_days"] == 2
    assert result["total"] == pytest.approx(83)


def test_scoring_is_order_independent_and_does_not_mutate_inputs(make_student, score_plan, catalog):
    student = make_student(optional=["ART", "HISTORY"], target=2)
    plan = ["ART_A", "HISTORY_A"]
    before = deepcopy((student, plan, catalog))
    assert score_plan(plan, student) == score_plan(list(reversed(plan)), student)
    assert (student, plan, catalog) == before
