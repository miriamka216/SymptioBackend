from shared.errors import install_error_handlers
from shared.health import create_app, postgres_ready

app = create_app("file-service", {"postgres": postgres_ready})
install_error_handlers(app)
