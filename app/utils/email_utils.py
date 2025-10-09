import os

from dotenv import load_dotenv
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import EmailStr

load_dotenv()

DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

conf = ConnectionConfig(
    MAIL_USERNAME=os.environ["MAIL_USERNAME"],
    MAIL_PASSWORD=os.environ["MAIL_PASSWORD"],
    MAIL_FROM=os.environ["MAIL_FROM"],
    MAIL_PORT=int(os.environ["MAIL_PORT"]),
    MAIL_SERVER=os.environ["MAIL_SERVER"],
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def send_reset_email(email: EmailStr, token: str):
    reset_link = f"{os.environ['FRONTEND_URL']}/reset-password?token={token}"

    if DEV_MODE:
        print(f"[DEV] Password reset link for {email}: {reset_link}")
        return

    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        body=f"""
        <h3>Password Reset Request</h3>
        <p>Click the link below to reset your password:</p>
        <a href="{reset_link}">{reset_link}</a>
        <p>This link will expire in 15 minutes.</p>
        """,
        subtype="html",
    )

    fm = FastMail(conf)
    await fm.send_message(message)
