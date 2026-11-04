"""可选的 SMTP 发信。缺主机、发件人或收件人时不创建发送函数，也不联网。"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any, Callable, Mapping, Optional


def build_review_email(sender: str, recipient: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "晨间复习"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    return message


def send_smtp_text(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    body: str,
    timeout_s: int = 10,
    smtp_factory: Optional[Callable[..., Any]] = None,
    smtp_ssl_factory: Optional[Callable[..., Any]] = None,
) -> None:
    message = build_review_email(sender, recipient, body)
    use_ssl = int(port) == 465
    factory = smtp_ssl_factory if use_ssl else smtp_factory
    if factory is None:
        factory = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with factory(host, int(port), timeout=timeout_s) as client:
        if not use_ssl:
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)


def sender_from_env(
    environ: Optional[Mapping[str, str]] = None,
    smtp_factory: Optional[Callable[..., Any]] = None,
    smtp_ssl_factory: Optional[Callable[..., Any]] = None,
) -> Optional[Callable[[str], None]]:
    env = os.environ if environ is None else environ
    host = str(env.get("SMTP_HOST", "")).strip()
    sender = str(env.get("SMTP_FROM", "")).strip()
    recipient = str(env.get("REVIEW_EMAIL_TO", "")).strip()
    if not host or not sender or not recipient:
        return None
    port_text = str(env.get("SMTP_PORT", "587") or "587").strip()
    try:
        port = int(port_text)
    except ValueError:
        return None
    username = str(env.get("SMTP_USERNAME", "")).strip()
    password = str(env.get("SMTP_PASSWORD", ""))

    def send(body: str) -> None:
        try:
            send_smtp_text(
                host=host,
                port=port,
                username=username,
                password=password,
                sender=sender,
                recipient=recipient,
                body=body,
                smtp_factory=smtp_factory,
                smtp_ssl_factory=smtp_ssl_factory,
            )
        except Exception as exc:
            message = str(exc)
            if password:
                message = message.replace(password, "***")
            raise RuntimeError(message) from exc

    return send
