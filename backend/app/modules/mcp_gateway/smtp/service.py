import smtplib

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schema import AuthSchema, PageResultSchema
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.utils.common_util import search_to_dict
from app.utils.crypto_util import CryptoUtil

from .client import deliver
from .crud import SmtpConfigCRUD
from .model import SmtpConfigModel
from .schema import SmtpConfigCreateSchema, SmtpConfigOutSchema, SmtpConfigQueryParam, SmtpConfigUpdateSchema

_ENCRYPTIONS = {"none", "starttls", "ssl"}


class SmtpConfigService:
    """保存唯一的 SMTP 配置，并发送一封不含连接信息的测试信。"""

    def __init__(
        self,
        auth: AuthSchema,
        db: AsyncSession,
        *,
        smtp_cls: type = smtplib.SMTP,
        smtp_ssl_cls: type = smtplib.SMTP_SSL,
    ) -> None:
        self.auth = auth
        self.db = db
        self.smtp_cls = smtp_cls
        self.smtp_ssl_cls = smtp_ssl_cls

    async def page(
        self,
        page_no: int,
        page_size: int,
        search: SmtpConfigQueryParam | None = None,
        order_by: list[dict[str, str]] | None = None,
    ) -> PageResultSchema[SmtpConfigOutSchema]:
        offset = (page_no - 1) * page_size
        return await SmtpConfigCRUD(self.auth, self.db).page(
            offset=offset,
            limit=page_size,
            order_by=order_by or [{"id": "asc"}],
            search=search_to_dict(search, {}),
            out_schema=SmtpConfigOutSchema,
        )

    async def detail(self, config_id: int) -> SmtpConfigOutSchema:
        return await SmtpConfigCRUD(self.auth, self.db).get_or_404(
            id=config_id,
            msg="SMTP 配置不存在",
            out_schema=SmtpConfigOutSchema,
        )

    async def create(self, data: SmtpConfigCreateSchema) -> SmtpConfigOutSchema:
        current = await SmtpConfigCRUD(self.auth, self.db).get()
        if current is not None:
            raise CustomException(msg="SMTP 配置已存在")
        try:
            obj = await SmtpConfigCRUD(self.auth, self.db).create(data=self._payload(data))
        except IntegrityError as exc:
            raise CustomException(msg="SMTP 配置已存在") from exc
        return SmtpConfigOutSchema.model_validate(obj)

    async def update(self, config_id: int, data: SmtpConfigUpdateSchema) -> SmtpConfigOutSchema:
        current = await SmtpConfigCRUD(self.auth, self.db).get(id=config_id)
        if current is None:
            raise CustomException(msg="SMTP 配置不存在")
        payload = data.model_dump(exclude_unset=True)
        password = payload.pop("password", None)
        if isinstance(password, str) and password.strip():
            payload["password_encrypted"] = CryptoUtil.encrypt(password.strip())
        if not payload:
            return SmtpConfigOutSchema.model_validate(current)
        obj = await SmtpConfigCRUD(self.auth, self.db).update(id=config_id, data=payload)
        return SmtpConfigOutSchema.model_validate(obj)

    async def send_test(self, to_address: str) -> None:
        """确认连接可用。未启用也可以发。不写发信记录。"""
        config = await self._configured()
        self.deliver_message(config, to_address, "SMTP 测试", "SMTP 测试邮件")

    async def load_for_connection_mail(self) -> SmtpConfigModel:
        """三个连接信息发送入口。未启用或不完整时直接拒绝，调用方还没写记录。"""
        config = await SmtpConfigCRUD(self.auth, self.db).get()
        if config is None or not config.enabled:
            raise CustomException(msg="SMTP 未启用")
        if not self._complete(config):
            raise CustomException(msg="SMTP 配置不完整")
        return config

    def deliver_message(self, config: SmtpConfigModel, to_address: str, subject: str, body: str) -> None:
        try:
            deliver(
                host=config.host,
                port=config.port,
                encryption=config.encryption,
                username=config.username,
                password=CryptoUtil.decrypt(config.password_encrypted) if config.password_encrypted else "",
                from_address=config.from_address,
                from_name=config.from_name,
                to_address=to_address,
                subject=subject,
                body=body,
                smtp_cls=self.smtp_cls,
                smtp_ssl_cls=self.smtp_ssl_cls,
            )
        except CustomException:
            raise
        except Exception:
            logger.warning("SMTP 发信失败")
            raise CustomException(msg="发信失败") from None

    async def _configured(self) -> SmtpConfigModel:
        config = await SmtpConfigCRUD(self.auth, self.db).get()
        if config is None or not self._complete(config):
            raise CustomException(msg="SMTP 未配置")
        return config

    @staticmethod
    def _complete(config: SmtpConfigModel) -> bool:
        return bool(config.host and config.port and config.from_address and config.encryption in _ENCRYPTIONS)

    @staticmethod
    def _payload(data: SmtpConfigCreateSchema) -> dict:
        return {
            "enabled": data.enabled,
            "host": data.host,
            "port": data.port,
            "username": data.username,
            "password_encrypted": CryptoUtil.encrypt(data.password) if data.password else "",
            "from_address": data.from_address,
            "from_name": data.from_name,
            "encryption": data.encryption,
        }
