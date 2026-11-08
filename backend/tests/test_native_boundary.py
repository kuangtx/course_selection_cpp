"""Exercise real pybind11 conversions and compare bounded small searches."""
import pytest
from backend.core import _planner
from backend.core.planner import planner
from backend.tests.reference_planner import planner as reference


@pytest.mark.parametrize('mask', [0, 1, 1 << 63, 1 << 64, (1 << 1637) | (1 << 65) | 3])
def test_mask_round_trip(mask):
    section = _planner.Section('A', 'C', 10, mask)
    assert section.time_mask == mask
    section.time_mask = mask | (1 << 127)
    assert section.time_mask == mask | (1 << 127)


def test_negative_mask_rejected_on_creation_and_assignment():
    with pytest.raises(ValueError):
        _planner.Section('A', 'C', 10, -1)
    section = _planner.Section('A', 'C', 10, 0)
    with pytest.raises(ValueError):
        section.time_mask = -1
    assert section.time_mask == 0


@pytest.mark.parametrize('partial', [False, True])
@pytest.mark.parametrize('budget', [1, 10000])
@pytest.mark.parametrize('mode,target', [('count', 1), ('credits', 3)])
def test_native_matches_reference(catalog, calendar_config, make_student, partial, budget, mode, target):
    courses, sections, masks = catalog
    student = make_student(required=['MATH', 'PHYS'], optional=['ART', 'HISTORY'],
                           mode=mode, target=target)
    options = dict(**calendar_config, section_masks=masks, fixed_section_ids=[],
                   allowed_section_ids=None, excluded_section_ids=set(),
                   allow_partial=partial, candidate_limit=20, max_search_nodes=budget,
                   default_course_score=80, course_weight=.7, time_weight=.3,
                   default_early_penalty=10)
    native = planner(student, courses, sections, **options)
    expected = reference(student, courses, sections, **options)
    assert native['search_status'] == expected['search_status']
    assert native['searched_nodes'] == expected['searched_nodes']
    assert len(native['plans']) == len(expected['plans'])
    for actual, original in zip(native['plans'], expected['plans']):
        assert actual['section_ids'] == original['section_ids']
        assert actual['is_complete'] == original['is_complete']
        assert actual['unmet_requirements'] == original['unmet_requirements']
        assert actual['preference_score']['total'] == pytest.approx(original['preference_score']['total'])
