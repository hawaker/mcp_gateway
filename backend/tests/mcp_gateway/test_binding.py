"""一个用户在一个业务系统上只有一条绑定，系统编码创建后不可修改。"""

from fastapi.testclient import TestClient


def _create_user(test_client: TestClient, auth_headers: dict[str, str], *, name: str, email: str) -> int:
    created = test_client.post(
        "/mcp-gateway/biz-user/create",
        json={
            "name": name,
            "email": email,
            "mobile": "13800000000",
            "nickname": "三",
            "enabled": True,
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]["id"]


def _create_system(
    test_client: TestClient,
    auth_headers: dict[str, str],
    *,
    name: str,
    code: str,
    attr_fields: list[str],
) -> dict:
    created = test_client.post(
        "/mcp-gateway/biz-system/create",
        json={
            "name": name,
            "code": code,
            "base_url": "https://oa.example.com",
            "enabled": True,
            "params": {},
            "uid_field": "user_id",
            "attr_fields": attr_fields,
        },
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


def test_one_binding_per_user_and_system_and_code_is_immutable(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    system = test_client.post(
        "/mcp-gateway/biz-system/create",
        json={
            "name": "OA",
            "code": "oa",
            "base_url": "https://oa.example.com",
            "enabled": True,
            "params": {},
            "uid_field": "user_id",
            "attr_fields": ["dept"],
        },
        headers=auth_headers,
    ).json()["data"]
    user_id = _create_user(test_client, auth_headers, name="张三", email="zhangsan@example.com")
    test_client.post(
        "/mcp-gateway/biz-binding/create",
        json={
            "user_id": user_id,
            "system_id": system["id"],
            "uid_value": "zhangsan",
            "attrs": {"dept": "rd"},
            "enabled": True,
        },
        headers=auth_headers,
    )
    again = test_client.post(
        "/mcp-gateway/biz-binding/create",
        json={
            "user_id": user_id,
            "system_id": system["id"],
            "uid_value": "other",
            "attrs": {},
            "enabled": True,
        },
        headers=auth_headers,
    )
    assert again.status_code == 400
    renamed = test_client.put(
        f"/mcp-gateway/biz-system/update/{system['id']}",
        json={"code": "erp"},
        headers=auth_headers,
    )
    assert renamed.status_code == 400
    same_code = test_client.put(
        f"/mcp-gateway/biz-system/update/{system['id']}",
        json={"code": "oa", "name": "办公自动化"},
        headers=auth_headers,
    )
    assert same_code.status_code == 200
    assert same_code.json()["data"]["code"] == "oa"
    omitted = test_client.put(
        f"/mcp-gateway/biz-system/update/{system['id']}",
        json={"name": "OA"},
        headers=auth_headers,
    )
    assert omitted.status_code == 200
    assert omitted.json()["data"]["code"] == "oa"


def test_unknown_attr_key_rejected_and_disable_does_not_affect_other_systems(test_client: TestClient, auth_headers: dict[str, str]) -> None:
    user_id = _create_user(test_client, auth_headers, name="李四", email="lisi@example.com")
    oa = _create_system(test_client, auth_headers, name="OA", code="oa-bind", attr_fields=["dept"])
    crm = _create_system(test_client, auth_headers, name="CRM", code="crm", attr_fields=["dept"])

    unknown = test_client.post(
        "/mcp-gateway/biz-binding/create",
        json={
            "user_id": user_id,
            "system_id": oa["id"],
            "uid_value": "lisi",
            "attrs": {"role": "admin"},
            "enabled": True,
        },
        headers=auth_headers,
    )
    assert unknown.status_code == 400

    first = test_client.post(
        "/mcp-gateway/biz-binding/create",
        json={
            "user_id": user_id,
            "system_id": oa["id"],
            "uid_value": "lisi",
            "attrs": {"dept": "rd"},
            "enabled": True,
        },
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text
    second = test_client.post(
        "/mcp-gateway/biz-binding/create",
        json={
            "user_id": user_id,
            "system_id": crm["id"],
            "uid_value": "lisi",
            "attrs": {"dept": "sales"},
            "enabled": True,
        },
        headers=auth_headers,
    )
    assert second.status_code == 200, second.text

    disabled = test_client.put(
        f"/mcp-gateway/biz-binding/update/{first.json()['data']['id']}",
        json={"enabled": False},
        headers=auth_headers,
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["data"]["enabled"] is False

    listed = test_client.get(
        "/mcp-gateway/biz-binding/list",
        params={"page_no": 1, "page_size": 20, "user_id": user_id},
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    by_system = {item["system_id"]: item for item in listed.json()["data"]["items"]}
    assert by_system[oa["id"]]["enabled"] is False
    assert by_system[crm["id"]]["enabled"] is True
    assert by_system[crm["id"]]["uid_value"] == "lisi"
    assert by_system[crm["id"]]["attrs"] == {"dept": "sales"}
