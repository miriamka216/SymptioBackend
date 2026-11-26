"""Run after docker compose up --wait. Uses the published Gateway only."""
import json
import sys
from urllib.request import urlopen

SERVICES = {f"{name}-service" for name in ("model", "file", "training", "provider", "chat", "runtime")}
base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def get(path):
    with urlopen(base + path, timeout=45) as response:
        if response.status != 200:
            raise RuntimeError(f"{path}: HTTP {response.status}")
        return json.load(response)


health = get("/healthz")
assert health == {"service": "gateway", "status": "ok"}, health
ready = get("/readyz")
assert ready["service"] == "gateway" and ready["status"] == "ready", ready
assert set(ready["checks"]) == SERVICES, ready
assert all(value == "ok" for value in ready["checks"].values()), ready
assert "/readyz" in get("/openapi.json")["paths"]
print(json.dumps(ready, indent=2))
print("PASS: gateway and all six domain services ready")
