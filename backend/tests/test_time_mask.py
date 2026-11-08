from backend.core.time_mask import build_mask

def test_building_mask_with_seven_days_and_thirteen_periods():
    meetings = [
        {"weeks": [1, 2], "day": 7, "start": 12, "length": 2}
    ]

    mask = build_mask(
        meetings,
        total_weeks=18,
        days_per_week=7,
        periods_per_day=13,
    )

    # Week 1: bit positions 89 and 90.
    # Week 2: bit positions 180 and 181.
    expected_mask = (
            (1 << 89)
            | (1 << 90)
            | (1 << 180)
            | (1 << 181)
    )

    assert mask == expected_mask
    assert mask.bit_count() == 4