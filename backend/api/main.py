from contextlib import asynccontextmanager

import copy
import json
import math
import random
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..core.models import SystemState, load_data
from ..core.recommend import recommend
from ..service.alerts import get_student_alerts, process_alert
from ..service.selection import draw_round1, submit_round1, submit_round2, withdraw_selection
from ..simulation.demo_simulation import DemoSimulation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_DATA = load_data(PROJECT_ROOT / "data" / "demo.json")
CONFIG = json.loads(
    (PROJECT_ROOT / "data" / "simulation_config.json").read_text(encoding="utf-8")
)

@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        simulation.stop()


app = FastAPI(title="Course Selection API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One process owns this in-memory state; multiple workers would diverge.
state = SystemState(DEMO_DATA, CONFIG)
simulation = DemoSimulation(state)

ERROR_STATUS = {
    "STUDENT_NOT_FOUND": 404,
    "COURSE_NOT_FOUND": 404,
    "SECTION_NOT_FOUND": 404,
    "ALERT_NOT_FOUND": 404,
    "INVALID_REQUEST": 422,
    "INVALID_PREFERENCES": 422,
    "INVALID_ACTION": 422,
}


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreferenceValues(RequestModel):
    course_scores: dict[str, float] | None = None
    early_penalty_per_week: float | None = Field(default=None, ge=0)


class PreferencesRequest(RequestModel):
    preferences: PreferenceValues


class RecommendRequest(RequestModel):
    student_id: str
    purpose: Literal["initial", "adjustment", "supplement"]
    limit: int = 3


class Round1SubmitRequest(RequestModel):
    student_id: str
    section_ids: list[str]
    expected_plan_revision: int = Field(ge=0)


class Round2SubmitRequest(RequestModel):
    student_id: str
    section_id: str


class WithdrawRequest(RequestModel):
    student_id: str
    expected_plan_revision: int = Field(ge=0)


class Round2WithdrawRequest(WithdrawRequest):
    section_ids: list[str] = Field(min_length=1)


def error_response(code, message):
    return JSONResponse(
        status_code=ERROR_STATUS.get(code, 409),
        content={"ok": False, "code": code, "message": message},
    )


def business_response(result, student_id=None):
    if not result["ok"]:
        return error_response(result["code"], result["message"])

    response = dict(result)
    if student_id is not None:
        with state.data["lock"]:
            response["student_state"] = student_state_unlocked(student_id)
    return response


def student_state_unlocked(student_id):
    data = state.data
    return {
        "phase": data["phase"],
        "current_application": list(data["applications"].get(student_id, [])),
        "enrolled_section_ids": list(data["enrollments"].get(student_id, [])),
        "applicant_counts": {
            section_id: len(data["applicants"][section_id])
            for section_id in data["sections"]
        },
        "remaining": {
            section_id: state.get_remaining(section_id)
            for section_id in data["sections"]
        },
        "state_version": data["state_version"],
        "plan_revision": data["plan_revision"][student_id],
    }


def student_not_found(student_id):
    return error_response(
        "STUDENT_NOT_FOUND",
        f"Student {student_id} does not exist.",
    )


@app.get("/api/catalog")
def get_catalog():
    with state.data["lock"]:
        data = state.data
        return {
            "term": copy.deepcopy(data["term"]),
            "students": copy.deepcopy(data["students"]),
            "courses": copy.deepcopy(data["courses"]),
            "sections": copy.deepcopy(data["sections"]),
            "section_masks": dict(data["section_masks"]),
        }


@app.get("/api/state")
def get_state(student_id: str):
    with state.data["lock"]:
        if student_id not in state.data["students"]:
            return student_not_found(student_id)
        return student_state_unlocked(student_id)


@app.patch("/api/students/{student_id}/preferences")
def update_preferences(student_id: str, request: PreferencesRequest):
    with state.data["lock"]:
        data = state.data
        if student_id not in data["students"]:
            return student_not_found(student_id)

        updates = request.preferences.model_dump(exclude_none=True)
        course_scores = updates.get("course_scores")
        if course_scores is not None:
            unknown_courses = sorted(set(course_scores) - set(data["courses"]))
            if unknown_courses:
                return error_response(
                    "COURSE_NOT_FOUND",
                    f"Unknown courses: {', '.join(unknown_courses)}.",
                )
            if any(
                not math.isfinite(score) or not 0 <= score <= 100
                for score in course_scores.values()
            ):
                return error_response(
                    "INVALID_PREFERENCES",
                    "Course scores must be finite numbers between 0 and 100.",
                )

        early_penalty = updates.get("early_penalty_per_week")
        if early_penalty is not None and not math.isfinite(early_penalty):
            return error_response(
                "INVALID_PREFERENCES",
                "Early-class penalty must be a finite number.",
            )

        if updates:
            data["students"][student_id].setdefault("preferences", {}).update(updates)
            data["state_version"] += 1

        result = {
            "ok": True,
            "state_version": data["state_version"],
            "plan_revision": data["plan_revision"][student_id],
        }
        return {
            **result,
            "student_state": student_state_unlocked(student_id),
        }


@app.post("/api/recommend")
def get_recommendation(request: RecommendRequest):
    if request.limit == 0:
        return error_response("INVALID_REQUEST", "limit must be a non-zero integer.")

    with state.data["lock"]:
        data = state.data
        if request.student_id not in data["students"]:
            return student_not_found(request.student_id)

        expected_phase = (
            "ROUND2_OPEN" if request.purpose == "supplement" else "ROUND1_OPEN"
        )
        if data["phase"] != expected_phase:
            return error_response(
                "WRONG_PHASE",
                f"{request.purpose} recommendations require {expected_phase}.",
            )

        student = copy.deepcopy(data["students"][request.student_id])
        courses = copy.deepcopy(data["courses"])
        sections = copy.deepcopy(data["sections"])
        section_masks = dict(data["section_masks"])
        snapshot = state.create_snapshot(request.student_id, request.purpose)

    return recommend(
        student,
        courses,
        sections,
        section_masks=section_masks,
        snapshot=snapshot,
        purpose=request.purpose,
        config=state.config,
        limit=request.limit,
    )


@app.post("/api/round1/submit")
def round1_submit(request: Round1SubmitRequest):
    result = submit_round1(
        state,
        request.student_id,
        request.section_ids,
        request.expected_plan_revision,
    )
    return business_response(result, request.student_id)


@app.post("/api/round1/draw")
def round1_draw():
    rng = random.Random(42)
    data = state.data
    draw_priorities = {
        section_id: {
            student_id: rng.random()
            for student_id in data["students"]
        }
        for section_id in data["sections"]
    }
    result = draw_round1(state, draw_priorities)
    return business_response(result)


@app.post("/api/round1/withdraw")
def round1_withdraw(request: WithdrawRequest):
    result = withdraw_selection(state, request.student_id, request.expected_plan_revision,
                                phase="ROUND1_OPEN")
    return business_response(result, request.student_id)


@app.post("/api/round2/withdraw")
def round2_withdraw(request: Round2WithdrawRequest):
    result = withdraw_selection(state, request.student_id, request.expected_plan_revision,
                                phase="ROUND2_OPEN", section_ids=request.section_ids)
    return business_response(result, request.student_id)


@app.post("/api/round2/submit")
def round2_submit(request: Round2SubmitRequest):
    result = submit_round2(state, request.student_id, request.section_id)
    return business_response(result, request.student_id)


@app.get("/api/alerts")
def get_alerts(student_id: str):
    with state.data["lock"]:
        if student_id not in state.data["students"]:
            return student_not_found(student_id)
        return {
            "state_version": state.data["state_version"],
            "alerts": get_student_alerts(state, student_id),
        }


@app.post("/api/alerts/{alert_id}/ack")
def acknowledge_alert(alert_id: str):
    result = process_alert(state, alert_id, "ack")
    if not result["ok"]:
        return business_response(result)
    return business_response(result, result["alert"]["student_id"])


@app.post("/api/close")
def close_selection():
    with state.data["lock"]:
        data = state.data
        if data["phase"] == "CLOSED":
            return {
                "ok": True,
                "already_closed": True,
                "state_version": data["state_version"],
                "phase": data["phase"],
            }
        if data["phase"] != "ROUND2_OPEN":
            return error_response(
                "WRONG_PHASE",
                "Selection can only be closed during round two.",
            )

        data["phase"] = "CLOSED"
        data["state_version"] += 1
        return {
            "ok": True,
            "already_closed": False,
            "state_version": data["state_version"],
            "phase": data["phase"],
        }


@app.post("/api/reset")
def reset_selection():
    simulation.reset()
    with state.data["lock"]:
        return {
            "ok": True,
            "state_version": state.data["state_version"],
            "phase": state.data["phase"],
        }


@app.get("/api/demo/simulation")
def get_simulation():
    return simulation.status()


@app.post("/api/demo/simulation/start")
def start_simulation():
    result = simulation.start()
    if not result["ok"]:
        return error_response(result["code"], result["message"])
    return result


@app.post("/api/demo/simulation/stop")
def stop_simulation():
    return simulation.stop()
