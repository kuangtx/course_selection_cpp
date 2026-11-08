# API reference

## HTTP conventions

Run `python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000` from
the repository root. The HTTP API prefix is `/api`, including when the frontend
is hosted under `/course1107/`. FastAPI exposes `/docs`, `/redoc`, and
`/openapi.json` on the backend. The supplied Nginx example forwards only `/api/`.
Request/response bodies are JSON; endpoints have no authentication.

Validation errors use HTTP 422 with FastAPI's `detail` array. Business errors use
`{"ok": false, "code": "...", "message": "..."}`. Unknown student/course/section/
alert IDs map to 404 where the handler emits those codes. Invalid request,
preferences, and action codes map to 422; other business failures (including
WRONG_PHASE, STALE_PLAN, NO_SEAT) default to 409. Extra top-level request fields
are forbidden. Consult generated OpenAPI for exact field validation.

## Endpoints

| Method | Path | Input | Result / behavior |
| --- | --- | --- | --- |
| GET | /api/catalog | None | term, students, courses, sections, section_masks |
| GET | /api/state | student_id query | Current student state |
| PATCH | /api/students/{student_id}/preferences | preferences object | Updated version and student_state |
| POST | /api/recommend | student_id, purpose, limit (default 3) | Evaluated candidates and search status |
| POST | /api/round1/submit | student_id, section_ids, expected_plan_revision | Replace current first-round application |
| POST | /api/round1/withdraw | student_id, expected_plan_revision | Withdraw the whole first-round application |
| POST | /api/round1/draw | None | Seeded lottery; move to ROUND2_OPEN |
| POST | /api/round2/submit | student_id, section_id | Enroll in one available section |
| POST | /api/round2/withdraw | student_id, section_ids (nonempty), expected_plan_revision | Release selected enrolled sections |
| GET | /api/alerts | student_id query | state_version and alerts |
| POST | /api/alerts/{alert_id}/ack | None | Acknowledge alert; returns student_state |
| POST | /api/close | None | Close round two; repeated close is idempotent |
| POST | /api/reset | None | Stop simulation and restore startup data |
| GET | /api/demo/simulation | None | Simulator progress/status |
| POST | /api/demo/simulation/start | None | Start simulator; round one requires S001's application |
| POST | /api/demo/simulation/stop | None | Stop simulator, preserve selections |

## Student state and revisions

State contains `phase`, `current_application`, `enrolled_section_ids`,
`applicant_counts`, `remaining`, `state_version`, and `plan_revision`.
Phases are ROUND1_OPEN, DRAWING, ROUND2_OPEN, and CLOSED. First-round applicant
counts can exceed capacity; they are not enrollment counts. Second-round occupied
seats equal capacity minus remaining.

Use the latest plan_revision as expected_plan_revision for replacement or
withdrawal. On STALE_PLAN refresh state and ask the user to review again.
Generating a plan never reserves a seat. Round-two submission rechecks remaining
capacity and conflicts; do not submit a whole candidate atomically.

## Examples

```json
{"student_id":"S001","purpose":"initial","limit":3}
```

Purpose is initial or adjustment in ROUND1_OPEN, supplement in ROUND2_OPEN.
Zero limit is rejected; negative limit returns all retained candidates (search
budgets still apply). Results include state_version, plan_revision, purpose,
search_status, searched_nodes, decision, current_plan, plans, and limitations.
Search status is FOUND, INFEASIBLE, or LIMIT_REACHED. An empty limited search does
not prove there is no valid schedule.

A plan contains section_ids, preference_score, is_complete, unmet_requirements,
risk, fallback, recommendation_score, comparison, and explanations as applicable.
Supplement plans also expose new_section_ids and use null risk/fallback/
recommendation_score/comparison. Fallback reports covered, uncovered, unknown,
coverage_lower_bound, coverage_upper_bound, counts, examples, and limitations.

```json
{"student_id":"S001","section_ids":["MATH_A"],"expected_plan_revision":0}
```

Section IDs here are illustrative: use /api/catalog for valid IDs and include
all required selections when submitting a first-round application.

```json
{"preferences":{"course_scores":{"MATH":90},"early_penalty_per_week":10}}
```

Course scores must reference catalog courses and be finite values in [0,100].
Early penalty must be finite and nonnegative. Supplied course_scores replaces
that preference map; omitted fields remain unchanged.

section_masks are arbitrary-size JSON integers; JavaScript cannot represent them
exactly as Number. Treat them as backend metadata; the UI uses meeting arrays.

## Native planner contract

`backend.core.planner.planner(student, courses, sections, *, ...)` accepts Python
dictionaries plus section_masks, fixed_section_ids, allowed_section_ids (None means
no whitelist), excluded_section_ids, allow_partial, candidate_limit,
max_search_nodes, total_weeks, days_per_week, periods_per_day, default_course_score,
course_weight, time_weight, and default_early_penalty. It validates arguments and
returns search_status, searched_nodes, and plans without mutating input data.

The extension entry point is `_planner.plan_courses(student, courses, sections,
calendar, scoring, options)`. Types are Student, Course, Section, Calendar, Scoring,
and SearchOptions. Section.time_mask is exposed as a Python integer; bindings
convert it to/from 64-bit words. Invalid negative masks raise ValueError.
SearchResult and Plan properties are read-only. Use the Python adapter for the
application's full input validation and legacy result format.

Export a machine-readable request schema with `python scripts/export_openapi.py`.
Response dictionaries currently have no Pydantic response models, so OpenAPI does
not fully describe response fields; the descriptions above complement the schema.
