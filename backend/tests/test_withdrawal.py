import copy
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.api import main
from backend.service.selection import submit_round1, submit_round2, withdraw_selection
from backend.tests.test_demo_simulation import scenario, prepare, draw


def withdraw(state, phase='ROUND1_OPEN', ids=None, revision=None, student='S001'):
    return withdraw_selection(state, student,
        state.data['plan_revision'].get(student, 0) if revision is None else revision,
        phase=phase, section_ids=ids)


def test_round1_clears_applicants_alerts_and_allows_resubmission(scenario):
    state, _ = scenario
    prepare(state)
    submit_round1(state, 'S002', ['MATH_A', 'ENG_A'], 0)
    assert any(a['student_id'] == 'S001' and a['status'] == 'PENDING' for a in state.data['alerts'].values())
    state.data['alert_cooldowns']['S001'] = 9999999999
    before = state.data['state_version']
    assert withdraw(state)['ok']
    assert not state.data['applications'].get('S001')
    assert state.data['applicants']['MATH_A'] == {'S002'}
    assert 'S001' not in state.data['probability_baselines']
    assert 'S001' not in state.data['alert_cooldowns']
    assert all(a['status'] != 'PENDING' for a in state.data['alerts'].values() if a['student_id'] == 'S001')
    assert state.data['state_version'] == before + 1
    assert submit_round1(state, 'S001', ['MATH_B', 'ENG_A'], state.data['plan_revision']['S001'])['ok']
    assert state.data['probability_baselines']['S001']['MATH_B'] == 1


def test_round2_partial_and_full_withdrawal_release_seats_and_allow_reenrollment(scenario):
    state, _ = scenario
    prepare(state)
    draw(state)
    assert withdraw(state, 'ROUND2_OPEN', ['MATH_A'])['ok']
    assert state.data['enrollments']['S001'] == ['ENG_A']
    assert state.get_remaining('MATH_A') == 1
    assert submit_round2(state, 'S002', 'MATH_A')['ok']
    assert submit_round2(state, 'S001', 'MATH_A')['code'] == 'NO_SEAT'
    assert submit_round2(state, 'S001', 'MATH_B')['ok']
    assert withdraw(state, 'ROUND2_OPEN', ['MATH_B', 'ENG_A'])['ok']
    assert state.data['enrollments']['S001'] == []
    assert state.get_remaining('MATH_B') == 3
    assert state.get_remaining('ENG_A') == 3
    assert submit_round2(state, 'S001', 'MATH_B')['ok']


@pytest.mark.parametrize('phase', ['ROUND1_OPEN', 'ROUND2_OPEN'])
def test_other_students_can_be_withdrawn_manually(scenario, phase):
    state, _ = scenario
    if phase == 'ROUND1_OPEN':
        assert submit_round1(state, 'S002', ['MATH_A', 'ENG_A'], 0)['ok']
        assert withdraw(state, phase, student='S002')['ok']
        assert not state.data['applications'].get('S002')
        assert 'S002' not in state.data['applicants']['MATH_A']
    else:
        prepare(state)
        draw(state)
        assert withdraw(state, phase, ['MATH_A'], student='S002')['code'] == 'NOT_ENROLLED'
        assert submit_round2(state, 'S002', 'MATH_B')['ok']
        assert withdraw(state, phase, ['MATH_B'], student='S002')['ok']
        assert 'S002' not in state.data['enrolled_students']['MATH_B']


@pytest.mark.parametrize('phase', ['DRAWING', 'CLOSED'])
def test_no_withdrawal_after_phase_has_changed(scenario, phase):
    state, _ = scenario
    prepare(state)
    state.data['phase'] = phase
    assert withdraw(state)['code'] == 'WRONG_PHASE'
    assert withdraw(state, 'ROUND2_OPEN', ['MATH_A'])['code'] == 'WRONG_PHASE'
    assert state.data['applications']['S001'] == ['MATH_A', 'ENG_A']


def test_atomic_validation_and_stale_requests(scenario):
    state, _ = scenario
    prepare(state)
    assert withdraw(state, revision=0)['code'] == 'STALE_PLAN'
    draw(state)
    before = copy.deepcopy(state.data['enrollments'])
    assert withdraw(state, 'ROUND2_OPEN', ['ENG_A', 'MATH_B'])['code'] == 'NOT_ENROLLED'
    assert withdraw(state, 'ROUND2_OPEN', ['ENG_A', 'UNKNOWN'])['code'] == 'SECTION_NOT_FOUND'
    assert withdraw(state, 'ROUND2_OPEN', [])['code'] == 'INVALID_REQUEST'
    assert state.data['enrollments'] == before
    assert withdraw(state, 'ROUND2_OPEN', ['ENG_A', 'ENG_A'])['ok']
    assert state.get_remaining('ENG_A') == 3


def test_concurrent_duplicate_withdrawals_do_not_release_extra_seats(scenario):
    state, _ = scenario
    prepare(state)
    draw(state)
    revision = state.data['plan_revision']['S001']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: withdraw(state, 'ROUND2_OPEN', ['MATH_A'], revision), range(2)))
    assert sum(r['ok'] for r in results) == 1
    assert state.get_remaining('MATH_A') == 1
    assert submit_round2(state, 'S001', 'MATH_A')['ok']
    assert withdraw(state, 'ROUND2_OPEN', ['MATH_A'], revision)['code'] == 'STALE_PLAN'
    assert state.get_remaining('MATH_A') == 0


def test_api_returns_updated_state_for_both_rounds(scenario, monkeypatch):
    state, _ = scenario
    monkeypatch.setattr(main, 'state', state)
    prepare(state)
    result = main.round1_withdraw(main.WithdrawRequest(student_id='S001', expected_plan_revision=1))
    assert result['student_state']['current_application'] == []
    assert result['student_state']['applicant_counts']['MATH_A'] == 0
    submit_round1(state, 'S001', ['MATH_A', 'ENG_A'], state.data['plan_revision']['S001'])
    draw(state)
    result = main.round2_withdraw(main.Round2WithdrawRequest(student_id='S001',
        expected_plan_revision=state.data['plan_revision']['S001'], section_ids=['MATH_A']))
    assert result['student_state']['enrolled_section_ids'] == ['ENG_A']
    assert result['student_state']['remaining']['MATH_A'] == 1
