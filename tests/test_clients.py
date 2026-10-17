"""Client service and API tests."""

from app.core.normalize import build_client_search_text, search_tokens
from app.db import SessionLocal
from app.schemas.client import ClientCreate
from app.services import clients as client_svc


def test_search_cyrillic_and_phone():
    text = build_client_search_text(
        "ООО Ромашка",
        None,
        "info@test.ru",
        "+7 (999) 123-45-67",
        None,
        None,
    )
    assert "ромашка" in text
    assert "9991234567" in text
    tokens = search_tokens("РОМАШКА")
    assert tokens == ["ромашка"]
    tokens = search_tokens("+7 999 123")
    assert "999123" in "".join(tokens) or any(
        "999" in t for t in tokens
    )


def test_create_archive_delete(auth_client):
    r = auth_client.post(
        "/api/v1/clients",
        json={"name": "Тест Клиент", "phone": "89991112233"},
    )
    assert r.status_code == 201
    client_id = r.json()["id"]

    r = auth_client.get("/api/v1/clients", params={"q": "тест"})
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r = auth_client.post(f"/api/v1/clients/{client_id}/archive")
    assert r.status_code == 200
    assert r.json()["is_archived"] is True

    r = auth_client.get("/api/v1/clients")
    assert r.json()["total"] == 0

    r = auth_client.get(
        "/api/v1/clients",
        params={"archived": "archived"},
    )
    assert r.json()["total"] == 1

    r = auth_client.delete(f"/api/v1/clients/{client_id}")
    assert r.status_code == 204
    r = auth_client.get(f"/api/v1/clients/{client_id}")
    assert r.status_code == 404


def test_deal_attach_detach(auth_client):
    c = auth_client.post(
        "/api/v1/clients",
        json={"name": "Клиент А"},
    ).json()
    d = auth_client.post(
        "/api/v1/deals",
        json={"title": "Сделка без клиента"},
    ).json()
    assert d["client_id"] is None

    r = auth_client.put(
        f"/api/v1/deals/{d['id']}/client",
        json={"client_id": c["id"]},
    )
    assert r.status_code == 200
    assert r.json()["client_id"] == c["id"]

    r = auth_client.delete(f"/api/v1/deals/{d['id']}/client")
    assert r.status_code == 200
    assert r.json()["client_id"] is None


def test_soft_delete_cascades_tasks(auth_client):
    c = auth_client.post(
        "/api/v1/clients",
        json={"name": "С каскадом"},
    ).json()
    t = auth_client.post(
        "/api/v1/tasks",
        json={"title": "Звонок", "client_id": c["id"]},
    ).json()
    auth_client.delete(f"/api/v1/clients/{c['id']}")
    r = auth_client.get(f"/api/v1/tasks/{t['id']}")
    assert r.status_code == 404
