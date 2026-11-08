from .preference import preference
from .risk import calculate_all_win_probability
from .fallback import analyze_fallback


def evaluate_plan(
        student: dict, plan: dict, courses: dict, sections: dict,
        *, section_masks: dict[str, int], snapshot: dict, config: dict,
        recalculate_preference: bool = True,
) -> dict:
    """Evaluate a complete first-round plan using current data.

    The caller validates the catalog, student, snapshot and configuration.
    Only section_ids is required in plan.
    Always recalculate old application scores. Set recalculate_preference=False
    only for candidates produced by the current planner call.
    """
    section_ids = sorted(plan["section_ids"])
    course_ids = set()
    taken_mask = 0
    permitted = set(student["required_course_ids"]) | set(student["optional_course_ids"])
    for sid in section_ids:
        cid = sections[sid]["course_id"]
        if cid not in permitted or cid in course_ids:
            raise ValueError(f"Invalid or repeated course in plan: {cid}")
        if taken_mask & section_masks[sid]:
            raise ValueError(f"Time conflict in plan: {sid}")
        course_ids.add(cid)
        taken_mask |= section_masks[sid]

    required_missing = sorted(set(student["required_course_ids"]) - course_ids)
    optional_ids = course_ids & set(student["optional_course_ids"])
    requirement = student["optional_requirement"]
    mode, target = requirement["mode"], requirement["target"]
    if mode == "count":
        achieved = len(optional_ids)
    elif mode == "credits":
        achieved = sum(courses[cid]["credits"] for cid in sorted(optional_ids))
    else:
        raise ValueError("Unsupported optional requirement mode")
    gap = max(0, target - achieved)
    if required_missing or gap > 0:
        raise ValueError("Evaluation requires a complete plan")

    if recalculate_preference or "preference_score" not in plan:
        term = config["term"]
        scoring = config["preference"]
        preference_score = preference(
            section_ids, student, sections,
            section_masks=section_masks,
            total_weeks=term["total_weeks"],
            days_per_week=term["days_per_week"],
            periods_per_day=term["periods_per_day"],
            default_course_score=scoring["default_course_score"],
            course_weight=scoring["course_weight"],
            time_weight=scoring["time_weight"],
            default_early_penalty=scoring["default_early_penalty"],
        )
    else:
        preference_score = plan["preference_score"]
    evaluated = {
        **plan,
        "section_ids": section_ids,
        "preference_score": preference_score,
        "is_complete": True,
        "unmet_requirements": {
            "required_course_ids": required_missing,
            "optional": {"mode": mode, "target": target, "achieved": achieved, "gap": gap},
        },
    }
    risk = calculate_all_win_probability(
        student["id"], section_ids,
        sections=sections, applicants=snapshot["applicants"],
    )
    fallback = analyze_fallback(
        student, evaluated, courses, sections,
        section_masks=section_masks, config=config,
    )
    weights = config["ranking"]
    score = (
            weights["preference_weight"] * preference_score["total"] / 100
            + weights["risk_weight"] * risk["first_round_all_win_probability"]
            + weights["fallback_weight"] * fallback["coverage_lower_bound"]
    )
    return {
        **evaluated,
        "risk": risk,
        "fallback": fallback,
        "recommendation_score": score,
        "comparison": None,
        "new_section_ids": None,
        "explanations": [
            "Probabilities use current applications, not final application counts.",
            "Fallback paths do not guarantee available seats in round two.",
        ],
    }
