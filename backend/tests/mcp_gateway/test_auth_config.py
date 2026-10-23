"""一个业务系统同时只有一条启用中的鉴权配置。"""

from fastapi.testclient import TestClient


def test_only_one_enabled_auth_config_per_system(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    system = test_client.post(
        "/mcp-gateway/biz-system/create",
        json={
            "name": "OA",
            "code": "oa-auth",
            "base_url": "https://oa.example.com",
            "enabled": True,
            "params": {},
            "uid_field": "user_id",
            "attr_fields": [],
        },
        headers=auth_headers,
    )
    assert system.status_code == 200, system.text
    system_id = system.json()["data"]["id"]

    def create(url: str) -> dict:
        created = test_client.post(
            "/mcp-gateway/biz-auth/create",
            json={
                "system_id": system_id,
                "method": "fixed",
                "enabled": True,
                "url": url,
                "rule": {},
            },
            headers=auth_headers,
        )
        assert created.status_code == 200, created.text
        return created.json()["data"]

    create("https://oa.example.com/login")
    second = create("https://oa.example.com/token")
    listed = test_client.get(
        "/mcp-gateway/biz-auth/list",
        params={"page_no": 1, "page_size": 20, "system_id": system_id},
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    enabled = [item for item in items if item["enabled"]]
    assert len(items) == 2
    assert len(enabled) == 1
    assert enabled[0]["id"] == second["id"]
