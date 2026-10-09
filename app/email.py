"""Email notification support for ResolveAI."""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from .config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FROM, EMAIL_TO

logger = logging.getLogger(__name__)


async def send_email(
    subject: str,
    body: str,
    to: Optional[str] = None,
    html: Optional[str] = None,
) -> bool:
    """Send an email notification. Returns True if sent successfully."""
    if not EMAIL_HOST or not EMAIL_TO:
        logger.debug("Email not configured, skipping notification")
        return False

    to_addr = to or EMAIL_TO

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_addr

    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=EMAIL_HOST,
            port=EMAIL_PORT,
            username=EMAIL_USER or None,
            password=EMAIL_PASSWORD or None,
            start_tls=True,
        )
        logger.info(f"Email sent: {subject} -> {to_addr}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send email: {e}")
        return False


async def notify_ticket_created(
    ticket_id: int,
    subject: str,
    customer_name: str,
    priority: str,
    category: str,
) -> bool:
    """Send notification when a new ticket is created."""
    body = f"""
New support ticket #{ticket_id} has been created.

Customer: {customer_name}
Subject: {subject}
Priority: {priority}
Category: {category}

Please review and respond within the SLA target.
"""
    html = f"""
<html><body>
<h3>New Support Ticket #{ticket_id}</h3>
<p><b>Customer:</b> {customer_name}</p>
<p><b>Subject:</b> {subject}</p>
<p><b>Priority:</b> {priority}</p>
<p><b>Category:</b> {category}</p>
<p>Please review and respond within the SLA target.</p>
</body></html>
"""
    return await send_email(
        subject=f"[ResolveAI] New Ticket #{ticket_id}: {subject}",
        body=body,
        html=html,
    )


async def notify_sla_breach(
    ticket_id: int,
    subject: str,
    customer_name: str,
    priority: str,
    hours_overdue: float,
) -> bool:
    """Send notification when a ticket breaches SLA."""
    body = f"""
SLA BREACH ALERT: Ticket #{ticket_id}

Customer: {customer_name}
Subject: {subject}
Priority: {priority}
Hours overdue: {hours_overdue:.1f}

Immediate action required!
"""
    html = f"""
<html><body>
<h3 style="color: red;">SLA BREACH: Ticket #{ticket_id}</h3>
<p><b>Customer:</b> {customer_name}</p>
<p><b>Subject:</b> {subject}</p>
<p><b>Priority:</b> {priority}</p>
<p><b>Hours overdue:</b> {hours_overdue:.1f}</p>
<p><b>Immediate action required!</b></p>
</body></html>
"""
    return await send_email(
        subject=f"[ResolveAI] SLA BREACH: Ticket #{ticket_id}",
        body=body,
        html=html,
    )


async def notify_ticket_resolved(
    ticket_id: int,
    subject: str,
    customer_name: str,
) -> bool:
    """Send notification when a ticket is resolved."""
    body = f"""
Ticket #{ticket_id} has been resolved.

Customer: {customer_name}
Subject: {subject}
"""
    return await send_email(
        subject=f"[ResolveAI] Ticket #{ticket_id} Resolved",
        body=body,
    )
