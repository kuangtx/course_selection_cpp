"""Small, deterministic fixtures for the task-1 acceptance tests."""

import pytest

from backend.core.planner import planner
from backend.core.preference import preference
from backend.core.time_mask import build_mask


@pytest.fixture
def calendar_config():
    return {"total_weeks": 18, "days_per_week": 5, "periods_per_day": 12}


@pytest.fixture
def make_student():
    def make(required=(), optional=(), mode="count", target=0, preferences=None):
        result = {
            "id": "S001",
            "required_course_ids": list(required),
            "optional_course_ids": list(optional),
            "optional_requirement": {"mode": mode, "target": target},
        }
        if preferences is not None:
            result["preferences"] = preferences
        return result
    return make


@pytest.fixture
def catalog(calendar_config):
    courses = {
        course_id: {"id": course_id, "credits": credits}
        for course_id, credits in (
            ("MATH", 4), ("PHYS", 4), ("ART", 2), ("HISTORY", 3), ("MUSIC", 1)
        )
    }
    sections = {}
    for section_id, course_id, day, start in (
        ("MATH_A", "MATH", 1, 1),
        ("MATH_B", "MATH", 2, 3),
        ("PHYS_A", "PHYS", 2, 3),
        ("ART_A", "ART", 1, 1),
        ("HISTORY_A", "HISTORY", 3, 3),
        ("MUSIC_A", "MUSIC", 4, 1),
    ):
        sections[section_id] = {
            "id": section_id,
            "course_id": course_id,
            "capacity": 40,
            "meetings": [
                {"weeks": list(range(1, 19)), "day": day, "start": start, "length": 2}
            ],
        }
    masks = {
        sid: build_mask(section["meetings"], **calendar_config)
        for sid, section in sections.items()
    }
    return courses, sections, masks


@pytest.fixture
def score_plan(catalog, calendar_config):
    _, sections, masks = catalog

    def score(plan, student, **overrides):
        options = dict(
            **calendar_config, section_masks=masks, default_course_score=80,
            course_weight=0.7, time_weight=0.3, default_early_penalty=10,
        )
        options.update(overrides)
        return preference(plan, student, sections, **options)
    return score


@pytest.fixture
def run_search(catalog, calendar_config):
    courses, sections, masks = catalog

    def run(student, **overrides):
        options = dict(
            **calendar_config, section_masks=masks,
            fixed_section_ids=[], allowed_section_ids=None,
            excluded_section_ids=set(), allow_partial=False,
            candidate_limit=20, max_search_nodes=10000,
            default_course_score=80, course_weight=0.7,
            time_weight=0.3, default_early_penalty=10,
        )
        options.update(overrides)
        return planner(student, courses, sections, **options)
    return run
