"""业务用户可同时加入多个用户组。"""

from fastapi.testclient import TestClient


def test_user_can_join_multiple_groups(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    user = test_client.post(
        "/mcp-gateway/biz-user/create",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
            "mobile": "13800000000",
            "nickname": "三",
            "enabled": True,
        },
        headers=auth_headers,
    ).json()["data"]
    g1 = test_client.post(
        "/mcp-gateway/biz-user-group/create",
        json={"name": "甲", "enabled": True},
        headers=auth_headers,
    ).json()["data"]
    g2 = test_client.post(
        "/mcp-gateway/biz-user-group/create",
        json={"name": "乙", "enabled": True},
        headers=auth_headers,
    ).json()["data"]
    test_client.post(
        f"/mcp-gateway/biz-user-group/{g1['id']}/members",
        json={"user_ids": [user["id"]]},
        headers=auth_headers,
    )
    resp = test_client.post(
        f"/mcp-gateway/biz-user-group/{g2['id']}/members",
        json={"user_ids": [user["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    for group in (g1, g2):
        members = test_client.get(
            f"/mcp-gateway/biz-user-group/{group['id']}/members",
            headers=auth_headers,
        )
        assert user["id"] in members.json()["data"]["user_ids"]
