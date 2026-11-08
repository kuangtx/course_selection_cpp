from .call_planner import call_planner

def analyze_fallback(
        student: dict, plan: dict,
        courses: dict, sections: dict,
        *, section_masks: dict[str, int],
        config: dict
    ) -> dict:
    if not plan.get("is_complete"):
        raise ValueError("Fallback analysis requires a complete plan")

    covered = unknown = uncovered = 0
    section_ids = sorted(plan["section_ids"])
    count = len(section_ids)
    evaluated = 0
    searched_nodes = 0
    limited_scenarios = 0
    examples = []
    # 1. Validate configuration containers.
    if not isinstance(config, dict):
        raise ValueError("config must be a dictionary")

    if "fallback" not in config:
        raise ValueError("Missing config field: fallback")

    fallback_config = config["fallback"]

    if not isinstance(fallback_config, dict):
        raise ValueError("config.fallback must be a dictionary")

    # 2. Check required fields before accessing their values.
    required_fields = (
        "max_scenarios",
        "max_nodes_per_scenario",
        "max_total_nodes",
        "max_examples",
    )

    for name in required_fields:
        if name not in fallback_config:
            raise ValueError(f"Missing fallback config field: {name}")

    # 3. Validate search limits.
    # Positive: bounded. Negative: unlimited. Zero: invalid.
    for name in (
            "max_scenarios",
            "max_nodes_per_scenario",
            "max_total_nodes",
    ):
        value = fallback_config[name]

        if type(value) is not int or value == 0:
            raise ValueError(
                f"fallback.{name} must be a non-zero integer"
            )

    # Zero examples is allowed; a negative value means unlimited.
    if type(fallback_config["max_examples"]) is not int:
        raise ValueError("fallback.max_examples must be an integer")

    # 4. Read values after validation.
    max_scenarios = fallback_config["max_scenarios"]
    per_scenario_limit = fallback_config["max_nodes_per_scenario"]
    total_limit = fallback_config["max_total_nodes"]
    max_examples = fallback_config["max_examples"]

    for scenario in range(2 ** count - 1, -1, -1):
        if evaluated >= max_scenarios > 0:
            break

        if total_limit > 0:
            remaining_nodes = total_limit - searched_nodes

            if remaining_nodes <= 0:
                break

            if per_scenario_limit < 0:
                node_budget = remaining_nodes
            else:
                node_budget = min(per_scenario_limit, remaining_nodes)
        else:
            # A negative total limit means no cumulative node limit.
            node_budget = per_scenario_limit

        won_section_ids = []
        lost_section_ids = set()

        for index, section_id in enumerate(section_ids):
            if scenario & (1 << index):
                won_section_ids.append(section_id)
            else:
                lost_section_ids.add(section_id)

        allowed_section_ids = {
            sid
            for sid, section in sections.items()
            if section["capacity"] > 0
        }
        fixed_section_ids = won_section_ids
        excluded_section_ids = set(lost_section_ids)
        allow_partial = False

        if excluded_section_ids:
            search_result = call_planner(
                student, courses, sections,
                section_masks, config, fixed=fixed_section_ids,
                allowed=allowed_section_ids, excluded=excluded_section_ids, allow_partial=allow_partial, max_search_nodes=node_budget)

            has_complete = any(
                plan["is_complete"]
                for plan in search_result["plans"]
            )
            evaluated += 1
            searched_nodes += search_result["searched_nodes"]

            if search_result["search_status"] == "LIMIT_REACHED":
                limited_scenarios += 1

            if has_complete:
                covered += 1
            elif search_result["search_status"] == "LIMIT_REACHED":
                unknown += 1
            elif search_result["search_status"] == "INFEASIBLE":
                uncovered += 1
            else:
                raise ValueError("Planner search status is inconsistent with the returned plans")

            if has_complete and (
                    max_examples < 0 or len(examples) < max_examples
            ):
                complete_plan = next(
                    plan
                    for plan in search_result["plans"]
                    if plan["is_complete"]
                )

                won_set = set(won_section_ids)

                examples.append({
                    "won_section_ids": list(won_section_ids),
                    "lost_section_ids": sorted(lost_section_ids),
                    "completion_section_ids": list(complete_plan["section_ids"]),
                    "added_section_ids": [
                        sid
                        for sid in complete_plan["section_ids"]
                        if sid not in won_set
                    ],
                    "search_status": search_result["search_status"],
                })
        else:
            evaluated += 1
            covered += 1

    total = 2 ** len(section_ids)
    skipped_scenarios = total - evaluated

    # During the loop, unknown counts only searched but unresolved scenarios.
    # Add scenarios that were never evaluated exactly once here.
    unknown += skipped_scenarios

    limitations = [
        "Completion paths do not guarantee available seats in the second round."
    ]

    if unknown > 0:
        limitations.insert(0, f"{unknown} scenario(s) remain unresolved.")

    return {
        "total": total,
        "covered": covered,
        "uncovered": uncovered,
        "unknown": unknown,
        "coverage_lower_bound": covered / total,
        "coverage_upper_bound": (covered + unknown) / total,
        "evaluated": evaluated,
        "searched_nodes": searched_nodes,
        "limited_scenarios": limited_scenarios,
        "skipped_scenarios": skipped_scenarios,
        "examples": examples,
        "limitations": limitations,
    }