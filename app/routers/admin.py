"""Internal admin endpoints and the server-side reminder worker."""
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.user import User
from app.models.medication_log import MedicationLog
from app.models.reminder import ReminderSchedule
from app.models.schedule import MedicationSchedule
from app.models.caregiver import Caregiver
from app.services.sms import send_sms_with_token, reminder_message, caregiver_reminder_message
from app.config import get_settings

EAT = ZoneInfo("Africa/Nairobi")
settings = get_settings()
router = APIRouter(prefix="/admin", tags=["Admin"], include_in_schema=False)
ADMIN_KEY = settings.SECRET_KEY

def verify_admin(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_KEY: raise HTTPException(status_code=403, detail="Forbidden")

async def _send_recipients(db: Session, patient: User, medicine: str | None):
    sent = failed = skipped = 0
    if patient.phone:
        ok, _ = await send_sms_with_token(db, patient.id, patient.phone, reminder_message(patient.name, medicine), "medication_reminder")
        sent += int(ok); failed += int(not ok)
    else:
        skipped += 1
    caregivers = db.query(Caregiver).filter(Caregiver.patient_id == patient.id, Caregiver.reminders_enabled.is_(True)).all()
    for cg in caregivers:
        ok, _ = await send_sms_with_token(db, patient.id, cg.phone, caregiver_reminder_message(cg.name, patient.name, medicine), "caregiver_reminder")
        sent += int(ok); failed += int(not ok)
    return sent, failed, skipped

async def run_reminders_job(db: Session):
    now_eat = datetime.now(EAT); today = now_eat.date()
    sent = skipped = failed = 0

    daily_schedules = db.query(ReminderSchedule).filter(ReminderSchedule.is_active.is_(True)).all()
    for sched in daily_schedules:
        if sched.last_sent_at and sched.last_sent_at.astimezone(EAT).date() >= today: skipped += 1; continue
        if now_eat.strftime("%H") != sched.reminder_time[:2]: skipped += 1; continue
        patient = db.query(User).filter(User.id == sched.patient_id).first()
        if not patient: skipped += 1; continue
        s, f, sk = await _send_recipients(db, patient, None)
        if s: sched.last_sent_at = now_eat
        sent += s; failed += f; skipped += sk

    interval_schedules = db.query(MedicationSchedule).filter(MedicationSchedule.active.is_(True), MedicationSchedule.start_date <= today, MedicationSchedule.end_date >= today).all()
    for sched in interval_schedules:
        hh, mm = (int(p) for p in sched.first_dose_time.split(":"))
        start_dt = datetime(sched.start_date.year, sched.start_date.month, sched.start_date.day, hh, mm, tzinfo=EAT)
        if now_eat < start_dt: skipped += 1; continue
        elapsed_hours = (now_eat - start_dt).total_seconds() / 3600
        slot_index = int(elapsed_hours // sched.interval_hours)
        slot_time = start_dt + timedelta(hours=slot_index * sched.interval_hours)
        if not (slot_time <= now_eat < slot_time + timedelta(hours=1)): skipped += 1; continue
        if sched.last_reminder_sent_at and sched.last_reminder_sent_at >= slot_time: skipped += 1; continue
        patient = db.query(User).filter(User.id == sched.patient_id).first()
        if not patient: skipped += 1; continue
        s, f, sk = await _send_recipients(db, patient, sched.medicine_name)
        if s: sched.last_reminder_sent_at = now_eat
        sent += s; failed += f; skipped += sk

    db.commit()
    return {"sent": sent, "skipped": skipped, "failed": failed}

@router.post("/run-reminders")
async def run_reminders(db: Session = Depends(get_db), _: None = Depends(verify_admin)):
    return await run_reminders_job(db)

@router.get("/stats")
def system_stats(db: Session = Depends(get_db), _: None = Depends(verify_admin)):
    total_patients = db.query(User).filter(User.role == "patient").count()
    total_doctors = db.query(User).filter(User.role == "doctor").count()
    total_logs = db.query(MedicationLog).count()
    taken_logs = db.query(MedicationLog).filter(MedicationLog.taken.is_(True)).count()
    return {"total_patients": total_patients, "total_doctors": total_doctors, "total_logs": total_logs,
            "overall_adherence_rate": round(taken_logs / total_logs * 100) if total_logs else 0,
            "logs_today": db.query(MedicationLog).filter(MedicationLog.log_date == date.today()).count(),
            "active_reminder_schedules": db.query(ReminderSchedule).filter(ReminderSchedule.is_active.is_(True)).count()}
