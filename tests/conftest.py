import pytest
import os
import sys

# Add backend/ to path so modules are importable both before and after the split
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = str(tmp_path / 'test.db')

    # Patch DATABASE in whichever module owns it (monolith: app, split: database)
    try:
        import database as db_module
        monkeypatch.setattr(db_module, 'DATABASE', db_path)
        from routes import app as flask_app
        db_module.init_db()
    except ImportError:
        import app as app_module
        monkeypatch.setattr(app_module, 'DATABASE', db_path)
        flask_app = app_module.app
        with flask_app.app_context():
            app_module.init_db()

    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c
