"""T01-T04 and calendar boundary tests; preserve the existing mask test."""

import pytest

from backend.core.time_mask import build_mask


def meeting(weeks, day=1, start=1, length=2):
    return {"weeks": weeks, "day": day, "start": start, "length": length}


@pytest.mark.parametrize("left,right,conflicts", [
    (list(range(1, 19, 2)), list(range(2, 19, 2)), False),
    (list(range(1, 9)), list(range(9, 17)), False),
    ([1, 2], [2, 3], True),
], ids=["T01-odd-even", "T02-disjoint-terms", "T03-common-week"])
def test_actual_teaching_weeks_determine_conflicts(calendar_config, left, right, conflicts):
    first = build_mask([meeting(left)], **calendar_config)
    second = build_mask([meeting(right)], **calendar_config)
    assert bool(first & second) is conflicts


def test_adjacent_periods_do_not_conflict(calendar_config):
    first = build_mask([meeting([1], start=1)], **calendar_config)
    second = build_mask([meeting([1], start=3)], **calendar_config)
    assert first & second == 0


def test_multiple_meetings_have_exact_bit_positions(calendar_config):
    mask = build_mask([meeting([1, 2]), meeting([1], day=3, start=5)], **calendar_config)
    expected = sum(1 << position for position in [0, 1, 60, 61, 28, 29])
    assert mask == expected
    assert mask.bit_count() == 6


def test_last_period_of_semester(calendar_config):
    mask = build_mask([meeting([18], day=5, start=12, length=1)], **calendar_config)
    assert mask == 1 << 1079


@pytest.mark.parametrize("changes", [
    {"weeks": [0]}, {"weeks": [19]}, {"weeks": [True]},
    {"weeks": [1.5]}, {"weeks": []}, {"weeks": "1"},
    {"day": 0}, {"day": 6}, {"day": True},
    {"start": 0}, {"start": 13}, {"start": 1.5},
    {"length": 0}, {"length": -1}, {"length": True},
    {"start": 12, "length": 2},
])
def test_invalid_time_block_is_rejected(calendar_config, changes):
    block = meeting([1])
    block.update(changes)
    with pytest.raises(ValueError):
        build_mask([block], **calendar_config)


@pytest.mark.parametrize("blocks", [
    [meeting([1, 1])],
    [meeting([1]), meeting([1])],
    [meeting([1], start=1), meeting([1], start=2)],
])
def test_duplicate_or_overlapping_meetings_are_rejected(calendar_config, blocks):
    with pytest.raises(ValueError, match="overlapping"):
        build_mask(blocks, **calendar_config)


@pytest.mark.parametrize("name,value", [
    ("total_weeks", 0), ("total_weeks", True),
    ("days_per_week", -1), ("periods_per_day", 12.5),
])
def test_invalid_calendar_is_rejected(calendar_config, name, value):
    calendar_config[name] = value
    with pytest.raises(ValueError):
        build_mask([meeting([1])], **calendar_config)
