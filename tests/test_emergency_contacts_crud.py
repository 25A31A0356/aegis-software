"""
Tests for Emergency Contacts Management.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_emergency_contacts_crud_lifecycle(async_client: AsyncClient):
    user_id = "user_contacts_test_01"
    headers = {"X-Aegis-User-Id": user_id}

    # 1. Initially empty
    list_res1 = await async_client.get("/api/v1/sos/contacts", headers=headers)
    assert list_res1.status_code == 200
    assert len(list_res1.json()["data"]) == 0

    # 2. Add contact
    create_res = await async_client.post("/api/v1/sos/contacts", headers=headers, json={
        "name": "Aarav Sharma",
        "phone": "+919876543210",
        "relationship": "Brother",
        "email": "aarav@example.com",
        "notify_on_sos": True,
        "notify_on_safe": True
    })
    assert create_res.status_code == 200
    contact = create_res.json()["data"]
    assert contact["name"] == "Aarav Sharma"
    contact_id = contact["id"]

    # 3. List contacts -> 1 contact
    list_res2 = await async_client.get("/api/v1/sos/contacts", headers=headers)
    assert list_res2.status_code == 200
    assert len(list_res2.json()["data"]) == 1

    # 4. Delete contact
    del_res = await async_client.delete(f"/api/v1/sos/contacts/{contact_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True

    # 5. List contacts -> 0 contacts
    list_res3 = await async_client.get("/api/v1/sos/contacts", headers=headers)
    assert list_res3.status_code == 200
    assert len(list_res3.json()["data"]) == 0