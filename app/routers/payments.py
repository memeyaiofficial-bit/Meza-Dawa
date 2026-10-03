from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.config import get_settings
from app.dependencies import get_db, require_patient
from app.models.sms_purchase import SmsPurchase
from app.models.sms_transaction import SmsTransaction
from app.models.user import User
from app.schemas.sms_purchase import SmsPurchaseCreate, SmsPurchaseOut
from app.services.mpesa import initiate_stk_push, normalize_phone

router = APIRouter(prefix="/payments", tags=["Payments"])
settings = get_settings()


@router.post("/sms-tokens", response_model=SmsPurchaseOut, status_code=201)
async def buy_sms_tokens(payload: SmsPurchaseCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    try:
        phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    purchase = SmsPurchase(user_id=current_user.id, phone=phone, amount=settings.SMS_TOKEN_PACKAGE_PRICE,
                           tokens=settings.SMS_TOKEN_PACKAGE_SIZE, status="pending")
    db.add(purchase); db.commit(); db.refresh(purchase)
    try:
        result = await initiate_stk_push(phone, purchase.amount, f"MD{purchase.id[:10]}")
    except Exception as exc:
        purchase.status = "failed"; purchase.result_description = str(exc); db.commit()
        raise HTTPException(status_code=502, detail="Unable to start the M-Pesa payment. Check the server payment configuration.")

    purchase.merchant_request_id = result.get("MerchantRequestID")
    purchase.checkout_request_id = result.get("CheckoutRequestID")
    if str(result.get("ResponseCode", "")) != "0" or not purchase.checkout_request_id:
        purchase.status = "failed"
        purchase.result_description = result.get("ResponseDescription") or result.get("errorMessage") or "M-Pesa rejected the payment request."
    else:
        purchase.result_description = result.get("ResponseDescription") or "STK Push sent. Enter your M-Pesa PIN to continue."
    db.commit(); db.refresh(purchase)
    return purchase


@router.get("/sms-tokens/history", response_model=list[SmsPurchaseOut])
def sms_purchase_history(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return db.query(SmsPurchase).filter(SmsPurchase.user_id == current_user.id).order_by(SmsPurchase.created_at.desc()).limit(50).all()


@router.get("/sms-tokens/{purchase_id}", response_model=SmsPurchaseOut)
def get_sms_purchase(purchase_id: str, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    purchase = db.query(SmsPurchase).filter(SmsPurchase.id == purchase_id, SmsPurchase.user_id == current_user.id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.post("/mpesa/callback", include_in_schema=False)
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    stk = payload.get("Body", {}).get("stkCallback", {})
    checkout_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")
    if not checkout_id:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    purchase = db.query(SmsPurchase).filter(SmsPurchase.checkout_request_id == checkout_id).with_for_update().first()
    if not purchase:
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    if purchase.status == "paid":
        return {"ResultCode": 0, "ResultDesc": "Already processed"}

    purchase.result_code = str(result_code) if result_code is not None else None
    purchase.result_description = stk.get("ResultDesc")
    if str(result_code) == "0":
        items = {item.get("Name"): item.get("Value") for item in stk.get("CallbackMetadata", {}).get("Item", [])}
        receipt = items.get("MpesaReceiptNumber")
        purchase.mpesa_receipt = str(receipt) if receipt else None
        purchase.status = "paid"
        purchase.completed_at = datetime.now(timezone.utc)
        current_user = db.query(User).filter(User.id == purchase.user_id).with_for_update().first()
        if current_user is not None:
            current_user.sms_tokens = (current_user.sms_tokens or 0) + purchase.tokens
    else:
        purchase.status = "failed"
    db.commit()
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.get("/sms-transactions")
def sms_transactions(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    rows = db.query(SmsTransaction).filter(SmsTransaction.user_id == current_user.id).order_by(SmsTransaction.created_at.desc()).limit(100).all()
    return [
        {"id": r.id, "recipient": r.recipient, "message_type": r.message_type, "tokens_used": r.tokens_used,
         "provider": r.provider, "provider_message_id": r.provider_message_id, "status": r.status,
         "error_message": r.error_message, "created_at": r.created_at, "sent_at": r.sent_at}
        for r in rows
    ]
