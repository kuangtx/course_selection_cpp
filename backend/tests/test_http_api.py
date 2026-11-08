"""HTTP-level regression tests with isolated state and a real native planner."""
import pytest
from fastapi.testclient import TestClient
from backend.api import main
from backend.tests.test_demo_simulation import scenario


@pytest.fixture
def client(scenario, monkeypatch):
    state, simulation = scenario
    monkeypatch.setattr(main, 'state', state)
    monkeypatch.setattr(main, 'simulation', simulation)
    with TestClient(main.app) as client:
        yield client


def test_catalog_and_request_validation(client):
    assert client.get('/api/catalog').status_code == 200
    assert client.get('/api/state', params={'student_id': 'missing'}).status_code == 404
    assert client.get('/api/state').status_code == 422
    assert client.post('/api/recommend', json={'student_id': 'S001', 'purpose': 'initial',
                                             'limit': 0}).status_code == 422
    assert client.post('/api/round1/withdraw', json={'student_id': 'S001',
                        'expected_plan_revision': 0, 'extra': True}).status_code == 422
    assert client.post('/api/close').status_code == 409


def test_round_trip_revision_lottery_withdrawal_and_reset(client):
    request = {'student_id': 'S001', 'section_ids': ['MATH_A', 'ENG_A'],
               'expected_plan_revision': 0}
    response = client.post('/api/round1/submit', json=request)
    assert response.status_code == 200
    revision = response.json()['student_state']['plan_revision']
    stale = client.post('/api/round1/withdraw', json={'student_id': 'S001',
                                                   'expected_plan_revision': 0})
    assert stale.status_code == 409
    assert stale.json()['code'] == 'STALE_PLAN'
    assert client.post('/api/round1/withdraw', json={'student_id': 'S001',
                        'expected_plan_revision': revision}).status_code == 200
    state = client.get('/api/state', params={'student_id': 'S001'}).json()
    assert state['applicant_counts']['MATH_A'] == 0
    request['expected_plan_revision'] = state['plan_revision']
    assert client.post('/api/round1/submit', json=request).status_code == 200
    assert client.post('/api/round1/draw').status_code == 200
    state = client.get('/api/state', params={'student_id': 'S001'}).json()
    assert state['phase'] == 'ROUND2_OPEN'
    assert set(state['enrolled_section_ids']) == {'MATH_A', 'ENG_A'}
    assert client.post('/api/round2/withdraw', json={'student_id': 'S001',
                        'section_ids': ['MATH_A'],
                        'expected_plan_revision': state['plan_revision']}).status_code == 200
    assert client.post('/api/round2/submit', json={'student_id': 'S002',
                                                'section_id': 'MATH_A'}).status_code == 200
    assert client.post('/api/close').status_code == 200
    assert client.post('/api/reset').status_code == 200
    state = client.get('/api/state', params={'student_id': 'S001'}).json()
    assert state['phase'] == 'ROUND1_OPEN'
    assert state['current_application'] == state['enrolled_section_ids'] == []


def test_preferences_reject_unknown_courses_and_out_of_range_scores(client):
    url = '/api/students/S001/preferences'
    assert client.patch(url, json={'preferences': {'course_scores': {'missing': 80}}}).status_code == 404
    assert client.patch(url, json={'preferences': {'course_scores': {'MATH': 101}}}).status_code == 422
    assert client.patch(url, json={'preferences': {'course_scores': {'MATH': 90}}}).status_code == 200
    assert client.get('/api/catalog').json()['students']['S001']['preferences']['course_scores'] == {'MATH': 90}
