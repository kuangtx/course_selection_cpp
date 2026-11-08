from .alerts import create_or_update_alerts, save_probability_baselines

def submit_round1(state, student_id, section_ids, expected_plan_revision):
    data = state.data

    with data["lock"]:
        if data["phase"] != "ROUND1_OPEN":
            return {
                "ok": False,
                "code": "WRONG_PHASE",
                "message": "Round-one submissions are not allowed in the current phase.",
            }

        if student_id not in data["students"]:
            return {
                "ok": False,
                "code": "STUDENT_NOT_FOUND",
                "message": f"Student {student_id} does not exist.",
            }

        unknown_sections = sorted(set(section_ids) - set(data["sections"]))
        if unknown_sections:
            return {
                "ok": False,
                "code": "SECTION_NOT_FOUND",
                "message": f"Unknown sections: {', '.join(unknown_sections)}.",
            }

        current_revision = data["plan_revision"][student_id]
        if expected_plan_revision != current_revision:
            return {
                "ok": False,
                "code": "STALE_PLAN",
                "message": "The application has changed. Refresh before submitting again.",
            }

        validation_error = _validate_round1_plan(data, student_id, section_ids)
        if validation_error is not None:
            return validation_error

        old_section_ids = data["applications"].get(student_id, [])
        for section_id in old_section_ids:
            data["applicants"][section_id].discard(student_id)

        new_section_ids = list(section_ids)
        data["applications"][student_id] = new_section_ids
        for section_id in new_section_ids:
            data["applicants"][section_id].add(student_id)

        data["plan_revision"][student_id] += 1
        data["state_version"] += 1

        affected_section_ids = set(old_section_ids) | set(new_section_ids)
        save_probability_baselines(state, student_id)
        create_or_update_alerts(state, affected_section_ids)

        return {
            "ok": True,
            "state_version": data["state_version"],
            "plan_revision": data["plan_revision"][student_id],
            "section_ids": new_section_ids,
        }

def _validate_round1_plan(data, student_id, section_ids):
    student = data["students"][student_id]
    sections = data["sections"]
    selected_course_ids = [
        sections[section_id]["course_id"]
        for section_id in section_ids
    ]
    selected_courses = set(selected_course_ids)

    required_courses = set(student["required_course_ids"])
    missing_required = sorted(required_courses - selected_courses)
    if missing_required:
        return {
            "ok": False,
            "code": "INVALID_PLAN",
            "message": f"Missing required courses: {', '.join(missing_required)}.",
        }

    if len(selected_courses) != len(selected_course_ids):
        return {
            "ok": False,
            "code": "DUPLICATE_COURSE",
            "message": "Each course can have at most one selected section.",
        }

    permitted_courses = required_courses | set(student["optional_course_ids"])
    outside_courses = sorted(selected_courses - permitted_courses)
    if outside_courses:
        return {
            "ok": False,
            "code": "INVALID_PLAN",
            "message": f"Courses outside the allowed set: {', '.join(outside_courses)}.",
        }

    optional_courses = set(student["optional_course_ids"])
    selected_optional = selected_courses & optional_courses
    requirement = student["optional_requirement"]
    if requirement["mode"] == "count":
        achieved = len(selected_optional)
        unit = "course(s)"
    else:
        achieved = sum(
            data["courses"][course_id]["credits"]
            for course_id in selected_optional
        )
        unit = "credit(s)"

    if achieved < requirement["target"]:
        return {
            "ok": False,
            "code": "INVALID_PLAN",
            "message": (
                f"Optional requirement not met: {requirement['target']} {unit} required, "
                f"but only {achieved} {unit} selected."
            ),
        }

    taken_mask = 0
    for section_id in section_ids:
        section_mask = data["section_masks"][section_id]
        if section_mask & taken_mask:
            return {
                "ok": False,
                "code": "TIME_CONFLICT",
                "message": f"Section {section_id} conflicts with another section in the plan.",
            }
        taken_mask |= section_mask

    return None

def draw_round1(state, draw_priorities):
    data = state.data

    with data["lock"]:
        if data["phase"] in ("ROUND2_OPEN", "CLOSED"):
            return {
                "ok": True,
                "already_drawn": True,
                "state_version": data["state_version"],
                "enrollments": {
                    student_id: list(section_ids)
                    for student_id, section_ids in data["enrollments"].items()
                },
            }

        if data["phase"] != "ROUND1_OPEN":
            return {
                "ok": False,
                "code": "WRONG_PHASE",
                "message": "The first-round draw is not allowed in the current phase.",
            }

        winners_by_section = {}
        for section_id, section in data["sections"].items():
            applicants = data["applicants"][section_id]
            if len(applicants) <= section["capacity"]:
                winners_by_section[section_id] = sorted(applicants)
                continue

            section_priorities = draw_priorities.get(section_id, {})
            missing_priorities = sorted(applicants - set(section_priorities))
            if missing_priorities:
                return {
                    "ok": False,
                    "code": "INVALID_DRAW_PRIORITIES",
                    "message": (
                        f"Section {section_id} is missing draw priorities for: "
                        f"{', '.join(missing_priorities)}."
                    ),
                }

            ranked_applicants = sorted(
                applicants,
                key=lambda student_id: (
                    section_priorities[student_id],
                    student_id,
                ),
            )
            winners_by_section[section_id] = ranked_applicants[:section["capacity"]]

        data["phase"] = "DRAWING"
        enrollments = {}
        enrolled_students = {
            section_id: set()
            for section_id in data["sections"]
        }

        for section_id, winners in winners_by_section.items():
            enrolled_students[section_id] = set(winners)
            for student_id in winners:
                enrollments.setdefault(student_id, []).append(section_id)

        data["enrollments"] = enrollments
        data["enrolled_students"] = enrolled_students

        for alert in data["alerts"].values():
            if alert["status"] == "PENDING":
                alert["status"] = "EXPIRED"

        data["state_version"] += 1
        data["phase"] = "ROUND2_OPEN"

        return {
            "ok": True,
            "already_drawn": False,
            "state_version": data["state_version"],
            "enrollments": {
                student_id: list(section_ids)
                for student_id, section_ids in enrollments.items()
            },
            "remaining": {
                section_id: state.get_remaining(section_id)
                for section_id in data["sections"]
            },
        }

def submit_round2(state, student_id, section_id):
    data = state.data

    with data["lock"]:
        if data["phase"] != "ROUND2_OPEN":
            return {
                "ok": False,
                "code": "WRONG_PHASE",
                "message": "Round-two submissions are not allowed in the current phase.",
            }

        if student_id not in data["students"]:
            return {
                "ok": False,
                "code": "STUDENT_NOT_FOUND",
                "message": f"Student {student_id} does not exist.",
            }

        if section_id not in data["sections"]:
            return {
                "ok": False,
                "code": "SECTION_NOT_FOUND",
                "message": f"Section {section_id} does not exist.",
            }

        enrolled_section_ids = data["enrollments"].get(student_id, [])
        if section_id in enrolled_section_ids:
            return {
                "ok": True,
                "already_enrolled": True,
                "state_version": data["state_version"],
                "remaining": state.get_remaining(section_id),
                "message": "Already enrolled in this section; no additional seat was taken.",
            }

        course_id = data["sections"][section_id]["course_id"]
        enrolled_course_ids = {
            data["sections"][enrolled_id]["course_id"]
            for enrolled_id in enrolled_section_ids
        }
        if course_id in enrolled_course_ids:
            return {
                "ok": False,
                "code": "DUPLICATE_COURSE",
                "message": f"Already enrolled in another section of course {course_id}.",
            }

        student = data["students"][student_id]
        required_courses = set(student["required_course_ids"])
        optional_courses = set(student["optional_course_ids"])
        if course_id not in required_courses | optional_courses:
            return {
                "ok": False,
                "code": "INVALID_PLAN",
                "message": f"Course {course_id} is outside the student's allowed courses.",
            }

        if course_id in optional_courses:
            enrolled_optional = optional_courses & enrolled_course_ids
            requirement = student["optional_requirement"]
            if requirement["mode"] == "count":
                achieved = len(enrolled_optional)
            else:
                achieved = sum(
                    data["courses"][enrolled_course_id]["credits"]
                    for enrolled_course_id in enrolled_optional
                )

            if achieved >= requirement["target"]:
                return {
                    "ok": False,
                    "code": "INVALID_PLAN",
                    "message": "The optional requirement is already satisfied.",
                }

        section_mask = data["section_masks"][section_id]
        if section_mask & state.get_student_taken_mask(student_id):
            return {
                "ok": False,
                "code": "TIME_CONFLICT",
                "message": f"Section {section_id} conflicts with an enrolled course.",
            }

        if state.get_remaining(section_id) <= 0:
            return {
                "ok": False,
                "code": "NO_SEAT",
                "message": f"Section {section_id} has no seats left. Refresh and choose again.",
            }

        data["enrollments"].setdefault(student_id, []).append(section_id)
        data["enrolled_students"][section_id].add(student_id)
        data["plan_revision"][student_id] += 1
        data["state_version"] += 1

        return {
            "ok": True,
            "already_enrolled": False,
            "state_version": data["state_version"],
            "remaining": state.get_remaining(section_id),
            "enrolled_section_ids": list(data["enrollments"][student_id]),
        }


def withdraw_selection(state, student_id, expected_plan_revision, *, phase, section_ids=None):
    """Withdraw a student application or chosen enrollments atomically."""
    data = state.data
    with data["lock"]:
        if data["phase"] != phase or phase not in ("ROUND1_OPEN", "ROUND2_OPEN"):
            return dict(ok=False, code="WRONG_PHASE", message="Withdrawal is not allowed in this phase.")
        if student_id not in data["students"]:
            return dict(ok=False, code="STUDENT_NOT_FOUND", message="Student does not exist.")
        if expected_plan_revision != data["plan_revision"][student_id]:
            return dict(ok=False, code="STALE_PLAN", message="Selection changed. Refresh before withdrawing.")

        if phase == "ROUND1_OPEN":
            removed = list(data["applications"].get(student_id, []))
            if not removed:
                return dict(ok=True, already_withdrawn=True, state_version=data["state_version"])
            for sid in removed:
                data["applicants"][sid].discard(student_id)
            data["applications"].pop(student_id, None)
            data["probability_baselines"].pop(student_id, None)
            data["alert_cooldowns"].pop(student_id, None)
        else:
            removed = list(dict.fromkeys(section_ids or []))
            if not removed:
                return dict(ok=False, code="INVALID_REQUEST", message="Choose at least one enrolled section.")
            if any(sid not in data["sections"] for sid in removed):
                return dict(ok=False, code="SECTION_NOT_FOUND", message="Unknown section.")
            enrolled = data["enrollments"].get(student_id, [])
            if any(sid not in enrolled for sid in removed):
                return dict(ok=False, code="NOT_ENROLLED", message="Some selected sections are no longer enrolled.")
            removed_set = set(removed)
            data["enrollments"][student_id] = [sid for sid in enrolled if sid not in removed_set]
            for sid in removed:
                data["enrolled_students"][sid].discard(student_id)

        data["plan_revision"][student_id] += 1
        data["state_version"] += 1
        if phase == "ROUND1_OPEN":
            # Expires S001's old reminders and updates competitors' probabilities.
            create_or_update_alerts(state, set(removed))
        return dict(ok=True, withdrawn_section_ids=removed,
                    state_version=data["state_version"], plan_revision=data["plan_revision"][student_id])
