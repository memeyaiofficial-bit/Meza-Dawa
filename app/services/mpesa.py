"""Safaricom Daraja M-Pesa STK Push integration.

Credentials stay on the backend. The frontend only receives the purchase ID
and Daraja's checkout request ID; payment is credited only after the callback.
"""
import base64
from datetime import datetime
import httpx
from app.config import get_settings

settings = get_settings()


def normalize_phone(phone: str) -> str:
    value = phone.strip().replace(" ", "").replace("-", "")
    if value.startswith("+254"):
        value = value[1:]
    elif value.startswith("07") or value.startswith("01"):
        value = "254" + value[1:]
    if not (value.startswith("254") and len(value) == 12 and value.isdigit()):
        raise ValueError("Enter a valid Kenyan M-Pesa number, e.g. 0712345678.")
    return value


async def get_access_token() -> str:
    if not settings.MPESA_CONSUMER_KEY or not settings.MPESA_CONSUMER_SECRET:
        raise RuntimeError("M-Pesa credentials are not configured on the server.")
    base = settings.MPESA_BASE_URL.rstrip("/")
    auth = base64.b64encode(
        f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode()
    ).decode()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{base}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {auth}"},
        )
        response.raise_for_status()
        data = response.json()
        return data["access_token"]


async def initiate_stk_push(phone: str, amount: int, account_reference: str) -> dict:
    phone = normalize_phone(phone)
    token = await get_access_token()
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    raw_password = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": settings.MPESA_TRANSACTION_TYPE,
        "Amount": amount,
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference[:12],
        "TransactionDesc": "Meza Dawa SMS"[:13],
    }

    base = settings.MPESA_BASE_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{base}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()
