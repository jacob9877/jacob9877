import os

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import EmailStr

from app.models.user_models import RoleAndCondition

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


async def send_registration_email(
    invitee_email: EmailStr,
    inviter_first_name: str,
    inviter_last_name: str,
    registration_role_and_condition: RoleAndCondition,
):
    """
    Send an email with a link to register with our platform

    Args:
        invitee_email (str): email that the registration invite should be sent to (i.e. the recipient)
        inviter_first_name (str): first name of the user who is initiating the invite
        inviter_last_name (str): last name of the user who is initiating the invite
        registration_role_and_condition: role and condition the invitee should be directed to upon opening the registration link
    """

    registration_link = f"{os.environ['FRONTEND_URL']}/register?role={registration_role_and_condition.role.value}"

    if registration_role_and_condition.condition:
        registration_link += (
            f"?condition={registration_role_and_condition.condition.value}"
        )

    message = MessageSchema(
        subject="Registration Invite",
        recipients=[invitee_email],
        body=f"""
    <h3>Registration Invite</h3>
    <p>{inviter_first_name} {inviter_last_name} has invited you to join AI for Medical Outcomes.\n
        Click the link below to register:</p>
    <a href="{registration_link}">{registration_link}</a>
    """,
        subtype="html",
    )

    fm = FastMail(conf)
    await fm.send_message(message)
