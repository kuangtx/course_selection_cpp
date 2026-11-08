from math import isfinite


def verify_parameters(student: dict, courses: dict,
                      sections: dict, *,
                      section_masks: dict[str, int], fixed_section_ids: list[str],
                      allowed_section_ids: set[str] | None, excluded_section_ids: set[str],
                      allow_partial: bool, candidate_limit: int,
                      max_search_nodes: int):
    """Validate planner inputs structurally; raise ValueError, else return None.

    Whether the fixed sections fit this student (excluded, duplicated per
    course, in time conflict) is left to planner, which can name the offender.
    """

    # Validate top-level data containers.
    if not isinstance(student, dict):
        raise ValueError("student must be a dictionary")

    if not isinstance(courses, dict):
        raise ValueError("courses must be a dictionary")

    if not isinstance(sections, dict):
        raise ValueError("sections must be a dictionary")

    if not isinstance(section_masks, dict):
        raise ValueError("section_masks must be a dictionary")

    # Negative limits mean unlimited; zero is not allowed.
    for name, value in (
            ("candidate_limit", candidate_limit),
            ("max_search_nodes", max_search_nodes),
    ):
        if type(value) is not int or value == 0:
            raise ValueError(f"{name} must be a non-zero integer")

    if type(allow_partial) is not bool:
        raise ValueError("allow_partial must be a boolean")

    # Validate ID collections before performing set operations.
    def validate_ids(name, values, expected_type):
        if not isinstance(values, expected_type):
            raise ValueError(
                f"{name} must be a {expected_type.__name__}"
            )

        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError(f"{name} must contain non-empty string IDs")

        if len(values) != len(set(values)):
            raise ValueError(f"{name} must not contain duplicate IDs")

    required_ids = student.get("required_course_ids")
    optional_ids = student.get("optional_course_ids")

    # Lists preserve the student's ordering, which fixes the search order.
    validate_ids("required_course_ids", required_ids, list)
    validate_ids("optional_course_ids", optional_ids, list)
    validate_ids("fixed_section_ids", fixed_section_ids, list)
    validate_ids("excluded_section_ids", excluded_section_ids, set)

    # None means "no whitelist".
    if allowed_section_ids is not None:
        validate_ids("allowed_section_ids", allowed_section_ids, set)

    # A course in both sets would be counted twice toward the optional target.
    if set(required_ids) & set(optional_ids):
        raise ValueError("Required and optional courses must not overlap")

    # Validate course references.
    need_course_ids = set(required_ids) | set(optional_ids)

    for course_id in need_course_ids:
        if course_id not in courses:
            raise ValueError(f"Unknown course: {course_id}")

        if not isinstance(courses[course_id], dict):
            raise ValueError(f"Invalid course record: {course_id}")

    # Validate the optional requirement.
    requirement = student.get("optional_requirement")

    if not isinstance(requirement, dict):
        raise ValueError("optional_requirement must be a dictionary")

    mode = requirement.get("mode")
    target = requirement.get("target")

    if mode not in ("count", "credits"):
        raise ValueError("mode must be 'count' or 'credits'")

    def is_nonnegative_number(value):
        """Finite int or float >= 0; rejects bool, NaN and infinity."""

        if type(value) is int:
            return value >= 0

        if type(value) is float:
            return isfinite(value) and value >= 0

        return False

    if mode == "count":
        if type(target) is not int or target < 0:
            raise ValueError("Count target must be a non-negative integer")
    else:
        # Credits may be fractional, so floats are accepted in this mode.
        if not is_nonnegative_number(target):
            raise ValueError(
                "Credit target must be a finite non-negative number"
            )

        for course_id in optional_ids:
            credits = courses[course_id].get("credits")

            if not is_nonnegative_number(credits):
                raise ValueError(f"Invalid credits for course: {course_id}")

    # Validate explicitly referenced section IDs.
    referenced_section_ids = (
            set(fixed_section_ids) | excluded_section_ids
    )

    if allowed_section_ids is not None:
        referenced_section_ids |= allowed_section_ids

    for section_id in referenced_section_ids:
        if section_id not in sections:
            raise ValueError(f"Unknown section: {section_id}")

    # Validate section records and masks used by this search.
    fixed_ids = set(fixed_section_ids)

    for section_id, section in sections.items():
        if not isinstance(section_id, str) or not section_id:
            raise ValueError("Section IDs must be non-empty strings")

        if not isinstance(section, dict):
            raise ValueError(f"Invalid section record: {section_id}")

        course_id = section.get("course_id")

        if not isinstance(course_id, str) or course_id not in courses:
            raise ValueError(
                f"Invalid course reference for section: {section_id}"
            )

        is_candidate = (
                course_id in need_course_ids
                and (
                        allowed_section_ids is None
                        or section_id in allowed_section_ids
                )
                and section_id not in excluded_section_ids
        )

        # Only pinned sections and real candidates are read during the search,
        # so only those need a mask.
        if section_id in fixed_ids or is_candidate:
            mask = section_masks.get(section_id)

            if type(mask) is not int or mask < 0:
                raise ValueError(
                    f"Missing or invalid time mask for section: {section_id}"
                )