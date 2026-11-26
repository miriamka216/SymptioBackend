"""Infrastructure probes. No domain endpoints or authentication in Patch 00."""
import os
from collections.abc import Callable

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

Probe = Callable[[], bool]


def postgres_ready() -> bool:
    import psycopg

    with psycopg.connect(
        host=os.environ["DB_HOST"], port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], connect_timeout=3,
        options="-c statement_timeout=2000",
    ) as connection:
        return connection.execute("SELECT 1").fetchone() == (1,)


def broker_ready() -> bool:
    import pika

    params = pika.ConnectionParameters(
        host=os.environ["BROKER_HOST"], port=int(os.getenv("BROKER_PORT", "5672")),
        credentials=pika.PlainCredentials(
            os.environ["BROKER_USER"], os.environ["BROKER_PASSWORD"]
        ),
        connection_attempts=1, socket_timeout=3, stack_timeout=5,
        blocked_connection_timeout=3,
    )
    connection = pika.BlockingConnection(params)
    try:
        return connection.is_open
    finally:
        if connection.is_open:
            connection.close()


def downstream_ready(url: str) -> bool:
    with httpx.Client(timeout=4.0, trust_env=False) as client:
        response = client.get(f"{url.rstrip('/')}/readyz")
        return response.status_code == 200 and response.json().get("status") == "ready"


def create_app(name: str, probes: dict[str, Probe]) -> FastAPI:
    app = FastAPI(title=f"Evalvo | {name}", version="0.1.0")

    @app.get("/healthz", tags=["Infrastructure"])
    def healthz():
        return {"service": name, "status": "ok"}

    @app.get("/readyz", tags=["Infrastructure"], responses={503: {"description": "Dependency unavailable"}})
    def readyz():
        checks = {}
        for dependency, probe in probes.items():
            try:
                checks[dependency] = "ok" if probe() else "unavailable"
            except Exception:
                # Never return connection strings, passwords or internal exceptions.
                checks[dependency] = "unavailable"
        ready = all(value == "ok" for value in checks.values())
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"service": name, "status": "ready" if ready else "not_ready", "checks": checks},
        )

    return app
