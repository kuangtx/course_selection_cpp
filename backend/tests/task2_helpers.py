"""Independent small fixtures shared by task-2 acceptance tests."""

from copy import deepcopy

import pytest

from backend.core.time_mask import build_mask


@pytest.fixture
def task2_case():
    term = {"total_weeks": 2, "days_per_week": 5, "periods_per_day": 12}
    courses = {cid: {"id": cid, "credits": credits} for cid, credits in (
        ("MATH", 4), ("PHYS", 4), ("ART", 2), ("HISTORY", 3),
    )}
    sections = {}
    for sid, cid, capacity, day, start in (
        ("MATH_A", "MATH", 4, 1, 1),
        ("MATH_B", "MATH", 20, 1, 3),
        ("PHYS_A", "PHYS", 4, 2, 3),
        ("PHYS_B", "PHYS", 20, 2, 5),
        ("ART_A", "ART", 4, 3, 3),
        ("HISTORY_A", "HISTORY", 20, 4, 3),
    ):
        sections[sid] = {
            "id": sid, "course_id": cid, "capacity": capacity,
            "meetings": [{"weeks": [1, 2], "day": day, "start": start, "length": 1}],
        }
    masks = {sid: build_mask(sec["meetings"], **term) for sid, sec in sections.items()}
    student = {
        "id": "S001", "required_course_ids": ["MATH", "PHYS"],
        "optional_course_ids": ["ART", "HISTORY"],
        "optional_requirement": {"mode": "count", "target": 1},
        "preferences": {"course_scores": {"ART": 90, "HISTORY": 70}},
    }
    config = {
        "term": term,
        "preference": {
            "default_course_score": 80, "course_weight": 0.7,
            "time_weight": 0.3, "default_early_penalty": 10,
        },
        "search": {"candidate_limit": 20, "max_search_nodes": 10000},
        "fallback": {
            "max_scenarios": 64, "max_total_nodes": 20000, "max_examples": 3,
            # The current implementation requires this key. -1 disables the
            # individual-scenario cap; only the cumulative budget applies.
            "max_nodes_per_scenario": -1,
        },
        "ranking": {"preference_weight": 0.5, "risk_weight": 0.3, "fallback_weight": 0.2},
        "adjustment": {"min_score_improvement": 0.02},
    }
    snapshot = {
        "phase": "ROUND1_OPEN", "state_version": 12, "plan_revision": 2,
        "current_application": ["MATH_A", "PHYS_A", "ART_A"],
        "enrolled_section_ids": [],
        "remaining": {sid: section["capacity"] for sid, section in sections.items()},
        "applicants": {
            sid: ({f"S{i:03d}" for i in range(1, 21)} if sid.endswith("_A") and sid != "HISTORY_A" else set())
            for sid in sections
        },
    }
    return {
        "student": student, "courses": courses, "sections": sections,
        "section_masks": masks, "snapshot": snapshot, "config": config,
    }


def call_recommend(case, **kwargs):
    from backend.core.recommend import recommend

    return recommend(**case, **kwargs)


def fallback_args(case, section_ids=None):
    return {
        "student": case["student"], "courses": case["courses"],
        "sections": case["sections"], "section_masks": case["section_masks"],
        "config": case["config"],
        "plan": {"section_ids": section_ids if section_ids is not None else list(case["snapshot"]["current_application"]), "is_complete": True},
    }


def two_required_case(case):
    result = deepcopy(case)
    result["student"]["optional_course_ids"] = []
    result["student"]["optional_requirement"]["target"] = 0
    result["snapshot"]["current_application"] = ["MATH_A", "PHYS_A"]
    return result
