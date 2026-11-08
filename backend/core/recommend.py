def compare_plans(
        old_plan: dict,
        new_plan: dict,
        *,
        sections: dict,
        ) -> dict:
    old_courses = {}
    new_courses = {}

    for sid in old_plan['section_ids']:
        old_courses[sections[sid]['course_id']] = sid

    for sid in new_plan['section_ids']:
        new_courses[sections[sid]['course_id']] = sid

    old_course = set(old_courses)
    new_course = set(new_courses)
    changed = {
        course_id
        for course_id in old_course & new_course
        if old_courses[course_id] != new_courses[course_id]
    }
    added = new_course - old_course
    deleted = old_course - new_course
    changed_course_count = len(changed) + max(len(added), len(deleted))
    result = {'changed_course_count': changed_course_count, 'switched_sections': []}

    for changed_courses_id in sorted(changed):
        temp_switched_sections = {'course_id': changed_courses_id,
                                  'old_section_id': old_courses[changed_courses_id],
                                  'new_section_id': new_courses[changed_courses_id]}

        result['switched_sections'].append(temp_switched_sections)

    result['removed_course_ids'] = sorted(deleted)
    result['added_course_ids'] = sorted(added)

    return result

def recommend(
        student: dict,
        courses: dict,
        sections: dict,
        *,
        section_masks: dict[str, int],
        snapshot: dict,
        purpose: str,
        config: dict,
        limit: int = 3,
) -> dict:
    """Dispatch a recommendation request without modifying application state.

    Negative limit returns all retained candidates; zero is invalid.
    The service supplies a consistent snapshot and validated configuration.
    """
    if type(limit) is not int or limit == 0:
        raise ValueError("limit must be a non-zero integer")

    if purpose not in ("initial", "adjustment", "supplement"):
        raise ValueError(f"Unsupported recommendation purpose: {purpose}")

    for name, value in (
            ("student", student),
            ("courses", courses),
            ("sections", sections),
            ("section_masks", section_masks),
            ("snapshot", snapshot),
            ("config", config),
    ):
        if not isinstance(value, dict):
            raise ValueError(f"{name} must be a dictionary")

    for name in ("phase", "state_version", "plan_revision"):
        if name not in snapshot:
            raise ValueError(f"Missing snapshot field: {name}")

    expected_phase = "ROUND2_OPEN" if purpose == "supplement" else "ROUND1_OPEN"
    if snapshot["phase"] != expected_phase:
        raise ValueError(f"{purpose} recommendations require {expected_phase}")

    if purpose == "supplement":
        required_fields = {"enrolled_section_ids": list, "remaining": dict}
    else:
        required_fields = {"applicants": dict}
        if purpose == "adjustment":
            required_fields["current_application"] = list

    for name, expected_type in required_fields.items():
        if name not in snapshot:
            raise ValueError(f"Missing snapshot field: {name}")
        if not isinstance(snapshot[name], expected_type):
            raise ValueError(f"snapshot.{name} must be a {expected_type.__name__}")

    # Import on dispatch: adjustment imports compare_plans from this module.
    # Local imports keep that dependency from becoming an import cycle.
    if purpose == "initial":
        from .recommend_initial import _recommend_initial
        handler = _recommend_initial
    elif purpose == "adjustment":
        from .recommend_adjustment import _recommend_adjustment
        handler = _recommend_adjustment
    else:
        from .recommend_supplement import _recommend_supplement
        handler = _recommend_supplement

    return handler(
        student,
        courses,
        sections,
        section_masks=section_masks,
        snapshot=snapshot,
        config=config,
        limit=limit,
    )