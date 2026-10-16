import os
from flask import Flask
from dotenv import load_dotenv

from app.database import close_db, init_db
from app.logging_config import setup_logging
from app.routes import api_bp, register_error_handlers


def create_app(test_config=None) -> Flask:
    """
    Application factory pattern to configure and instantiate the Flask app.
    Supports runtime environment variables and test configuration overrides.
    """
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    # Base configuration defaults
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key-change-in-prod"),
        DATABASE_PATH=os.getenv("DATABASE_PATH", "data/inventory.db"),
        LOG_FILE_PATH=os.getenv("LOG_FILE_PATH"),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
    )

    if test_config is not None:
        app.config.update(test_config)

    # Configure structured JSON logging
    setup_logging(app)

    # Ensure application context database cleanup
    app.teardown_appcontext(close_db)

    # Initialize database tables and indexes
    with app.app_context():
        init_db(app)

    # Register API routes and uniform error handlers
    app.register_blueprint(api_bp)
    register_error_handlers(app)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
