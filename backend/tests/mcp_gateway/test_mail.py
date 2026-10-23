"""SMTP 配置、三维发信和发信记录。

断言读的是假 SMTP 收到的邮件和表里的行，不替换 MailService。
"""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config.path_conf import BASE_DIR
from app.core.base_model import MappedBase, ModelMixin
from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException
from app.modules.mcp_gateway.mail.controller import MailRouter
from app.modules.mcp_gateway.mail.model import MailLogModel
from app.modules.mcp_gateway.mail.schema import MailLogOutSchema, MailLogQueryParam
from app.modules.mcp_gateway.mail.service import MailService
from app.modules.mcp_gateway.mcp_group.model import McpCredentialModel, McpGroupMemberModel, McpGroupModel
from app.modules.mcp_gateway.mcp_group.service import McpCredentialService
from app.modules.mcp_gateway.smtp.controller import SmtpRouter
from app.modules.mcp_gateway.smtp.model import SmtpConfigModel
from app.modules.mcp_gateway.smtp.schema import SmtpConfigCreateSchema, SmtpConfigOutSchema, SmtpConfigUpdateSchema
from app.modules.mcp_gateway.smtp.service import SmtpConfigService
from app.modules.mcp_gateway.user.model import BizUserGroupMemberModel, BizUserGroupModel, BizUserModel
from app.utils.crypto_util import CryptoUtil

_LOG_COLUMNS = {"id", "user_id", "group_id", "channel", "ok", "reason", "created_at"}
_REVISION = "e5a9c2d84f17"
_PASSWORD = "smtp-plain-secret"


class FakeSMTP:
    """不打开网络。记录构造、登录和送出的邮件。"""

    created: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.messages: list = []
        self.login_args: tuple[str, str] | None = None
        self.started_tls = False
        self.quit_called = False
        FakeSMTP.created.append(self)

    def starttls(self, *args, **kwargs) -> None:
        self.started_tls = True

    def login(self, user: str, password: str) -> None:
        self.login_args = (user, password)

    def send_message(self, message) -> None:
        self.messages.append(message)

    def quit(self) -> None:
        self.quit_called = True


class FakeSMTPSSL(FakeSMTP):
    """SSL 构造器。和普通 SMTP 分开，便于断言没有走错类。"""


class BoomSMTP(FakeSMTP):
    def send_message(self, message) -> None:
        raise RuntimeError(f"login failed password={_PASSWORD} token=should-not-leak")


@pytest.fixture(autouse=True)
def _reset_fake_smtp() -> None:
    FakeSMTP.created = []


@pytest.fixture
async def db():
    from app.core.database import async_db_session, async_engine

    async with async_engine.begin() as conn:
        await conn.run_sync(MappedBase.metadata.create_all)

    async with async_db_session() as session:
        transaction = await session.begin()
        try:
            yield session
        finally:
            if transaction.is_active:
                await transaction.rollback()


def _auth() -> AuthSchema:
    return AuthSchema()


def _mail(db, smtp_cls=FakeSMTP, smtp_ssl_cls=FakeSMTPSSL) -> MailService:
    return MailService(_auth(), db, smtp_cls=smtp_cls, smtp_ssl_cls=smtp_ssl_cls)


def _smtp(db) -> SmtpConfigService:
    return SmtpConfigService(_auth(), db, smtp_cls=FakeSMTP, smtp_ssl_cls=FakeSMTPSSL)


async def _add(db, row):
    db.add(row)
    await db.flush()
    return row


async def _user(db, name: str, email: str | None, *, enabled: bool = True) -> BizUserModel:
    return await _add(db, BizUserModel(name=name, email=email, enabled=enabled))


async def _biz_group(db, name: str, *, enabled: bool = True) -> BizUserGroupModel:
    return await _add(db, BizUserGroupModel(name=name, enabled=enabled))


async def _join(db, user_id: int, group_id: int) -> None:
    await _add(db, BizUserGroupMemberModel(user_id=user_id, group_id=group_id))


async def _mcp_group(db, name: str, *, enabled: bool = True) -> McpGroupModel:
    return await _add(db, McpGroupModel(name=name, enabled=enabled))


async def _member(db, group_id: int, principal_type: str, principal_id: int, *, enabled: bool = True) -> McpGroupMemberModel:
    return await _add(
        db,
        McpGroupMemberModel(
            group_id=group_id,
            principal_type=principal_type,
            principal_id=principal_id,
            enabled=enabled,
        ),
    )


async def _credential(db, user_id: int, group_id: int, token: str) -> McpCredentialModel:
    return await _add(
        db,
        McpCredentialModel(
            user_id=user_id,
            group_id=group_id,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            token_encrypted=CryptoUtil.encrypt(token),
        ),
    )


async def _credential_count(db) -> int:
    return (await db.execute(select(func.count()).select_from(McpCredentialModel))).scalar_one()


async def _logs(db) -> list[MailLogModel]:
    result = await db.execute(select(MailLogModel).order_by(MailLogModel.id.asc()))
    return list(result.scalars().all())


def _messages() -> list:
    sent = []
    for client in FakeSMTP.created:
        sent.extend(client.messages)
    return sent


def _body(message) -> str:
    return message.get_content().strip()


def _expected_body(group_id: int, token: str) -> str:
    return "\n".join(
        [
            f"/mcp/{group_id}",
            f"/mcp/{group_id}/sse",
            f"/mcp/{group_id}/messages",
            f"Authorization: Bearer {token}",
        ]
    )


async def _enable_smtp(db, *, enabled: bool = True, encryption: str = "starttls", password: str = _PASSWORD) -> SmtpConfigOutSchema:
    return await _smtp(db).create(
        SmtpConfigCreateSchema(
            enabled=enabled,
            host="smtp.example.com",
            port=587,
            username="smtp-user",
            password=password,
            from_address="mcp@example.com",
            from_name="MCP",
            encryption=encryption,
        )
    )


def test_mail_log_table_has_no_secret_or_mixin_columns() -> None:
    assert issubclass(MailLogModel, MappedBase)
    assert not issubclass(MailLogModel, ModelMixin)
    assert set(MailLogModel.__table__.columns.keys()) == _LOG_COLUMNS
    assert MailLogModel.reason.nullable is True
    assert "password" not in SmtpConfigModel.__table__.columns
    assert "password_encrypted" in SmtpConfigModel.__table__.columns
    assert "token" not in MailLogOutSchema.model_fields
    assert "password" not in SmtpConfigOutSchema.model_fields
    assert "password_encrypted" not in SmtpConfigOutSchema.model_fields


def test_revision_follows_call_log() -> None:
    script = ScriptDirectory.from_config(Config(str(BASE_DIR / "alembic.ini")))
    revision = script.get_revision(_REVISION)
    assert revision is not None
    assert revision.down_revision == "c8d4f1a07e53"
    group_revision = script.get_revision("a7c3e9b14d62")
    assert group_revision is not None
    assert group_revision.down_revision == "b6e2d8a14c90"


def test_routers_and_permissions() -> None:
    from app.api.v1.routers import DOMAIN_CONTROLLERS
    from app.core.dependencies import AuthPermission

    assert SmtpRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    assert MailRouter in DOMAIN_CONTROLLERS["/mcp-gateway"]
    smtp_actions: dict[str, set[str]] = {}
    for route in SmtpRouter.routes:
        path = getattr(route, "path", "")
        assert path.startswith("/smtp")
        assert "/api/v1" not in path
        methods = getattr(route, "methods", set()) or set()
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if isinstance(call, AuthPermission):
                smtp_actions[path] = set()
                for permission in call.permissions:
                    prefix, action = permission.rsplit(":", 1)
                    assert prefix == "module_mcp_gateway:smtp"
                    smtp_actions[path].add(action)
                if path == "/smtp/test":
                    assert "POST" in methods
                    assert smtp_actions[path] == {"test"}
    assert smtp_actions["/smtp/list"] == {"query"}
    assert smtp_actions["/smtp/detail/{id}"] == {"query"}
    assert smtp_actions["/smtp/create"] == {"create"}
    assert smtp_actions["/smtp/update/{id}"] == {"update"}
    assert smtp_actions["/smtp/test"] == {"test"}

    mail_actions: dict[str, set[str]] = {}
    for route in MailRouter.routes:
        path = getattr(route, "path", "")
        assert path.startswith("/mail")
        assert "/api/v1" not in path
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = getattr(dep, "call", None)
            if isinstance(call, AuthPermission):
                mail_actions[path] = {permission.rsplit(":", 1)[1] for permission in call.permissions}
                for permission in call.permissions:
                    prefix = permission.rsplit(":", 1)[0]
                    if path == "/mail/log/list":
                        assert prefix == "module_mcp_gateway:mail-log"
                    else:
                        assert prefix == "module_mcp_gateway:smtp"
    assert mail_actions["/mail/group/{group_id}"] == {"update"}
    assert mail_actions["/mail/user-group/{user_group_id}"] == {"update"}
    assert mail_actions["/mail/user/{user_id}"] == {"update"}
    assert mail_actions["/mail/log/list"] == {"query"}

    for relative in (
        "app/modules/mcp_gateway/smtp/controller.py",
        "app/modules/mcp_gateway/mail/controller.py",
        "app/modules/mcp_gateway/smtp/service.py",
        "app/modules/mcp_gateway/mail/service.py",
    ):
        source = (BASE_DIR / relative).read_text(encoding="utf-8")
        assert "status_code=" not in source


def test_encryption_must_be_none_starttls_or_ssl() -> None:
    with pytest.raises(ValidationError):
        SmtpConfigCreateSchema(
            enabled=True,
            host="smtp.example.com",
            port=25,
            password="secret",
            from_address="mcp@example.com",
            encryption="tls",
        )


async def test_smtp_disabled_writes_no_rows(db) -> None:
    """未启用时三个发送接口都是 400，成功和失败都不落库。"""
    user = await _user(db, "张三", None)
    group = await _mcp_group(db, "办公")
    await _member(db, group.id, "user", user.id)
    await _enable_smtp(db, enabled=False)
    mail = _mail(db)

    for send in (
        lambda: mail.send_for_group(group.id),
        lambda: mail.send_for_user_group(1),
        lambda: mail.send_for_user(user.id),
    ):
        with pytest.raises(CustomException) as exc:
            await send()
        assert exc.value.status_code == 400
        assert _PASSWORD not in exc.value.msg

    assert FakeSMTP.created == []
    assert await _logs(db) == []


async def test_send_for_group_skips_disabled_and_records_missing_email(db) -> None:
    """禁用成员不发也不记成功。没有邮箱记 ok=false，且信里只有本人的地址和 token。"""
    ready = await _user(db, "张三", "zhangsan@example.com")
    silent = await _user(db, "李四", "lisi@example.com")
    no_mail = await _user(db, "王五", None)
    blank_mail = await _user(db, "赵六", "  ")
    stopped_user = await _user(db, "钱七", "qianqi@example.com", enabled=False)
    group = await _mcp_group(db, "办公")
    other = await _mcp_group(db, "别的组")
    await _member(db, group.id, "user", ready.id)
    await _member(db, group.id, "user", silent.id, enabled=False)
    await _member(db, group.id, "user", no_mail.id)
    await _member(db, group.id, "user", blank_mail.id)
    await _member(db, group.id, "user", stopped_user.id)
    ready_token = "zhangsan-mcp-token"
    silent_token = "lisi-mcp-token"
    other_token = "other-group-token"
    await _credential(db, ready.id, group.id, ready_token)
    await _credential(db, silent.id, group.id, silent_token)
    await _credential(db, no_mail.id, group.id, "wangwu-mcp-token")
    await _credential(db, stopped_user.id, group.id, "qianqi-mcp-token")
    await _credential(db, ready.id, other.id, other_token)
    before = await _credential_count(db)
    stored = await db.get(McpCredentialModel, (await _credential_row_id(db, ready.id, group.id)))
    assert stored is not None
    original_hash = stored.token_hash
    await _enable_smtp(db)

    await _mail(db).send_for_group(group.id)

    messages = _messages()
    assert len(messages) == 1
    assert messages[0]["To"] == "zhangsan@example.com"
    assert _body(messages[0]) == _expected_body(group.id, ready_token)
    assert silent_token not in _body(messages[0])
    assert other_token not in _body(messages[0])
    assert _PASSWORD not in _body(messages[0])
    assert ready_token not in str(messages[0]["Subject"])
    client = FakeSMTP.created[0]
    assert isinstance(client, FakeSMTP)
    assert not isinstance(client, FakeSMTPSSL)
    assert client.host == "smtp.example.com"
    assert client.port == 587
    assert client.started_tls is True
    assert client.login_args == ("smtp-user", _PASSWORD)
    assert client.quit_called is True

    rows = await _logs(db)
    assert [(row.user_id, row.group_id, row.channel, row.ok) for row in rows if row.ok] == [
        (ready.id, group.id, "group", True),
    ]
    failed = [row for row in rows if not row.ok]
    assert {row.user_id for row in failed} == {no_mail.id, blank_mail.id}
    assert all(row.channel == "group" and row.group_id == group.id for row in failed)
    assert all(row.reason == "没有邮箱" for row in failed)
    blob = " ".join(row.reason or "" for row in rows)
    assert ready_token not in blob
    assert _PASSWORD not in blob
    assert silent.id not in {row.user_id for row in rows}
    assert stopped_user.id not in {row.user_id for row in rows}
    assert await _credential_count(db) == before
    again = await db.get(McpCredentialModel, stored.id)
    assert again is not None
    assert again.token_hash == original_hash


async def _credential_row_id(db, user_id: int, group_id: int) -> int:
    row = (
        await db.execute(
            select(McpCredentialModel).where(
                McpCredentialModel.user_id == user_id,
                McpCredentialModel.group_id == group_id,
            )
        )
    ).scalar_one()
    return row.id


async def test_missing_credential_sends_nothing_and_does_not_issue(db) -> None:
    user = await _user(db, "张三", "zhangsan@example.com")
    group = await _mcp_group(db, "办公")
    await _member(db, group.id, "user", user.id)
    await _enable_smtp(db)

    await _mail(db).send_for_group(group.id)

    assert _messages() == []
    assert await _credential_count(db) == 0
    rows = await _logs(db)
    assert len(rows) == 1
    assert rows[0].ok is False
    assert rows[0].reason == "凭证不存在"
    assert rows[0].user_id == user.id
    assert rows[0].group_id == group.id


async def test_send_for_user_group_one_message_per_checked_mcp_group(db) -> None:
    """用户组被勾选且未禁用的每个 MCP 组各一封。禁用的勾选和不在组里的人不发。"""
    office = await _user(db, "张三", "zhangsan@example.com")
    stopped = await _user(db, "李四", "lisi@example.com", enabled=False)
    outsider = await _user(db, "王五", "wangwu@example.com")
    biz = await _biz_group(db, "研发")
    await _join(db, office.id, biz.id)
    await _join(db, stopped.id, biz.id)
    checked = await _mcp_group(db, "办公")
    second = await _mcp_group(db, "人事")
    unchecked = await _mcp_group(db, "财务")
    disabled_link = await _mcp_group(db, "停用勾选")
    await _member(db, checked.id, "group", biz.id, enabled=True)
    await _member(db, second.id, "group", biz.id, enabled=True)
    await _member(db, disabled_link.id, "group", biz.id, enabled=False)
    office_checked = "zhangsan-office"
    office_second = "zhangsan-hr"
    stopped_token = "lisi-office"
    outsider_token = "wangwu-finance"
    await _credential(db, office.id, checked.id, office_checked)
    await _credential(db, office.id, second.id, office_second)
    await _credential(db, stopped.id, checked.id, stopped_token)
    await _credential(db, outsider.id, unchecked.id, outsider_token)
    await _member(db, unchecked.id, "user", outsider.id)
    await _enable_smtp(db)

    await _mail(db).send_for_user_group(biz.id)

    bodies = {_body(message) for message in _messages()}
    assert bodies == {
        _expected_body(checked.id, office_checked),
        _expected_body(second.id, office_second),
    }
    assert all(message["To"] == "zhangsan@example.com" for message in _messages())
    rows = await _logs(db)
    assert {(row.user_id, row.group_id, row.channel, row.ok) for row in rows} == {
        (office.id, checked.id, "user_group", True),
        (office.id, second.id, "user_group", True),
    }
    assert stopped_token not in "".join(bodies)
    assert outsider_token not in "".join(bodies)


async def test_disabled_user_group_principal_is_skipped(db) -> None:
    person = await _user(db, "张三", "zhangsan@example.com")
    biz = await _biz_group(db, "研发", enabled=False)
    await _join(db, person.id, biz.id)
    group = await _mcp_group(db, "办公")
    await _member(db, group.id, "group", biz.id, enabled=True)
    await _credential(db, person.id, group.id, "zhangsan-mcp-token")
    await _enable_smtp(db)

    await _mail(db).send_for_group(group.id)
    await _mail(db).send_for_user_group(biz.id)

    assert _messages() == []
    assert await _logs(db) == []


async def test_send_for_user_one_message_per_allowed_group(db) -> None:
    """当前还能用的每个 MCP 组一封。停用的组、停用的成员和停用的用户组不算。"""
    person = await _user(db, "张三", "zhangsan@example.com")
    direct = await _mcp_group(db, "办公")
    via_group = await _mcp_group(db, "人事")
    closed = await _mcp_group(db, "财务", enabled=False)
    blocked = await _mcp_group(db, "停用成员")
    biz = await _biz_group(db, "研发")
    closed_biz = await _biz_group(db, "离职", enabled=False)
    await _join(db, person.id, biz.id)
    await _join(db, person.id, closed_biz.id)
    await _member(db, direct.id, "user", person.id)
    await _member(db, via_group.id, "group", biz.id)
    await _member(db, closed.id, "user", person.id)
    await _member(db, blocked.id, "user", person.id, enabled=False)
    parked = await _mcp_group(db, "停用用户组")
    await _member(db, parked.id, "group", closed_biz.id, enabled=True)
    direct_token = "zhangsan-office"
    group_token = "zhangsan-hr"
    closed_token = "zhangsan-finance"
    blocked_token = "zhangsan-blocked"
    parked_token = "zhangsan-parked"
    await _credential(db, person.id, direct.id, direct_token)
    await _credential(db, person.id, via_group.id, group_token)
    await _credential(db, person.id, closed.id, closed_token)
    await _credential(db, person.id, blocked.id, blocked_token)
    await _credential(db, person.id, parked.id, parked_token)
    await _enable_smtp(db)

    await _mail(db).send_for_user(person.id)

    bodies = {_body(message) for message in _messages()}
    assert bodies == {
        _expected_body(direct.id, direct_token),
        _expected_body(via_group.id, group_token),
    }
    rows = await _logs(db)
    assert {(row.group_id, row.channel, row.ok) for row in rows} == {
        (direct.id, "user", True),
        (via_group.id, "user", True),
    }
    joined = "".join(bodies)
    assert closed_token not in joined
    assert blocked_token not in joined
    assert parked_token not in joined

    person.enabled = False
    await db.flush()
    FakeSMTP.created = []
    await _mail(db).send_for_user(person.id)
    assert _messages() == []
    assert len(await _logs(db)) == 2


async def test_password_is_encrypted_and_blank_update_keeps_it(db) -> None:
    created = await _enable_smtp(db)
    stored = await db.get(SmtpConfigModel, created.id)
    assert stored is not None
    assert stored.password_encrypted
    assert _PASSWORD not in stored.password_encrypted
    assert CryptoUtil.decrypt(stored.password_encrypted) == _PASSWORD
    ciphertext = stored.password_encrypted

    listed = await _smtp(db).page(page_no=1, page_size=10)
    detail = await _smtp(db).detail(created.id)
    payload = listed.model_dump_json() + detail.model_dump_json()
    assert _PASSWORD not in payload
    assert ciphertext not in payload
    assert "password" not in detail.model_dump()

    updated = await _smtp(db).update(created.id, SmtpConfigUpdateSchema(password="", host="smtp2.example.com"))
    assert updated.host == "smtp2.example.com"
    again = await db.get(SmtpConfigModel, created.id)
    assert again is not None
    assert again.password_encrypted == ciphertext

    with pytest.raises(CustomException) as exc:
        await _smtp(db).create(
            SmtpConfigCreateSchema(
                enabled=True,
                host="smtp.example.com",
                port=25,
                password="another-secret",
                from_address="other@example.com",
                encryption="none",
            )
        )
    assert exc.value.status_code == 400
    assert "another-secret" not in exc.value.msg
    assert await db.scalar(select(func.count()).select_from(SmtpConfigModel)) == 1


async def test_test_send_does_not_write_mail_log(db) -> None:
    user = await _user(db, "张三", "zhangsan@example.com")
    group = await _mcp_group(db, "办公")
    token = "zhangsan-mcp-token"
    await _credential(db, user.id, group.id, token)
    created = await _enable_smtp(db, encryption="ssl")
    await _smtp(db).update(created.id, SmtpConfigUpdateSchema(enabled=False))

    await _smtp(db).send_test(to_address="admin@example.com")

    assert len(FakeSMTP.created) == 1
    assert isinstance(FakeSMTP.created[0], FakeSMTPSSL)
    assert FakeSMTP.created[0].started_tls is False
    assert len(_messages()) == 1
    body = _body(_messages()[0])
    assert _messages()[0]["To"] == "admin@example.com"
    assert token not in body
    assert _PASSWORD not in body
    assert "/mcp/" not in body
    assert await _logs(db) == []


async def test_smtp_failure_reason_omits_secrets(db) -> None:
    user = await _user(db, "张三", "zhangsan@example.com")
    group = await _mcp_group(db, "办公")
    await _member(db, group.id, "user", user.id)
    token = "zhangsan-mcp-token"
    await _credential(db, user.id, group.id, token)
    await _enable_smtp(db)

    await _mail(db, smtp_cls=BoomSMTP).send_for_group(group.id)

    rows = await _logs(db)
    assert len(rows) == 1
    assert rows[0].ok is False
    assert rows[0].reason == "发信失败"
    assert token not in (rows[0].reason or "")
    assert _PASSWORD not in (rows[0].reason or "")


async def test_mail_log_filters_omit_secrets(db) -> None:
    person = await _user(db, "张三", "zhangsan@example.com")
    other = await _user(db, "李四", None)
    biz = await _biz_group(db, "研发")
    await _join(db, person.id, biz.id)
    group = await _mcp_group(db, "办公")
    await _member(db, group.id, "user", person.id)
    await _member(db, group.id, "user", other.id)
    token = "zhangsan-mcp-token"
    await _credential(db, person.id, group.id, token)
    await _enable_smtp(db)
    await _mail(db).send_for_group(group.id)
    service = _mail(db)

    by_user = await service.page(page_no=1, page_size=10, search=MailLogQueryParam(user_id=person.id, ok=True))
    assert [item.user_id for item in by_user.items] == [person.id]
    by_group = await service.page(page_no=1, page_size=10, search=MailLogQueryParam(user_group_id=biz.id))
    assert {item.user_id for item in by_group.items} == {person.id}
    by_channel = await service.page(page_no=1, page_size=10, search=MailLogQueryParam(channel="group", group_id=group.id))
    assert len(by_channel.items) == 2
    failed = await service.page(page_no=1, page_size=10, search=MailLogQueryParam(ok=False))
    assert [item.reason for item in failed.items] == ["没有邮箱"]
    future = datetime.now(UTC) + timedelta(days=1)
    empty = await service.page(
        page_no=1,
        page_size=10,
        search=MailLogQueryParam(created_at_start=future, created_at_end=future + timedelta(hours=1)),
    )
    assert empty.items == []
    payload = by_channel.model_dump_json()
    assert token not in payload
    assert _PASSWORD not in payload
    assert "password" not in payload


async def test_connection_info_still_works_when_smtp_is_disabled(db) -> None:
    user = await _user(db, "张三", "zhangsan@example.com")
    group = await _mcp_group(db, "办公")
    token = "zhangsan-mcp-token"
    await _credential(db, user.id, group.id, token)
    await _enable_smtp(db, enabled=False)

    info = await McpCredentialService(_auth(), db).connection_info(user_id=user.id, group_id=group.id)

    assert info.streamable_http_url == f"/mcp/{group.id}"
    assert info.sse_url == f"/mcp/{group.id}/sse"
    assert info.messages_url == f"/mcp/{group.id}/messages"
    assert info.authorization == f"Authorization: Bearer {token}"
    assert await _logs(db) == []


async def test_none_encryption_does_not_call_starttls(db) -> None:
    user = await _user(db, "张三", "zhangsan@example.com")
    group = await _mcp_group(db, "办公")
    await _member(db, group.id, "user", user.id)
    await _credential(db, user.id, group.id, "zhangsan-mcp-token")
    created = await _enable_smtp(db, encryption="none")
    await _smtp(db).update(created.id, SmtpConfigUpdateSchema(username=""))

    await _mail(db).send_for_user(user.id)

    assert len(FakeSMTP.created) == 1
    assert FakeSMTP.created[0].started_tls is False
    assert FakeSMTP.created[0].login_args is None
    assert not isinstance(FakeSMTP.created[0], FakeSMTPSSL)
    assert _body(_messages()[0]) == _expected_body(group.id, "zhangsan-mcp-token")
