def preference(section_ids: list, student: dict, sections: dict,
               *, total_weeks: int, days_per_week: int,
               periods_per_day: int, section_masks: dict[str, int], default_course_score,
               course_weight, time_weight, default_early_penalty) -> dict:
    """Score a timetable against the student's preferences; higher is better.

    No validation here; verify_parameters is expected to have run first.
    """

    # An empty plan is legal; return zeros instead of dividing by zero below.
    if not section_ids:
        return {
            "total": 0.0,
            "details": {
                "course_preference": 0.0,
                "total_early_days": 0,
                "average_early_days_per_week": 0.0,
                "time_score": 0.0,
            },
        }

    preferences = student.get("preferences", {})
    course_score_map = preferences.get("course_scores", {})

    early_penalty = preferences.get(
        "early_penalty_per_week",
        default_early_penalty,
    )
    course_ids = []

    for selected_section in section_ids:
        course_ids.append(sections[selected_section]["course_id"])

    # Only optional courses express a preference; required ones are obligations.
    selected_optional_courses = set(course_ids) & set(student['optional_course_ids'])
    course_scores = 0.0

    for course_id in sorted(selected_optional_courses):
        course_scores += course_score_map.get(
            course_id,
            default_course_score,
        )

    if selected_optional_courses:
        course_scores /= len(selected_optional_courses)
    else:
        course_scores = 0.0

    # Period 1 of every teaching day, so a two-period early class is one early day.
    early_mask = 0

    for day in range(days_per_week * total_weeks):
        early_mask |= 1 << (day * periods_per_day)

    taken_mask = 0

    for section_id in section_ids:
        taken_mask |= section_masks[section_id]

    # Whole-semester early days, not credits and not periods per week.
    early_num = (taken_mask & early_mask).bit_count()
    average_early_days = early_num / total_weeks

    # Clamped so a heavy early schedule cannot score below zero.
    total_weight = course_weight + time_weight
    early_score = max(0, 100 - average_early_days * early_penalty)
    total_score = (
            course_scores * course_weight / total_weight
            + early_score * time_weight / total_weight
    )

    return {
        "total": total_score,
        "details": {
            "course_preference": course_scores,
            "total_early_days": early_num,
            "average_early_days_per_week": average_early_days,
            "time_score": early_score,
        },
    }