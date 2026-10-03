"""TalkSasa SMS integration plus token-accounting helpers."""
import logging
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.user import User
from app.models.sms_transaction import SmsTransaction

settings = get_settings()
logger = logging.getLogger(__name__)


def normalize_sms_phone(phone: str) -> str:
    value = (phone or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("+"):
        value = value[1:]
    elif value.startswith("07") or value.startswith("01"):
        value = "254" + value[1:]
    elif not value.startswith("254"):
        value = "254" + value
    if not (value.startswith("254") and len(value) == 12 and value.isdigit()):
        raise ValueError("Enter a valid Kenyan phone number.")
    return value


async def send_sms_talksasa(phone: str, message: str) -> tuple[bool, str | None, str | None]:
    """Return (accepted, provider_message_id, error)."""
    if not settings.TALKSASA_API_KEY:
        return False, None, "TALKSASA_API_KEY is not configured on the server."
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.TALKSASA_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.TALKSASA_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "recipient": phone,
                    "sender_id": settings.TALKSASA_SENDER_ID,
                    "type": "plain",
                    "message": message,
                },
            )
            try:
                body = resp.json()
            except ValueError:
                body = {}
            if not resp.is_success:
                return False, None, body.get("message") or f"TalkSasa HTTP {resp.status_code}"
            accepted = str(body.get("status", "")).lower() in {"success", "accepted", "ok"}
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            provider_id = body.get("message_id") or body.get("messageId") or body.get("id") or data.get("message_id") or data.get("messageId") or data.get("id")
            if accepted:
                logger.info("TalkSasa accepted SMS to %s", phone)
                return True, str(provider_id) if provider_id else None, None
            return False, str(provider_id) if provider_id else None, body.get("message") or body.get("error") or "TalkSasa rejected the SMS."
    except httpx.HTTPError as exc:
        logger.error("TalkSasa HTTP error for %s: %s", phone, exc)
        return False, None, str(exc)


async def send_sms_with_token(
    db: Session,
    user_id: str,
    phone: str,
    message: str,
    message_type: str = "reminder",
) -> tuple[bool, SmsTransaction]:
    """Reserve one token, send through TalkSasa, then finalise the ledger.

    The user row is locked while the token is reserved, preventing concurrent
    reminders from spending the same available token. A failed provider call
    restores the reserved token.
    """
    phone = normalize_sms_phone(phone)
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise ValueError("Patient account not found.")
    if (user.sms_tokens or 0) < 1:
        tx = SmsTransaction(user_id=user_id, recipient=phone, message_type=message_type, status="rejected", tokens_used=0, error_message="Insufficient SMS tokens")
        db.add(tx)
        db.commit()
        return False, tx

    # Temporary reservation: balance is reduced before the external request,
    # but is restored immediately if TalkSasa does not accept the message.
    user.sms_tokens -= 1
    tx = SmsTransaction(user_id=user_id, recipient=phone, message_type=message_type, status="pending", tokens_used=1)
    db.add(tx)
    db.commit()
    db.refresh(tx)

    ok, provider_id, error = await send_sms_talksasa(phone, message)
    tx.provider_message_id = provider_id
    tx.status = "sent" if ok else "failed"
    tx.error_message = error
    tx.sent_at = datetime.now(timezone.utc) if ok else None
    if not ok:
        locked_user = db.query(User).filter(User.id == user_id).with_for_update().first()
        if locked_user:
            locked_user.sms_tokens = (locked_user.sms_tokens or 0) + 1
    db.commit()
    db.refresh(tx)
    return ok, tx


async def send_sms(phone: str, message: str) -> bool:
    """Low-level send kept for non-token system uses."""
    phone = normalize_sms_phone(phone)
    ok, _, _ = await send_sms_talksasa(phone, message)
    return ok


def reminder_message(patient_name: str, medicine: str | None = None) -> str:
    base = f"Hi {patient_name}, this is your Meza Dawa medication reminder."
    if medicine:
        base += f" Please take your {medicine}."
    base += " Log it at mezadawa.com. Stay healthy!"
    return base


def caregiver_reminder_message(caregiver_name: str, patient_name: str, medicine: str | None = None) -> str:
    base = f"Hi {caregiver_name}, please remind {patient_name} to take their medication."
    if medicine:
        base += f" Medicine: {medicine}."
    return base + " Meza Dawa."


def urgent_note_message(patient_name: str, doctor_name: str) -> str:
    return f"Hi {patient_name}, {doctor_name} has sent you an urgent message on Meza Dawa. Please log in at mezadawa.com to read it."
