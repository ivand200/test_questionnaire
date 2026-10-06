from pathlib import Path

from fastapi.testclient import TestClient

from qws.api.main import create_app


def make_client(dist: Path) -> TestClient:
    return TestClient(create_app(dist))


def make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text('<html><body><div id="root"></div></body></html>')
    return dist


def test_health_returns_ok(tmp_path):
    # spec: 1.1-a
    # GIVEN the Backend is up
    client = make_client(tmp_path / "missing-dist")

    # WHEN a client sends GET /api/health
    response = client.get("/api/health")

    # THEN HTTP 200 and the body is exactly {"status": "ok"}
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_built_index_html(tmp_path):
    # spec: 2.1-a
    # GIVEN frontend/dist/index.html exists
    client = make_client(make_dist(tmp_path))

    # WHEN a client sends GET /
    response = client.get("/")

    # THEN HTTP 200, content type text/html, body contains <div id="root">
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in response.text


def test_health_is_not_html_when_built_frontend_exists(tmp_path):
    # spec: 2.2-a
    # GIVEN frontend/dist/ exists
    client = make_client(make_dist(tmp_path))

    # WHEN a client sends GET /api/health
    response = client.get("/api/health")

    # THEN HTTP 200 and the body is {"status": "ok"}, not HTML
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_without_built_frontend_health_answers_and_root_is_404(tmp_path):
    # spec: 2.3-a
    # GIVEN frontend/dist/ does not exist
    client = make_client(tmp_path / "missing-dist")

    # WHEN a client sends GET /api/health, then GET /
    health = client.get("/api/health")
    root = client.get("/")

    # THEN /api/health gives 200 {"status": "ok"} and / gives 404
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert root.status_code == 404
