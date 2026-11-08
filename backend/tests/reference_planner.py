from backend.core.preference import preference
from backend.core.verify_parameters import verify_parameters


def planner(student: dict, courses: dict,
            sections: dict, *,
            section_masks: dict[str, int], fixed_section_ids: list[str],
            allowed_section_ids: set[str] | None, excluded_section_ids: set[str],
            allow_partial: bool, candidate_limit: int,
            max_search_nodes: int, total_weeks: int,
            days_per_week: int, periods_per_day: int,
            default_course_score: int, course_weight: float,
            time_weight: float, default_early_penalty) -> dict:
    """Backtracking search for conflict-free timetables; returns ranked plans.

    LIMIT_REACHED means the node budget ran out, not that no plan exists.
    INFEASIBLE may still carry partial plans, so check is_complete rather than
    whether plans is empty.
    """

    verify_parameters(student, courses, sections,
                      section_masks=section_masks, fixed_section_ids=fixed_section_ids, allowed_section_ids=allowed_section_ids,
                      excluded_section_ids=excluded_section_ids, allow_partial=allow_partial, candidate_limit=candidate_limit,
                      max_search_nodes=max_search_nodes)
    searched_nodes = 0
    limit_reached = False
    plans = []
    selected = []
    remaining_required_courses = student['required_course_ids']
    remaining_optional_courses = student['optional_course_ids']
    need_course_ids = set(remaining_required_courses) | set(remaining_optional_courses)
    sections_by_course = {}
    fixed_taken_mask = 0
    optional_achieved = 0
    mode = student["optional_requirement"]["mode"]
    target = student["optional_requirement"]["target"]
    fixed_course_ids = set()
    optional_course_ids = set(student["optional_course_ids"])

    # verify_parameters only checked structure; these confirm the pinned
    # sections are consistent with this student.
    for section_id in fixed_section_ids:
        if section_id not in sections:
            raise ValueError(f"Unknown fixed section: {section_id}")

        course_id = sections[section_id]["course_id"]

        if course_id not in need_course_ids:
            raise ValueError(f"Fixed course is outside student requirements: {course_id}")

        if section_id in excluded_section_ids:
            raise ValueError(f"Fixed section is excluded: {section_id}")

        if course_id in fixed_course_ids:
            raise ValueError(f"Duplicate fixed course: {course_id}")

        mask = section_masks[section_id]

        if mask & fixed_taken_mask:
            raise ValueError(f"Fixed section has a time conflict: {section_id}")

        fixed_taken_mask |= mask
        selected.append(section_id)
        fixed_course_ids.add(course_id)

        # An already-won elective counts toward the target and is not re-taken.
        if course_id in optional_course_ids:
            optional_achieved += (1 if mode == "count" else courses[course_id]["credits"])

    remaining_required_courses = [
        course_id
        for course_id in student["required_course_ids"]
        if course_id not in fixed_course_ids
    ]

    remaining_optional_courses = [
        course_id
        for course_id in student["optional_course_ids"]
        if course_id not in fixed_course_ids
    ]

    need_course_ids = set(remaining_required_courses) | set(remaining_optional_courses)

    # Sections are sorted by ID so the attempt order never depends on dict
    # insertion order, which keeps repeated calls reproducible.
    for course_id in sorted(need_course_ids):
        matched_sections = []

        for section_id, section in sections.items():
            if section['course_id'] != course_id:
                continue

            # The whitelist restricts new choices only; pinned sections bypass
            # it, so an empty set means "keep the pins, add nothing".
            if allowed_section_ids is not None:
                if section_id not in allowed_section_ids:
                    continue

            if section_id in excluded_section_ids:
                continue

            matched_sections.append(section_id)

        sections_by_course[course_id] = sorted(matched_sections)

    def enter_node():
        nonlocal searched_nodes, limit_reached

        # A negative budget means unlimited.
        if searched_nodes >= max_search_nodes >= 0:
            limit_reached = True
            return False

        searched_nodes += 1
        return True

    def save_plan():
        unmet_requirements = calculate_gaps(selected)

        result = {
            # Copy: `selected` keeps being mutated by backtracking.
            "section_ids": selected.copy(),
            "preference_score": preference(selected, student, sections,
                                           total_weeks=total_weeks, periods_per_day=periods_per_day,
                                           days_per_week=days_per_week, section_masks=section_masks,
                                           default_course_score=default_course_score,course_weight=course_weight,
                                           time_weight=time_weight, default_early_penalty=default_early_penalty),
            "is_complete": (
                    not unmet_requirements["required_course_ids"]
                    and unmet_requirements["optional"]["gap"] == 0
            ),
            "unmet_requirements": unmet_requirements,
        }

        plans.append(result)
        rank_plan()

        # The pool stays sorted, so the last entry is the worst one.
        if len(plans) > candidate_limit >= 0:
            plans.pop()

    def search_required(index: int, taken_mask: int):
        if not enter_node():
            return

        if index == len(remaining_required_courses):
            search_optional(0, taken_mask, optional_achieved)

            return

        # taken_mask is passed by value, so backtracking needs no cleanup.
        for section_id in sections_by_course[remaining_required_courses[index]]:
            if section_masks[section_id] & taken_mask:
                continue

            selected.append(section_id)
            search_required(index + 1, taken_mask | section_masks[section_id])
            selected.pop()

            if limit_reached:
                return

        # Skipping a required course is only explored for partial plans.
        if allow_partial:
            search_required(index + 1, taken_mask)

        return

    def search_optional(index: int, taken_mask: int, optional_achieved: int):
        if not enter_node():
            return

        # Stop once satisfied; overshooting the target in credit mode is fine.
        if optional_achieved >= target:
            save_plan()

            return

        if index == len(remaining_optional_courses):
            if allow_partial:
                save_plan()

            return

        course_id = remaining_optional_courses[index]
        increment = 1 if mode == "count" else courses[course_id]["credits"]

        for section_id in sections_by_course[course_id]:
            if section_masks[section_id] & taken_mask:
                continue

            selected.append(section_id)
            optional_achieved += increment
            search_optional(index + 1, taken_mask | section_masks[section_id], optional_achieved)
            selected.pop()
            optional_achieved -= increment

            if limit_reached:
                return

        # Branch taking no section of this course.  Explored even when partial
        # plans are off: the target may still be reachable later in the list.
        search_optional(index + 1, taken_mask, optional_achieved)

        return

    def calculate_gaps(section_ids):
        # Accounting happens at course level, not section level.
        selected_course_ids = {
            sections[section_id]["course_id"]
            for section_id in section_ids
        }

        missing_required_ids = sorted(
            set(student["required_course_ids"]) - selected_course_ids
        )

        # A required course never counts toward the optional target.
        selected_optional_ids = (
                optional_course_ids & selected_course_ids
        )

        if mode == "count":
            achieved = len(selected_optional_ids)
        else:
            achieved = sum(
                courses[course_id]["credits"]
                for course_id in sorted(selected_optional_ids)
            )

        return {
            "required_course_ids": missing_required_ids,
            "optional": {
                "mode": mode,
                "target": target,
                "achieved": achieved,
                "gap": max(0, target - achieved),
            },
        }

    def rank_plan():
        if len(plans) <= 1:
            return

        # Completion outranks preference, so a thin timetable with no early
        # classes can never beat a complete one.
        plans.sort(
            key=lambda p: (
                len(p["unmet_requirements"]["required_course_ids"]),
                p["unmet_requirements"]["optional"]["gap"],
                -p["preference_score"]["total"],
                tuple(sorted(p["section_ids"])),
            )
        )

    search_required(0, fixed_taken_mask)

    has_complete = any(p["is_complete"] for p in plans)

    if limit_reached:
        search_status = "LIMIT_REACHED"
    elif has_complete:
        search_status = "FOUND"
    else:
        search_status = "INFEASIBLE"

    return {
        "search_status": search_status,
        "searched_nodes": searched_nodes,
        "plans": plans,
    }
