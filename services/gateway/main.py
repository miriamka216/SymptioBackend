import os
from functools import partial

from shared.health import create_app, downstream_ready

SERVICES = ("model", "file", "training", "provider", "chat", "runtime")
app = create_app(
    "gateway",
    {
        f"{service}-service": partial(
            downstream_ready,
            os.getenv(f"{service.upper()}_SERVICE_URL", f"http://{service}-service:8000"),
        )
        for service in SERVICES
    },
)
