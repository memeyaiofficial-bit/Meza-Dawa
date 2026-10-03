"""
All environment configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Doctor registration gate
    DOCTOR_ACCESS_CODE: str = "DOC2026"
    PHARMACY_ACCESS_CODE: str = "PH2026"

    # TalkSasa SMS
    TALKSASA_API_KEY: str = ""
    TALKSASA_SENDER_ID: str = "MezaDawa"
    TALKSASA_API_URL: str = "https://bulksms.talksasa.com/api/v3/sms/send"

    # M-Pesa Daraja (all credentials stay server-side)
    MPESA_BASE_URL: str = "https://sandbox.safaricom.co.ke"
    MPESA_CONSUMER_KEY: str = ""
    MPESA_CONSUMER_SECRET: str = ""
    MPESA_SHORTCODE: str = ""
    MPESA_PASSKEY: str = ""
    MPESA_CALLBACK_URL: str = ""
    MPESA_TRANSACTION_TYPE: str = "CustomerPayBillOnline"
    SMS_TOKEN_PACKAGE_PRICE: int = 30
    SMS_TOKEN_PACKAGE_SIZE: int = 100


    # App
    APP_ENV: str = "development"
    FRONTEND_URL: str = "http://localhost:5500"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()