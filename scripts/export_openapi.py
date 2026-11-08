"""Export the FastAPI schema after building the native extension."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.api.main import app

if __name__ == '__main__':
    destination = ROOT / 'docs/openapi.json'
    destination.write_text(json.dumps(app.openapi(), indent=2) + '\n', encoding='utf-8')
    print(destination)
