from .call_planner import call_planner
from .evaluate_plan import evaluate_plan

def _recommend_initial(
        student: dict,
        courses: dict,
        sections: dict,
        *,
        section_masks: dict[str, int],
        snapshot: dict,
        config: dict,
        limit: int = 3,
) -> dict:
    if type(limit) is not int or limit == 0:
        raise ValueError("limit must be a non-zero integer")

    allowed = {
        sid
        for sid, section in sections.items()
        if section['capacity'] > 0
    }
    search_result = call_planner(
        student, courses, sections,
        section_masks, config, fixed=[],
        allowed=allowed, excluded=set(), allow_partial=False,
    )
    seen = set()
    candidates = []

    for plan in search_result['plans']:
        if not plan['is_complete']:
            continue

        key = tuple(sorted(plan['section_ids']))

        if key not in seen:
            seen.add(key)
            candidates.append(plan)

    evaluated_plans = []
    for plan in candidates:
        evaluated_plans.append(evaluate_plan(
            student, plan, courses, sections,
            section_masks=section_masks,
            snapshot=snapshot,
            config=config,
            recalculate_preference=False,
        ))

    # 2. Sort by recommendation score, then preference score,
    #    then section IDs for deterministic ordering
    evaluated_plans.sort(
        key=lambda plan: (
            -plan['recommendation_score'],
            -plan['preference_score']['total'],
            tuple(sorted(plan['section_ids'])),
        )
    )

    # 3. Return at most 'limit' plans
    selected_plans = evaluated_plans if limit < 0 else evaluated_plans[:limit]

    # 4. Describe the limitations of this recommendation
    limitations = [
        'Recommendations are based on a limited candidate pool '
        'and are not guaranteed to be globally optimal.',
    ]

    if search_result['search_status'] == 'LIMIT_REACHED':
        limitations.append(
            'The candidate search reached its budget limit '
            'before completing the search. Finding no complete plan '
            'does not prove that none exists.'
        )

    if any(
            plan['fallback']['unknown'] > 0
            for plan in selected_plans
    ):
        limitations.append(
            'Some fallback scenarios remain unverified. '
            'See the fallback results for each recommended plan.'
        )

    # 5. Return the initial recommendation results
    return {
        'state_version': snapshot['state_version'],
        'plan_revision': snapshot['plan_revision'],
        'purpose': 'initial',
        'search_status': search_result['search_status'],
        'searched_nodes': search_result['searched_nodes'],
        'decision': 'SHOW_PLANS' if selected_plans else 'NO_PLAN',
        'current_plan': None,
        'plans': selected_plans,
        'limitations': limitations,
    }
