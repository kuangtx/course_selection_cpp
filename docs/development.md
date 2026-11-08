# Development guide

## Architecture and data flow

The browser renders the timetable and calls `/api`. FastAPI validates request
bodies, reads a locked snapshot, and delegates selection mutations to the service
layer. Recommendations compute on copied state; submitting a recommendation
validates the latest state again.

`core/planner.py` preserves the dictionary API used by the Python orchestration.
It validates input, creates native Student/Course/Section objects, calls the
extension, and converts native results back to dictionaries. `cpp/planner.hpp`
declares plain C++ data types and the search function; `cpp/planner.cpp` implements
search. `cpp/bindings.cpp` registers those types and functions when Python imports
`_planner`. No Python fallback is silently selected if the extension is missing.

## Build and ABI

Install requirements-dev.txt in the interpreter environment, then run
`python scripts/build_native.py`. This chooses the invoking Python, locates
pybind11's CMake package, builds Release, and copies the extension into
backend/core. Use `--generator Ninja` if desired. A C++ compiler and CMake must
be on PATH. The build directory is segregated by Python cache tag; remove that
build directory before changing compilers or CMake generators.

A CPython 3.14 Linux x86_64 module is not a portable Python source file: operating
system, architecture, Python ABI, and C++/system runtime compatibility all matter.
Rebuild on Ubuntu when deploying. The static C++ library is linked into the Python
module and does not need to be distributed separately.

## Search and scoring

Time slots are represented by a semester bitmask. A slot is indexed by week,
day, then period, all supplied as one-based meeting values. Python uses arbitrary
precision integers; bindings split them into little-endian 64-bit words. Conflict
checking is a word-wise AND. A mask wider than 64 bits must never be truncated.

The search places fixed sections first, traverses required courses, then optional
courses. Optional courses may be skipped. Partial searches may also skip required
courses. Allowed/excluded sections constrain the candidate pool. Optional targets
are either course counts or credits. Candidates are ordered by missing required
courses, optional gap, descending preference, then section IDs. Candidate limits
bound retained results; node budgets bound traversal. Negative limits mean
unlimited and zero is invalid. LIMIT_REACHED never proves infeasibility.

Preference combines optional-course preference and an early-class time score.
Round-one risk multiplies per-section win estimates; it is an approximation, not
a guarantee of admission. Fallback evaluates bounded lottery-outcome scenarios
and reports lower/upper coverage bounds with unresolved scenarios. Adjustment
search targets one crowded section at a time while pinning the others when
oversubscribed sections exist. Supplement search pins enrolled sections and uses
remaining seats; submissions still happen individually.

## State and concurrency

SystemState owns students, courses, applications, applicant sets, enrollments,
remaining-seat counts, alert baselines, and revisions. `state_version` tracks
shared changes, while `plan_revision` guards replacement/withdrawal for one
student. Read data under the state lock; avoid expensive search while holding it.

The simulator runs a background thread, skips S001, waits between turns, and
uses the same selection service as manual requests. Round one currently requires
S001 to submit first. It does not automatically withdraw simulated students.
Shutdown/reset stops and joins the simulator. All state is process-local: multiple
Uvicorn workers would create inconsistent independent selections. A restart loses
applications, preferences, results, and alerts.

## Configuration

Edit data/demo.json for the sample term/catalog/students. Edit
simulation_config.json for preference weights, candidate/node budgets, fallback
scenario budgets, ranking weights, and alert thresholds/cooldowns. These files
are loaded at backend startup; restart after changing them. Backend reset restores
the startup catalog. The round-one HTTP draw uses random seed 42 for reproducibility.

Vite development serves `/`; production defaults to `/course1107/`.
VITE_BASE_PATH overrides that choice. VITE_API_BASE_URL defaults to `/api`.
API_PROXY_TARGET changes only Vite's development proxy. Build-time Vite variables
are public browser configuration and must not contain secrets.

## Test strategy

Run `python -m pytest -q` after building the native module. Existing tests cover
conflicts, scoring, feasibility, risk, fallback, recommendation, simulation, and
withdrawal. Native-boundary tests cover wide integer masks and native/reference
agreement. HTTP tests exercise JSON validation, revisions, phase transitions,
withdrawal, and reset via FastAPI TestClient with isolated state.

Run frontend `npm test` for components/hooks, `npm run build` for TypeScript and
production bundling, and Playwright for browser behavior. Desktop scenarios mock
API data; selection scenarios start a real backend. CI builds native code on
Ubuntu for Python 3.11 and 3.14 and runs frontend unit/build/desktop checks. CI
configuration is provided; a green remote run still needs to be observed after push.

Keep comments in English and explain invariants or decisions rather than repeating
syntax. Chinese course names, UI text, and user-visible simulator messages are
intentional. Keep tests independent of real server addresses and credentials.
