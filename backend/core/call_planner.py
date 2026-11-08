from .planner import planner

def call_planner(
        student, courses, sections,
        section_masks, config, *,
        fixed, allowed, excluded,
        allow_partial, candidate_limit=None, max_search_nodes=None,
        ) -> dict:
    if candidate_limit is None:
        candidate_limit = config["search"]["candidate_limit"]

    if max_search_nodes is None:
        max_search_nodes = config["search"]["max_search_nodes"]

    term = config['term']
    preference = config['preference']

    return planner(
        student, courses,
        sections, section_masks=section_masks,
        fixed_section_ids=sorted(fixed), allowed_section_ids=None if allowed is None else set(allowed),
        excluded_section_ids=set(excluded), allow_partial=allow_partial,
        candidate_limit=candidate_limit, max_search_nodes=max_search_nodes,
        total_weeks=term['total_weeks'], days_per_week=term['days_per_week'],
        periods_per_day=term['periods_per_day'], default_course_score=preference['default_course_score'],
        course_weight=preference['course_weight'], time_weight=preference['time_weight'],
        default_early_penalty=preference['default_early_penalty']
        )