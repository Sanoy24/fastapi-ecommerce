"""
Email service — pluggable SMTP implementation.

Uses aiosmtplib for async delivery. Set SMTP_USER and SMTP_PASSWORD in .env.
If SMTP credentials are not configured, emails are logged to the console instead
(useful for local development without a mail provider).
"""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.core.config import settings
from app.core.logger import logger

try:
    import aiosmtplib  # type: ignore

    _SMTP_AVAILABLE = True
except ImportError:
    _SMTP_AVAILABLE = False
    logger.warning(
        "aiosmtplib not installed — emails will be logged only. "
        "Install with: pip install aiosmtplib"
    )


async def send_email(
    to_address: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> None:
    """
    Send a transactional email.

    Falls back to console logging when SMTP is not configured or aiosmtplib
    is not installed, so the app keeps working in development.
    """
    if not settings.SMTP_USER or not _SMTP_AVAILABLE:
        logger.info(
            f"[EMAIL STUB] To: {to_address} | Subject: {subject}\n{text_body or html_body}"
        )
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_ADDRESS or settings.SMTP_USER}>"
    message["To"] = to_address

    if text_body:
        message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Email sent to {to_address}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_address}: {e}")
        # Do not raise — email failures should not break the HTTP response


async def send_password_reset_email(to_address: str, reset_token: str) -> None:
    """Send a password-reset link to the user."""
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    html_body = f"""
    <html><body>
    <h2>Password Reset Request</h2>
    <p>You requested a password reset for your account. Click the link below to set a new password:</p>
    <p><a href="{reset_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
        Reset Password
    </a></p>
    <p>This link expires in <strong>15 minutes</strong>.</p>
    <p>If you did not request this, you can safely ignore this email.</p>
    </body></html>
    """
    text_body = (
        f"Password Reset Request\n\nReset your password here: {reset_url}\n"
        f"This link expires in 15 minutes.\n"
        f"If you did not request this, ignore this email."
    )
    await send_email(
        to_address=to_address,
        subject="Reset your password",
        html_body=html_body,
        text_body=text_body,
    )


async def send_order_confirmation_email(
    to_address: str, order_number: str, total_amount: float
) -> None:
    """Send an order confirmation email."""
    html_body = f"""
    <html><body>
    <h2>Order Confirmed! 🎉</h2>
    <p>Thank you for your purchase. Your order <strong>#{order_number}</strong> has been placed.</p>
    <p><strong>Total:</strong> ${total_amount:.2f}</p>
    <p>We'll notify you when your order ships.</p>
    </body></html>
    """
    text_body = (
        f"Order Confirmed!\n\nOrder #{order_number} has been placed.\n"
        f"Total: ${total_amount:.2f}\n"
        f"We'll notify you when your order ships."
    )
    await send_email(
        to_address=to_address,
        subject=f"Order #{order_number} Confirmed",
        html_body=html_body,
        text_body=text_body,
    )


async def send_order_shipped_email(
    to_address: str, order_number: str, tracking_number: str, carrier: str
) -> None:
    """Send an order dispatch/shipping email."""
    html_body = f"""
    <html><body>
    <h2>Your Order is on the way! 🚚</h2>
    <p>Great news! Your order <strong>#{order_number}</strong> has shipped.</p>
    <p><strong>Carrier:</strong> {carrier}</p>
    <p><strong>Tracking Number:</strong> {tracking_number}</p>
    </body></html>
    """
    text_body = (
        f"Your Order is on the way!\n\nOrder #{order_number} has shipped.\n"
        f"Carrier: {carrier}\n"
        f"Tracking Number: {tracking_number}\n"
    )
    await send_email(
        to_address=to_address,
        subject=f"Order #{order_number} Shipped",
        html_body=html_body,
        text_body=text_body,
    )

async def send_verification_email(to_address: str, verification_token: str) -> None:
    """Send an email verification link to the user."""
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

    html_body = f"""
    <html><body>
    <h2>Welcome to FastAPI E-Commerce!</h2>
    <p>Please verify your email address by clicking the link below:</p>
    <p><a href="{verify_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
        Verify Email
    </a></p>
    <p>If you did not create an account, you can safely ignore this email.</p>
    </body></html>
    """
    text_body = (
        f"Welcome to FastAPI E-Commerce!\n\nVerify your email here: {verify_url}\n"
        f"If you did not create an account, ignore this email."
    )
    await send_email(
        to_address=to_address,
        subject="Verify your email address",
        html_body=html_body,
        text_body=text_body,
    )


async def send_guest_order_claim_email(to_address: str, order_number: str, claim_token: str) -> None:
    """Send a guest a link that attaches their order to an account.

    Sent on request (POST /order/guest/request-claim-link), not
    automatically at checkout — mirrors the password-reset request/consume
    shape rather than baking a sensitive token into every order
    confirmation email regardless of whether the guest ever wants an account.
    """
    claim_url = f"{settings.FRONTEND_URL}/claim-order?token={claim_token}"

    html_body = f"""
    <html><body>
    <h2>Save order #{order_number} to an account</h2>
    <p>Create or sign in to an account to track this order and any future ones in one place:</p>
    <p><a href="{claim_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
        Save This Order
    </a></p>
    <p>This link expires in 30 days. If you didn't request this, you can safely ignore this email.</p>
    </body></html>
    """
    text_body = (
        f"Save order #{order_number} to an account\n\n"
        f"Save this order to an account here: {claim_url}\n"
        f"This link expires in 30 days.\n"
        f"If you didn't request this, ignore this email."
    )
    await send_email(
        to_address=to_address,
        subject=f"Save your order #{order_number} to an account",
        html_body=html_body,
        text_body=text_body,
    )


async def send_abandoned_cart_email(to_address: str, item_count: int) -> None:
    """Remind a customer about items still sitting in their cart.

    Sent by app.workers.arq_worker.detect_abandoned_carts_task, which runs
    twice a day and only ever notifies a given cart once per abandonment
    (see Cart.abandoned_email_sent_at) — this function itself sends
    unconditionally each time it's called.
    """
    cart_url = f"{settings.FRONTEND_URL}/cart"
    item_word = "item" if item_count == 1 else "items"

    html_body = f"""
    <html><body>
    <h2>You left something behind 🛒</h2>
    <p>You have <strong>{item_count} {item_word}</strong> waiting in your cart.</p>
    <p><a href="{cart_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
        Return to Your Cart
    </a></p>
    <p>If you no longer want these items, you can safely ignore this email.</p>
    </body></html>
    """
    text_body = (
        f"You left something behind\n\n"
        f"You have {item_count} {item_word} waiting in your cart.\n"
        f"Return to your cart: {cart_url}\n"
        f"If you no longer want these items, ignore this email."
    )
    await send_email(
        to_address=to_address,
        subject="You left something in your cart",
        html_body=html_body,
        text_body=text_body,
    )


async def send_back_in_stock_email(to_address: str, product_name: str, product_slug: str) -> None:
    """Notify a customer that an item they subscribed to is available
    again. Sent by app.workers.arq_worker.process_outbox_events_task for
    "product.back_in_stock" outbox events — see
    app.services.back_in_stock_service.notify_back_in_stock_subscribers
    for where those get written.
    """
    product_url = f"{settings.FRONTEND_URL}/products/{product_slug}"

    html_body = f"""
    <html><body>
    <h2>{product_name} is back in stock! 🎉</h2>
    <p>Good news — an item you were waiting on is available again.</p>
    <p><a href="{product_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
        View {product_name}
    </a></p>
    <p>Stock can run out again, so it's worth grabbing it soon.</p>
    </body></html>
    """
    text_body = (
        f"{product_name} is back in stock!\n\n"
        f"An item you were waiting on is available again: {product_url}\n"
        f"Stock can run out again, so it's worth grabbing it soon."
    )
    await send_email(
        to_address=to_address,
        subject=f"{product_name} is back in stock!",
        html_body=html_body,
        text_body=text_body,
    )


async def send_price_drop_email(
    to_address: str, product_name: str, product_slug: str, old_price: float, new_price: float
) -> None:
    """Notify a customer that a product they subscribed to has dropped in
    price. Sent by app.workers.arq_worker.process_outbox_events_task for
    "product.price_drop" outbox events — see
    app.services.price_drop_service.notify_price_drop_subscribers for where
    those get written.
    """
    product_url = f"{settings.FRONTEND_URL}/products/{product_slug}"

    html_body = f"""
    <html><body>
    <h2>Price drop on {product_name}! 🎉</h2>
    <p>Good news — an item you were watching just got cheaper: <s>${old_price:.2f}</s> now ${new_price:.2f}.</p>
    <p><a href="{product_url}" style="background:#4F46E5;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;">
        View {product_name}
    </a></p>
    <p>Prices can change again, so it's worth grabbing it soon.</p>
    </body></html>
    """
    text_body = (
        f"Price drop on {product_name}!\n\n"
        f"An item you were watching just got cheaper: ${old_price:.2f} -> ${new_price:.2f}\n"
        f"{product_url}\n"
        f"Prices can change again, so it's worth grabbing it soon."
    )
    await send_email(
        to_address=to_address,
        subject=f"Price drop on {product_name}!",
        html_body=html_body,
        text_body=text_body,
    )
