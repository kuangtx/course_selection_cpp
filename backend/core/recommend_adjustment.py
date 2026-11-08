from .call_planner import call_planner
from .evaluate_plan import evaluate_plan
from .recommend import compare_plans


def _recommend_adjustment(
        student: dict, courses: dict, sections: dict,
        *, section_masks: dict[str, int], snapshot: dict,
        config: dict, limit: int = 3,
) -> dict:
    if type(limit) is not int or limit == 0:
        raise ValueError("limit must be a non-zero integer")
    if snapshot["phase"] != "ROUND1_OPEN":
        raise ValueError("Adjustment requires ROUND1_OPEN")
    if snapshot.get("current_application") is None:
        raise ValueError("Adjustment requires a current application")

    # 1. Evaluate the current application.
    old_plan = evaluate_plan(
        student, {"section_ids": snapshot["current_application"]}, courses, sections,
        section_masks=section_masks, snapshot=snapshot, config=config,
        recalculate_preference=True,
    )
    old_key = tuple(old_plan["section_ids"])

    # 2. If a current section is oversubscribed, search one-course swaps for
    # those sections first and pin every other course to the current section.
    applicant_counts = snapshot["applicants"]
    crowded = [
        sid for sid in old_plan["section_ids"]
        if len(applicant_counts[sid]) > sections[sid]["capacity"]
    ]
    if crowded:
        candidate_plans = []
        searched_nodes = 0
        search_status = "FOUND"
        per_target_budget = max(1, config["search"]["max_search_nodes"] // len(crowded))
        per_target_limit = max(1, config["search"]["candidate_limit"] // len(crowded))
        for target_id in crowded:
            course_id = sections[target_id]["course_id"]
            fixed = set(old_plan["section_ids"]) - {target_id}
            alternatives = {
                sid for sid, section in sections.items()
                if section["course_id"] == course_id
                and sid != target_id
                and section["capacity"] > 0
                and len(applicant_counts[sid]) <= section["capacity"]
            }
            if not alternatives:
                continue
            result = call_planner(
                student, courses, sections, section_masks, config,
                fixed=fixed, allowed=fixed | alternatives,
                excluded={target_id}, allow_partial=False,
                candidate_limit=per_target_limit,
                max_search_nodes=per_target_budget,
            )
            candidate_plans.extend(result["plans"])
            searched_nodes += result["searched_nodes"]
            if result["search_status"] == "LIMIT_REACHED":
                search_status = "LIMIT_REACHED"
        search_result = {
            "plans": candidate_plans,
            "searched_nodes": searched_nodes,
            "search_status": search_status,
        }
    else:
        search_result = call_planner(
            student, courses, sections, section_masks, config,
            fixed=[],
            allowed={sid for sid, section in sections.items() if section["capacity"] > 0},
            excluded=set(), allow_partial=False,
        )

    # 3. Evaluate every distinct complete alternative found by the planner.
    seen = {old_key}
    plans = []
    for candidate in search_result["plans"]:
        key = tuple(sorted(candidate["section_ids"]))
        if not candidate["is_complete"] or key in seen:
            continue
        seen.add(key)
        new_plan = evaluate_plan(
            student, candidate, courses, sections,
            section_masks=section_masks, snapshot=snapshot, config=config,
            recalculate_preference=False,
        )
        improvement = new_plan["recommendation_score"] - old_plan["recommendation_score"]

        comparison = compare_plans(old_plan, new_plan, sections=sections)
        preference_delta = new_plan["preference_score"]["total"] - old_plan["preference_score"]["total"]
        comparison.update({
            "score_improvement": improvement,
            "preference_delta": preference_delta,
            "preference_loss": max(0.0, -preference_delta) / 100,
            "risk_improvement": (
                    old_plan["risk"]["first_round_failure_risk"]
                    - new_plan["risk"]["first_round_failure_risk"]
            ),
            "fallback_coverage_delta": (
                    new_plan["fallback"]["coverage_lower_bound"]
                    - old_plan["fallback"]["coverage_lower_bound"]
            ),
            "change_ratio": comparison["changed_course_count"] / max(
                1, len(old_plan["section_ids"]), len(new_plan["section_ids"])
            ),
        })
        new_plan["comparison"] = comparison
        if crowded:
            new_plan["explanations"].append(
                "Replaces one oversubscribed section and keeps the other selected sections unchanged."
            )
        else:
            new_plan["explanations"].append(
                "The overall score changes; first-round risk does not necessarily decrease."
            )
        plans.append(new_plan)

    # 4. Prefer fewer changes, then greater improvement.
    plans.sort(key=lambda plan: (
        plan["comparison"]["changed_course_count"],
        -plan["comparison"]["score_improvement"],
        -plan["preference_score"]["total"],
        tuple(plan["section_ids"]),
    ))
    selected = plans if limit < 0 else plans[:limit]

    # 5. Preserve search and fallback limitations.
    limitations = ["Results are limited to the generated candidate pool."]
    if search_result["search_status"] == "LIMIT_REACHED":
        limitations.append("Candidate search was limited; other alternatives may exist.")
    if any(plan["fallback"]["unknown"] > 0 for plan in [old_plan, *selected]):
        limitations.append(
            "Fallback coverage is not fully known; scores use confirmed lower bounds."
        )
    if not selected:
        limitations.append("No different complete alternative was found in the generated candidate pool.")

    return {
        "state_version": snapshot["state_version"],
        "plan_revision": snapshot["plan_revision"],
        "purpose": "adjustment",
        "search_status": search_result["search_status"],
        "searched_nodes": search_result["searched_nodes"],
        "decision": "SHOW_PLANS" if selected else "KEEP_CURRENT",
        "current_plan": old_plan,
        "plans": selected,
        "limitations": limitations,
    }
