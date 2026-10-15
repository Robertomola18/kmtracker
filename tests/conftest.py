import os
import sys
import tempfile
import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

TEST_PASSWORD = 'test-password'


@pytest.fixture(scope='session')
def km_db_path(tmp_path_factory):
    tmp = tmp_path_factory.mktemp('km_db')
    db = str(tmp / 'kmtracker_test.db')
    os.environ['KMTRACKER_DB_PATH'] = db
    yield db


@pytest.fixture(scope='session')
def km(km_db_path):
    import app
    app.app.config['TESTING'] = True
    app.app.config['WTF_CSRF_ENABLED'] = False
    from models import init_db, init_settings, set_setting
    from werkzeug.security import generate_password_hash
    init_db()
    init_settings()
    set_setting('password_hash', generate_password_hash(TEST_PASSWORD))
    return app


@pytest.fixture
def client(km):
    return km.app.test_client()


@pytest.fixture(autouse=True)
def _reset_rate_limit(km):
    km._login_attempts.clear()
    yield
    km._login_attempts.clear()


@pytest.fixture
def logged_client(client):
    resp = client.get('/login')
    assert resp.status_code == 200
    csrf = client.get('/login').get_data(as_text=True)
    import re
    m = re.search(r'name="_csrf" value="([^"]+)"', csrf)
    assert m, 'csrf token no encontrado en login.html'
    token = m.group(1)
    resp = client.post('/login', data={'password': TEST_PASSWORD, '_csrf': token})
    assert resp.status_code in (200, 302)
    return client