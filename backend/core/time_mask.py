def build_mask(meetings: list[dict], *, total_weeks: int, days_per_week: int, periods_per_day: int) -> int:
    """Convert a section's meetings into a full-semester time mask."""

    # type(x) is int rejects bool and numpy integers on purpose.
    for name, value in (("total_weeks", total_weeks), ("days_per_week", days_per_week), ("periods_per_day", periods_per_day)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")

    periods_per_week = days_per_week * periods_per_day
    section_mask = 0

    for meeting in meetings:
        weeks = meeting["weeks"]
        day = meeting["day"]
        start = meeting["start"]
        length = meeting["length"]

        # Validate numeric types before checking ranges.
        for name, value in (("day", day), ("start", start), ("length", length)):
            if type(value) is not int:
                raise ValueError(f"{name} must be an integer")

        # Validate the meeting day.
        if not 1 <= day <= days_per_week:
            raise ValueError(f"Day must be between 1 and {days_per_week}")

        # Validate the starting period.
        if not 1 <= start <= periods_per_day:
            raise ValueError(
                f"Starting period must be between 1 and {periods_per_day}"
            )

        # Validate the duration.
        if length < 1 or start + length - 1 > periods_per_day:
            raise ValueError(f"Duration must be positive, and the ending period must not exceed {periods_per_day}")

        # The week list is what makes single/double-week schedules expressible.
        if not isinstance(weeks, list) or not weeks:
            raise ValueError("Weeks must be a non-empty list")

        # Build a time block for each teaching week.
        for week in weeks:
            if type(week) is not int or not 1 <= week <= total_weeks:
                raise ValueError(f"Week must be an integer between 1 and {total_weeks}")

            # 0-based slot index of the block's first period.
            base = (week - 1) * periods_per_week + (day - 1) * periods_per_day + start - 1
            block_mask = ((1 << length) - 1) << base

            # Reject duplicate or overlapping blocks within the section.
            if section_mask & block_mask:
                raise ValueError(f"Duplicate or overlapping meeting times within the section: week {week}, day {day}")

            # Merge the block into the section's time mask.
            section_mask |= block_mask

    return section_mask