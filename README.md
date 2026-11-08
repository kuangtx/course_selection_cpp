# Course Selection

A two-round course selection demo with a React/TypeScript timetable, a FastAPI
backend, and a C++17 backtracking planner exposed through pybind11. The sample
catalog and UI use Chinese; source comments and developer documentation use English.

Round one collects applications and resolves oversubscribed sections by a seeded
lottery. Round two admits students to remaining seats one section at a time.
Students can withdraw and resubmit. Recommendations combine preferences, estimated
lottery risk, and bounded fallback search. The simulator submits real applications
for other students; S001 remains the manual participant.

## Quick start (Ubuntu / WSL)

Prerequisites: Python 3.11 or newer with development headers and venv support,
CMake 3.18+, a C++17 compiler, and Node.js 22.12+.
Use the same Python interpreter for building and running the native module.

```bash
sudo apt update
sudo apt install -y build-essential cmake python3-dev python3-venv
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/build_native.py
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to the backend. Start the backend
from the repository root so package-relative imports resolve correctly.
Windows users can use WSL, or a matching Python installation and MSVC C++ toolchain.
Linux `.so` files cannot be loaded by Windows Python, which uses `.pyd` files.

## Repository layout

```text
backend/
  api/             HTTP request validation and endpoints
  core/            Models, scoring, recommendations, Python/native adapter
    cpp/           C++ algorithm, shared declarations, pybind11 bindings
  service/         Application, enrollment, lottery, and alert mutations
  simulation/      Background demo student workflow
  tests/           Unit, integration, native-boundary, and HTTP tests
    reference_planner.py  Python regression oracle (not used by the application)
data/              Demo catalog and search/scoring configuration
frontend/          React UI, component tests, and Playwright scenarios
scripts/           Reproducible build and schema export tools
docs/              Development, API, and deployment guides
.github/workflows/ Automated source build and tests
```

## Validation

```bash
python -m pytest -q
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:desktop
# With the compiled backend available in the active Python environment:
npm run test:e2e
```

Native tests import the real extension and fail if it has not been built. The
Python reference implementation is used only for comparison in tests.

## Deployment and limitations

Build the frontend with `npm run build`; the default production prefix is
`/course1107/`. Upload the *contents* of `frontend/dist` to the matching Nginx
location. Set `VITE_BASE_PATH=/` when deploying at the domain root. API requests
use `/api`, independently of the frontend prefix.

This is a demonstration application: all state lives in one backend process and
is lost on restart/reset. Run **one Uvicorn worker**. There is no authentication
or administrator authorization; reset, draw, and simulation controls are publicly
callable if the API is exposed. Add access control and persistence before real
student use. Native search currently holds the Python GIL, and concurrent CPU
heavy requests can delay other work. Search budgets do not guarantee optimality.

Do not commit virtual environments, node_modules, generated binaries, certificates,
private keys, or machine-specific IDE files. Build native artifacts on the target
platform (or a compatible build environment) rather than shipping the local `.so`.

See [Development](docs/development.md), [HTTP and native API](docs/api.md), and
[Deployment](docs/deployment.md). No project license has been selected yet; choose
one before inviting redistribution or outside contributions.
