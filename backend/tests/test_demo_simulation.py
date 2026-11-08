import copy
import random
import threading
import time

import pytest
from backend.core.models import SystemState
from backend.simulation.demo_simulation import DemoSimulation
from backend.service.selection import draw_round1, submit_round1
from backend.simulation import demo_simulation as module


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "Background task did not reach the expected state"


@pytest.fixture
def scenario():
    term = dict(total_weeks=2, days_per_week=7, periods_per_day=13)
    courses = {c: dict(id=c, name=c, credits=2) for c in ['MATH', 'ENG']}
    sections = {}
    for sid, cid, day, start, cap in [('MATH_A', 'MATH', 1, 1, 1), ('MATH_B', 'MATH', 2, 4, 3), ('ENG_A', 'ENG', 3, 4, 3)]:
        sections[sid] = dict(id=sid, course_id=cid, capacity=cap,
            meetings=[dict(weeks=[1, 2], day=day, start=start, length=2)])
    students = {sid: dict(id=sid, major_id='SE', required_course_ids=['MATH', 'ENG'], optional_course_ids=[],
        optional_requirement=dict(mode='count', target=0), preferences=dict(course_scores={}, early_penalty_per_week=0))
        for sid in ['S001', 'S002', 'S003']}
    config = dict(term=term, preference=dict(default_course_score=80, course_weight=.7, time_weight=.3,
        default_early_penalty=0), search=dict(candidate_limit=20, max_search_nodes=10000), alert=dict(threshold=.15, cooldown_seconds=0))
    state = SystemState(dict(term=term, courses=courses, sections=sections, students=students), config)
    sim = DemoSimulation(state, delay=(0, 0), rng=random.Random(7))
    yield state, sim
    sim.stop()


def prepare(state):
    assert submit_round1(state, 'S001', ['MATH_A', 'ENG_A'], 0)['ok']


def draw(state):
    priorities = {sid: {student: i for i, student in enumerate(state.data['students'])} for sid in state.data['sections']}
    assert draw_round1(state, priorities)['ok']


def test_requires_s001_application_before_start(scenario):
    state, sim = scenario
    assert sim.start()['code'] == 'DEMO_NEEDS_APPLICATION'
    assert not sim.status()['running']
    assert not state.data['applications']


def test_real_alerts_draw_and_supplement_leave_s001_untouched(scenario):
    state, sim = scenario
    prepare(state)
    assert sim.start()['ok']
    thread = sim._thread
    assert sim.start()['ok']
    assert sim._thread is thread
    wait_for(lambda: sim.status()['stage'] == 'waiting_draw')
    assert sim.status()['round1_submitted'] == 2
    assert sim.status()['pending_alerts'] > 0
    assert state.data['plan_revision']['S001'] == 1
    assert state.data['applications']['S001'] == ['MATH_A', 'ENG_A']
    draw(state)
    won = copy.deepcopy(state.data['enrollments'])
    wait_for(lambda: sim.status()['stage'] == 'finished')
    assert sim.status()['round2_submitted'] == 2
    assert state.data['enrollments']['S001'] == won['S001']
    for student in ['S002', 'S003']:
        assert set(won[student]) <= set(state.data['enrollments'][student])
        assert set(state.data['enrollments'][student]) == {'MATH_B', 'ENG_A'}
    assert all(state.get_remaining(sid) >= 0 for sid in state.data['sections'])


def test_prefers_higher_score_over_first_id(scenario):
    state, sim = scenario
    state.data['students']['S002']['preferences']['early_penalty_per_week'] = 50
    chosen = sim._choose(sim._snapshot('S002'), False)
    assert 'MATH_B' in chosen['section_ids']
    assert 'MATH_A' not in chosen['section_ids']


@pytest.mark.parametrize('action', ['stop', 'reset'])
def test_stop_or_reset_waits_for_planning_and_prevents_late_commits(scenario, monkeypatch, action):
    state, sim = scenario
    prepare(state)
    entered, release = threading.Event(), threading.Event()
    original = sim._choose
    def blocked(snapshot, supplement):
        entered.set()
        assert release.wait(3)
        return original(snapshot, supplement)
    monkeypatch.setattr(sim, '_choose', blocked)
    sim.start()
    assert entered.wait(3)
    stopped = threading.Event()
    def perform():
        getattr(sim, action)()
        stopped.set()
    stopper = threading.Thread(target=perform)
    stopper.start()
    wait_for(lambda: sim._stop.is_set())
    assert not stopped.is_set()
    release.set()
    stopper.join(3)
    assert stopped.is_set()
    assert not sim.status()['running']
    assert set(state.data['applications']) == (set() if action == 'reset' else {'S001'})
    assert sim.status()['stage'] == ('idle' if action == 'reset' else 'stopped')


def test_supplement_retries_no_seat_with_fresh_plan(scenario, monkeypatch):
    state, sim = scenario
    prepare(state)
    sim.start()
    wait_for(lambda: sim.status()['stage'] == 'waiting_draw')
    sim.stop()
    draw(state)
    original = module.submit_round2
    calls = []
    def racing(state, student, sid):
        calls.append(student)
        if len(calls) == 1:
            return dict(ok=False, code='NO_SEAT')
        return original(state, student, sid)
    monkeypatch.setattr(module, 'submit_round2', racing)
    sim.start()
    wait_for(lambda: sim.status()['stage'] == 'finished')
    assert len(calls) == 3
    assert sim.status()['round2_submitted'] == 2
    assert all(len(state.data['enrollments'][s]) == 2 for s in ['S002', 'S003'])


def test_api_start_status_stop_and_reset(scenario, monkeypatch):
    from backend.api import main
    state, sim = scenario
    monkeypatch.setattr(main, 'state', state)
    monkeypatch.setattr(main, 'simulation', sim)
    assert main.start_simulation().status_code == 409
    submitted = main.round1_submit(main.Round1SubmitRequest(student_id='S001', section_ids=['MATH_A','ENG_A'], expected_plan_revision=0))
    assert submitted['ok']
    assert main.start_simulation()['simulation']['running']
    wait_for(lambda: sim.status()['stage'] == 'waiting_draw')
    assert main.get_simulation()['pending_alerts'] > 0
    assert main.get_alerts('S001')['alerts']
    assert main.stop_simulation()['simulation']['stage'] == 'stopped'
    assert main.reset_selection()['ok']
    assert main.get_simulation()['stage'] == 'idle'
    assert not main.get_state('S001')['current_application']


def test_api_reports_applicants_and_remaining_across_both_rounds(scenario, monkeypatch):
    from backend.api import main
    state, sim = scenario
    monkeypatch.setattr(main, 'state', state)
    monkeypatch.setattr(main, 'simulation', sim)
    assert main.get_state('S001')['applicant_counts']['MATH_A'] == 0
    prepare(state)
    result = main.round1_submit(main.Round1SubmitRequest(
        student_id='S002', section_ids=['MATH_A', 'ENG_A'], expected_plan_revision=0))
    assert result['student_state']['applicant_counts']['MATH_A'] == 2
    assert main.get_state('S001')['remaining']['MATH_A'] == 1
    draw(state)
    snapshot = main.get_state('S001')
    assert snapshot['phase'] == 'ROUND2_OPEN'
    assert snapshot['applicant_counts']['MATH_A'] == 2
    assert snapshot['remaining']['MATH_A'] == 0
    result = main.round2_submit(main.Round2SubmitRequest(student_id='S002', section_id='MATH_B'))
    assert result['ok']
    assert result['student_state']['remaining']['MATH_B'] == 2
