import os
import tempfile
import pytest
from app import create_app


@pytest.fixture
def app():
    """Create and configure a clean Flask application instance for testing."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": db_path,
        "LOG_LEVEL": "WARNING",
    })

    yield app

    # Cleanup temporary database file after test execution
    os.close(db_fd)
    if os.path.exists(db_path):
        try:
            os.unlink(db_path)
        except OSError:
            pass


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()
