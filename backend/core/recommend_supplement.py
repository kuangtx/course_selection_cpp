from .call_planner import call_planner


def _recommend_supplement(
        student: dict,
        courses: dict,
        sections: dict,
        *,
        section_masks: dict[str, int],
        snapshot: dict,
        config: dict,
        limit: int = 3,
) -> dict:
    """Recommend round-two additions while preserving enrolled sections.

    Negative limit returns all retained candidates. No seats are reserved.
    The caller provides a validated catalog and a consistent snapshot.
    """
    if type(limit) is not int or limit == 0:
        raise ValueError("limit must be a non-zero integer")

    if snapshot["phase"] != "ROUND2_OPEN":
        raise ValueError("Supplement recommendations require ROUND2_OPEN")

    enrolled = snapshot["enrolled_section_ids"]
    remaining = snapshot["remaining"]
    if not isinstance(remaining, dict):
        raise ValueError("snapshot.remaining must be a dictionary")

    # 1. Only new sections require available seats.
    allowed = set()
    for sid in sections:
        if sid not in remaining:
            raise ValueError(f"Missing remaining seats for section: {sid}")
        seats = remaining[sid]
        if type(seats) is not int or seats < 0:
            raise ValueError(f"Invalid remaining seats for section: {sid}")
        if seats > 0:
            allowed.add(sid)

    # 2. Preserve enrolled sections, including those with zero seats left.
    search_result = call_planner(
        student, courses, sections, section_masks, config,
        fixed=enrolled,
        allowed=allowed,
        excluded=set(),
        allow_partial=True,
    )

    # 3. Keep the planner's ordering and its partial plans.
    enrolled_set = set(enrolled)
    seen = set()
    plans = []
    for plan in search_result["plans"]:
        key = tuple(sorted(plan["section_ids"]))
        if key in seen:
            continue
        seen.add(key)
        new_section_ids = sorted(set(plan["section_ids"]) - enrolled_set)

        if not new_section_ids and plan["is_complete"]:
            explanation = "Enrolled sections already satisfy all requirements."
        elif not new_section_ids:
            explanation = "This result adds no sections and leaves requirements unmet."
        elif plan["is_complete"]:
            explanation = "This plan would meet all requirements if the additions succeed."
        else:
            explanation = "This partial plan adds sections but leaves requirements unmet."

        plans.append({
            **plan,
            "risk": None,
            "fallback": None,
            "recommendation_score": None,
            "comparison": None,
            "new_section_ids": new_section_ids,
            "explanations": [explanation],
        })

    # 4. Apply the display limit only after processing the candidates.
    selected = plans if limit < 0 else plans[:limit]
    limitations = [
        "Availability is based on the current snapshot; no seats are reserved.",
        "Submit additions individually and refresh the snapshot after each attempt.",
    ]
    if search_result["search_status"] == "LIMIT_REACHED":
        limitations.append(
            "Search reached its budget; missing a complete plan does not prove none exists."
        )

    return {
        "state_version": snapshot["state_version"],
        "plan_revision": snapshot["plan_revision"],
        "purpose": "supplement",
        "search_status": search_result["search_status"],
        "searched_nodes": search_result["searched_nodes"],
        "decision": "SHOW_PLANS" if selected else "NO_PLAN",
        "current_plan": None,
        "plans": selected,
        "limitations": limitations,
    }
