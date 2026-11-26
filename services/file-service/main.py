from shared.health import create_app, postgres_ready

app = create_app("file-service", {"postgres": postgres_ready})
