from shared.health import create_app, postgres_ready, broker_ready

app = create_app("chat-service", {"postgres": postgres_ready, "rabbitmq": broker_ready})
