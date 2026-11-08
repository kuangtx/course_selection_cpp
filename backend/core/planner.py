"""Drop-in planner adapter backed by the compiled ``_planner`` extension."""

from ._planner import (
    Calendar as _Calendar,
    Course as _Course,
    Scoring as _Scoring,
    SearchOptions as _SearchOptions,
    Section as _Section,
    Student as _Student,
    plan_courses as _plan_courses,
)
from .verify_parameters import verify_parameters


def planner(student: dict, courses: dict, sections: dict, *,
            section_masks: dict[str, int], fixed_section_ids: list[str],
            allowed_section_ids: set[str] | None, excluded_section_ids: set[str],
            allow_partial: bool, candidate_limit: int, max_search_nodes: int,
            total_weeks: int, days_per_week: int, periods_per_day: int,
            default_course_score: int, course_weight: float, time_weight: float,
            default_early_penalty) -> dict:
    """Preserve the Python planner API while running its search in C++."""
    verify_parameters(
        student, courses, sections,
        section_masks=section_masks,
        fixed_section_ids=fixed_section_ids,
        allowed_section_ids=allowed_section_ids,
        excluded_section_ids=excluded_section_ids,
        allow_partial=allow_partial,
        candidate_limit=candidate_limit,
        max_search_nodes=max_search_nodes,
    )

    # Keep the public dictionary API stable across the native boundary.
    native_student = _Student()
    native_student.id = student.get("id", "")
    native_student.required_course_ids = student["required_course_ids"]
    native_student.optional_course_ids = student["optional_course_ids"]
    native_student.optional_mode = student["optional_requirement"]["mode"]
    native_student.optional_target = float(student["optional_requirement"]["target"])
    preferences = student.get("preferences", {})
    native_student.course_scores = preferences.get("course_scores", {})
    native_student.early_penalty_per_week = float(
        preferences.get("early_penalty_per_week", default_early_penalty)
    )

    native_courses = {}
    for course_id, record in courses.items():
        course = _Course()
        course.id = course_id
        course.credits = float(record["credits"])
        native_courses[course_id] = course

    native_sections = {}
    for section_id, record in sections.items():
        native_sections[section_id] = _Section(
            section_id,
            record["course_id"],
            int(record["capacity"]),
            int(section_masks[section_id]),
        )

    calendar = _Calendar()
    calendar.total_weeks = total_weeks
    calendar.days_per_week = days_per_week
    calendar.periods_per_day = periods_per_day

    scoring = _Scoring()
    scoring.default_course_score = float(default_course_score)
    scoring.course_weight = float(course_weight)
    scoring.time_weight = float(time_weight)
    scoring.default_early_penalty = float(default_early_penalty)

    options = _SearchOptions()
    options.fixed_section_ids = fixed_section_ids
    options.use_allowed_whitelist = allowed_section_ids is not None
    options.allowed_section_ids = allowed_section_ids or set()
    options.excluded_section_ids = excluded_section_ids
    options.allow_partial = allow_partial
    options.candidate_limit = candidate_limit
    options.max_search_nodes = max_search_nodes

    # Only search runs in C++; risk and fallback orchestration stay in Python.
    result = _plan_courses(
        native_student, native_courses, native_sections,
        calendar, scoring, options,
    )

    plans = []
    for native_plan in result.plans:
        score = native_plan.preference_score
        score_details = {
            "course_preference": score.course_preference,
            "total_early_days": score.total_early_days,
            "average_early_days_per_week": score.average_early_days_per_week,
            "time_score": score.time_score,
        }
        score_total = score.total
        # The legacy Python scorer defines an empty timetable's score as zero.
        if not native_plan.section_ids:
            score_total = 0.0
            score_details = {
                "course_preference": 0.0,
                "total_early_days": 0,
                "average_early_days_per_week": 0.0,
                "time_score": 0.0,
            }
        plans.append({
            "section_ids": list(native_plan.section_ids),
            "preference_score": {
                "total": score_total,
                "details": score_details,
            },
            "is_complete": native_plan.is_complete,
            "unmet_requirements": {
                "required_course_ids": sorted(native_plan.unmet_required_course_ids),
                "optional": {
                    "mode": native_plan.optional.mode,
                    "target": native_plan.optional.target,
                    "achieved": native_plan.optional.achieved,
                    "gap": native_plan.optional.gap,
                },
            },
        })

    return {
        "search_status": result.search_status,
        "searched_nodes": result.searched_nodes,
        "plans": plans,
    }
