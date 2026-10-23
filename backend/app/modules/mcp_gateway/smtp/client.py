"""用标准库 smtplib 发信。调用方传入 SMTP 类，测试因此不必连网。"""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.exceptions import CustomException

_ENCRYPTIONS = {"none", "starttls", "ssl"}


def deliver(
    *,
    host: str,
    port: int,
    encryption: str,
    username: str | None,
    password: str,
    from_address: str,
    from_name: str | None,
    to_address: str,
    subject: str,
    body: str,
    smtp_cls: type = smtplib.SMTP,
    smtp_ssl_cls: type = smtplib.SMTP_SSL,
) -> None:
    """发出一封纯文本邮件。失败时不把账号、密码或正文放进异常信息。"""
    if encryption not in _ENCRYPTIONS:
        raise CustomException(msg="加密方式无效")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((from_name, from_address)) if from_name else from_address
    message["To"] = to_address
    message.set_content(body)
    client = smtp_ssl_cls(host, port, timeout=30) if encryption == "ssl" else smtp_cls(host, port, timeout=30)
    try:
        if encryption == "starttls":
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)
    finally:
        try:
            client.quit()
        except Exception:
            pass
