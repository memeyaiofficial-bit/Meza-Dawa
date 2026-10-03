# Meza Dawa

Medication adherence and care-coordination platform for patients, doctors and pharmacies.

## Stack
- Frontend: HTML/CSS/JavaScript
- Backend: FastAPI
- Database: PostgreSQL
- Migrations: Alembic
- M-Pesa: Safaricom Daraja STK Push
- SMS: TalkSasa REST API
- Scheduler: APScheduler

## Local testing in PyCharm

1. Create a PostgreSQL database named `meza_dawa`.
2. Copy `.env.example` to `.env`.
3. Set `DATABASE_URL` and a strong random `SECRET_KEY`.
4. Install dependencies:
   `pip install -r requirements.txt`
5. Run migrations:
   `alembic upgrade head`
6. Start the API from the project root:
   `uvicorn app.main:app --reload --port 8000`
7. Serve the frontend over HTTP (do not open HTML files directly). Use PyCharm's static server or another local server on port 5500.
8. Open `portal.html` and register/login.

`config.js` points localhost frontends to `http://localhost:8000`. For a deployed frontend, set `window.MEZA_DAWA_API` to the deployed API URL.

## SMS token system

The SMS balance is now fully backend-controlled.

### Buying tokens
1. Patient enters an M-Pesa number in **Buy SMS Tokens**.
2. Frontend calls `POST /payments/sms-tokens`.
3. Backend creates a pending purchase and starts a Daraja STK Push.
4. Safaricom calls `POST /payments/mpesa/callback` after the customer's PIN decision.
5. Only `ResultCode = 0` credits the configured token package.
6. The frontend polls `GET /payments/sms-tokens/{purchase_id}` and refreshes the balance.

Default package: **KSh 30 = 100 SMS tokens**.

### Sending SMS
Every patient SMS is now routed through the backend token service:

`Reminder due → lock patient balance → reserve 1 token → TalkSasa → accepted = SMS ledger SENT and token remains spent; failure = token restored`

This applies to:
- medication reminder SMS
- caregiver reminder SMS
- manual **Test SMS** sends
- urgent doctor-note SMS

The backend records each attempt in `sms_transactions`, including recipient, message type, token count, provider, provider message ID, status, errors and timestamps.

Patients can read the persisted SMS history at:
- `GET /reminders/sms-log`
- `GET /payments/sms-transactions`

### TalkSasa configuration
Get the API key and approved sender ID from your TalkSasa SMS account. TalkSasa's current public guidance describes REST API access for transactional/2FA messaging and recommends storing API credentials in environment variables rather than source code. urlTalkSasa Bulk SMS API guidehttps://talksasa.com/guides/bulk-sms-kenya-api-guide-businesses

Set these in `.env`:
- `TALKSASA_API_KEY`
- `TALKSASA_SENDER_ID`
- `TALKSASA_API_URL` (default: `https://bulksms.talksasa.com/api/v3/sms/send`)

Never put the TalkSasa key in HTML, `script.js`, `config.js`, or any frontend bundle.

## M-Pesa configuration

For sandbox testing use the Daraja sandbox base URL. Before production, replace it with the production Daraja URL and use production credentials.

Required backend-only variables:
- `MPESA_BASE_URL`
- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_SHORTCODE`
- `MPESA_PASSKEY`
- `MPESA_CALLBACK_URL`
- `MPESA_TRANSACTION_TYPE`
- `SMS_TOKEN_PACKAGE_PRICE`
- `SMS_TOKEN_PACKAGE_SIZE`

`MPESA_CALLBACK_URL` must be a publicly reachable HTTPS endpoint in production.

## Database migration

The SMS transaction ledger is added by the latest Alembic revision:

`d4e5f6a7b8c9_add_sms_transactions.py`

Run:

```bash
alembic upgrade head
```

## Production checklist

- Use a strong unique `SECRET_KEY`.
- Keep `.env` out of Git.
- Use PostgreSQL.
- Run `alembic upgrade head` during deployment.
- Configure a public HTTPS M-Pesa callback URL.
- Configure a valid TalkSasa API key and approved sender ID.
- Test M-Pesa callbacks before enabling real payments.
- Test SMS delivery using a real Kenyan number before launch.
- Monitor `sms_transactions` and `sms_purchases` for failed or pending transactions.
