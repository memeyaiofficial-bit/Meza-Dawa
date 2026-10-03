from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.dependencies import get_db, require_patient
from app.models.reminder import ReminderSchedule
from app.models.user import User
from app.models.medication_log import MedicationLog
from app.schemas.reminder import ReminderScheduleCreate, ReminderScheduleOut, ReminderScheduleUpdate
from app.services.sms import send_sms_with_token, reminder_message, caregiver_reminder_message

router = APIRouter(prefix="/reminders", tags=["Reminders"])

@router.get("/me", response_model=ReminderScheduleOut | None)
def get_my_reminder(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return db.query(ReminderSchedule).filter(ReminderSchedule.patient_id == current_user.id).first()

@router.post("/me", response_model=ReminderScheduleOut, status_code=status.HTTP_201_CREATED)
def create_or_replace_reminder(payload: ReminderScheduleCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    schedule = db.query(ReminderSchedule).filter(ReminderSchedule.patient_id == current_user.id).first()
    if schedule:
        schedule.reminder_time = payload.reminder_time; schedule.is_active = True
    else:
        schedule = ReminderSchedule(patient_id=current_user.id, reminder_time=payload.reminder_time); db.add(schedule)
    db.commit(); db.refresh(schedule); return schedule

@router.patch("/me", response_model=ReminderScheduleOut)
def update_reminder(payload: ReminderScheduleUpdate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    schedule = db.query(ReminderSchedule).filter(ReminderSchedule.patient_id == current_user.id).first()
    if not schedule: raise HTTPException(status_code=404, detail="No reminder schedule found — POST /reminders/me first")
    if payload.reminder_time is not None: schedule.reminder_time = payload.reminder_time
    if payload.is_active is not None: schedule.is_active = payload.is_active
    db.commit(); db.refresh(schedule); return schedule

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    schedule = db.query(ReminderSchedule).filter(ReminderSchedule.patient_id == current_user.id).first()
    if schedule: db.delete(schedule); db.commit()


async def _send_patient_and_caregivers(current_user: User, db: Session):
    from app.models.caregiver import Caregiver
    sent_to, failed, insufficient = [], [], []
    latest_log = db.query(MedicationLog).filter(MedicationLog.patient_id == current_user.id).order_by(MedicationLog.logged_at.desc()).first()
    medicine = latest_log.medicine_name if latest_log else None

    recipients = []
    if current_user.phone:
        recipients.append((current_user.phone, reminder_message(current_user.name, medicine), current_user.name + " (you)"))
    caregivers = db.query(Caregiver).filter(Caregiver.patient_id == current_user.id, Caregiver.reminders_enabled.is_(True)).all()
    for cg in caregivers:
        recipients.append((cg.phone, caregiver_reminder_message(cg.name, current_user.name, medicine), cg.name))
    if not recipients:
        raise HTTPException(status_code=422, detail="No caregivers added and no phone number on your account.")

    for phone, msg, label in recipients:
        try:
            ok, tx = await send_sms_with_token(db, current_user.id, phone, msg, "reminder_test")
            if ok: sent_to.append(label)
            elif tx.status == "rejected": insufficient.append(label)
            else: failed.append(label)
        except ValueError:
            failed.append(label)
    return {"sent_to": sent_to, "failed": failed, "insufficient_tokens": insufficient,
            "detail": f"SMS sent to {len(sent_to)} recipient(s)."}


@router.post("/send-now")
async def send_test_sms(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return await _send_patient_and_caregivers(current_user, db)


@router.get("/sms-log")
def sms_log(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    from app.models.sms_transaction import SmsTransaction
    rows = db.query(SmsTransaction).filter(SmsTransaction.user_id == current_user.id).order_by(SmsTransaction.created_at.desc()).limit(100).all()
    return [{"id": r.id, "recipient": r.recipient, "message_type": r.message_type, "tokens_used": r.tokens_used,
             "status": r.status, "provider": r.provider, "provider_message_id": r.provider_message_id,
             "error_message": r.error_message, "created_at": r.created_at, "sent_at": r.sent_at} for r in rows]
