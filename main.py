"""
Hostel Complaint Management System — FastAPI Backend
Run: uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import shutil, uuid, os, json

# ─── Config ──────────────────────────────────────────────────────────────────
SECRET_KEY      = "change-this-to-a-long-random-secret-in-production"
ALGORITHM       = "HS256"
TOKEN_EXPIRE    = 60  # minutes

SMTP_HOST       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT       = int(os.getenv("SMTP_PORT", 587))
SMTP_USER       = os.getenv("SMTP_USER", "your@gmail.com")
SMTP_PASS       = os.getenv("SMTP_PASS", "your-app-password")
SMTP_FROM       = os.getenv("SMTP_FROM", "Hostel CMS <your@gmail.com>")

UPLOAD_DIR      = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hostel CMS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ─── Auth helpers ─────────────────────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2  = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_pw(pw: str) -> str:          return pwd_ctx.hash(pw)
def verify_pw(plain, hashed) -> bool: return pwd_ctx.verify(plain, hashed)

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def get_current_user(token: str = Depends(oauth2)) -> dict:
    return decode_token(token)

def require_role(*roles):
    def checker(user=Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker

# ─── In-memory DB (replace with SQLAlchemy + PostgreSQL in production) ────────
users_db: dict = {}
complaints_db: dict = {}
comments_db: dict = {}  # complaint_id -> list of comments

def seed():
    users_db["stu001"] = {
        "id": "stu001", "name": "Aarav Shah",
        "email": "aarav@hostel.edu", "role": "student",
        "room": "A-204", "password": hash_pw("student123")
    }
    users_db["war001"] = {
        "id": "war001", "name": "Dr. Meera Nair",
        "email": "warden@hostel.edu", "role": "warden",
        "room": None, "password": hash_pw("warden123")
    }
    users_db["mnt001"] = {
        "id": "mnt001", "name": "Raju Verma",
        "email": "maintenance@hostel.edu", "role": "maintenance",
        "room": None, "password": hash_pw("maint123")
    }

    sample = [
        {"id": "C001", "student_id": "stu001", "student_name": "Aarav Shah",
         "room": "A-204", "category": "Plumbing", "subject": "Leaking tap in bathroom",
         "description": "The tap has been leaking for 3 days.", "priority": "High",
         "status": "Assigned", "assigned_to": "mnt001", "photos": [],
         "warden_note": "Fix ASAP", "created_at": "2026-05-01T10:00:00",
         "updated_at": "2026-05-01T12:00:00"},
        {"id": "C002", "student_id": "stu001", "student_name": "Aarav Shah",
         "room": "A-204", "category": "Electrical", "subject": "Fan not working",
         "description": "Ceiling fan stopped working last night.", "priority": "Medium",
         "status": "In Progress", "assigned_to": "mnt001", "photos": [],
         "warden_note": "", "created_at": "2026-05-02T08:00:00",
         "updated_at": "2026-05-02T09:00:00"},
    ]
    for c in sample:
        complaints_db[c["id"]] = c
        comments_db[c["id"]] = []

seed()

# ─── Pydantic models ──────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str       # student | warden | maintenance
    room: Optional[str] = None

class ComplaintUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    warden_note: Optional[str] = None
    priority: Optional[str] = None

class CommentIn(BaseModel):
    text: str

class EmailNotify(BaseModel):
    to: EmailStr
    subject: str
    body: str

# ─── Email helper ─────────────────────────────────────────────────────────────
def send_email(to: str, subject: str, body: str):
    """Send HTML email. Silently skips if SMTP not configured."""
    if SMTP_USER == "your@gmail.com":
        print(f"[EMAIL SKIPPED — configure SMTP] To: {to} | {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_FROM
        msg["To"]      = to
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to, msg.as_string())
        print(f"[EMAIL SENT] To: {to} | {subject}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")

def notify_complaint_submitted(complaint: dict, student_email: str):
    send_email(
        to=student_email,
        subject=f"Complaint {complaint['id']} Received — Hostel CMS",
        body=f"""
        <h2>Your complaint has been received</h2>
        <p><b>ID:</b> {complaint['id']}<br>
        <b>Subject:</b> {complaint['subject']}<br>
        <b>Category:</b> {complaint['category']}<br>
        <b>Priority:</b> {complaint['priority']}<br>
        <b>Status:</b> Pending</p>
        <p>You will be notified when the warden reviews your complaint.</p>
        """
    )

def notify_status_change(complaint: dict, student_email: str):
    send_email(
        to=student_email,
        subject=f"Complaint {complaint['id']} Status Updated — {complaint['status']}",
        body=f"""
        <h2>Complaint Status Updated</h2>
        <p><b>ID:</b> {complaint['id']}<br>
        <b>Subject:</b> {complaint['subject']}<br>
        <b>New Status:</b> <b>{complaint['status']}</b></p>
        {f"<p><b>Warden Note:</b> {complaint['warden_note']}</p>" if complaint.get('warden_note') else ""}
        <p>Log in to the Hostel CMS for more details.</p>
        """
    )

def notify_assigned(complaint: dict, maint_email: str):
    send_email(
        to=maint_email,
        subject=f"New Task Assigned — {complaint['id']}",
        body=f"""
        <h2>A complaint has been assigned to you</h2>
        <p><b>ID:</b> {complaint['id']}<br>
        <b>Room:</b> {complaint['room']}<br>
        <b>Category:</b> {complaint['category']}<br>
        <b>Subject:</b> {complaint['subject']}<br>
        <b>Priority:</b> {complaint['priority']}</p>
        <p>{complaint.get('warden_note','')}</p>
        <p>Please log in to update the status.</p>
        """
    )

# ─── Routes: Auth ─────────────────────────────────────────────────────────────
@app.post("/auth/register", status_code=201, tags=["Auth"])
def register(payload: UserCreate):
    for u in users_db.values():
        if u["email"] == payload.email:
            raise HTTPException(400, "Email already registered")
    uid = str(uuid.uuid4())[:8]
    users_db[uid] = {
        "id": uid, "name": payload.name, "email": payload.email,
        "role": payload.role, "room": payload.room,
        "password": hash_pw(payload.password)
    }
    return {"message": "Registered successfully", "user_id": uid}

@app.post("/auth/login", tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = next((u for u in users_db.values() if u["email"] == form.username), None)
    if not user or not verify_pw(form.password, user["password"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token({"sub": user["id"], "role": user["role"], "name": user["name"]})
    return {"access_token": token, "token_type": "bearer",
            "role": user["role"], "name": user["name"]}

@app.get("/auth/me", tags=["Auth"])
def me(user=Depends(get_current_user)):
    u = users_db.get(user["sub"])
    if not u:
        raise HTTPException(404, "User not found")
    return {k: v for k, v in u.items() if k != "password"}

# ─── Routes: Complaints ───────────────────────────────────────────────────────
@app.post("/complaints", status_code=201, tags=["Complaints"])
async def create_complaint(
    category:    str = Form(...),
    subject:     str = Form(...),
    description: str = Form(...),
    priority:    str = Form(...),
    photos: List[UploadFile] = File(default=[]),
    user=Depends(require_role("student"))
):
    student = users_db[user["sub"]]
    cid     = "C" + str(len(complaints_db) + 1).zfill(3)
    saved   = []

    for photo in photos:
        if photo.filename:
            ext  = photo.filename.rsplit(".", 1)[-1].lower()
            if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
                raise HTTPException(400, f"Unsupported file type: {ext}")
            fname = f"{cid}_{uuid.uuid4().hex[:8]}.{ext}"
            path  = os.path.join(UPLOAD_DIR, fname)
            with open(path, "wb") as f:
                shutil.copyfileobj(photo.file, f)
            saved.append(f"/uploads/{fname}")

    now = datetime.utcnow().isoformat()
    complaint = {
        "id": cid, "student_id": user["sub"],
        "student_name": student["name"], "room": student.get("room", "N/A"),
        "category": category, "subject": subject,
        "description": description, "priority": priority,
        "status": "Pending", "assigned_to": None, "photos": saved,
        "warden_note": "", "created_at": now, "updated_at": now
    }
    complaints_db[cid]  = complaint
    comments_db[cid]    = []
    notify_complaint_submitted(complaint, student["email"])
    return complaint

@app.get("/complaints", tags=["Complaints"])
def list_complaints(
    status: Optional[str]   = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    user=Depends(get_current_user)
):
    all_c = list(complaints_db.values())
    if user["role"] == "student":
        all_c = [c for c in all_c if c["student_id"] == user["sub"]]
    elif user["role"] == "maintenance":
        all_c = [c for c in all_c if c["assigned_to"] == user["sub"]]

    if status:   all_c = [c for c in all_c if c["status"]   == status]
    if category: all_c = [c for c in all_c if c["category"] == category]
    if priority: all_c = [c for c in all_c if c["priority"] == priority]

    return sorted(all_c, key=lambda c: c["created_at"], reverse=True)

@app.get("/complaints/{cid}", tags=["Complaints"])
def get_complaint(cid: str, user=Depends(get_current_user)):
    c = complaints_db.get(cid)
    if not c:
        raise HTTPException(404, "Complaint not found")
    return {**c, "comments": comments_db.get(cid, [])}

@app.patch("/complaints/{cid}", tags=["Complaints"])
def update_complaint(cid: str, payload: ComplaintUpdate, user=Depends(get_current_user)):
    c = complaints_db.get(cid)
    if not c:
        raise HTTPException(404, "Complaint not found")

    role = user["role"]
    if role not in ("warden", "maintenance"):
        raise HTTPException(403, "Only warden or maintenance can update complaints")

    old_status = c["status"]

    if payload.status:      c["status"]      = payload.status
    if payload.warden_note is not None: c["warden_note"] = payload.warden_note
    if payload.priority:    c["priority"]    = payload.priority

    if payload.assigned_to:
        maint = users_db.get(payload.assigned_to)
        if not maint or maint["role"] != "maintenance":
            raise HTTPException(400, "Invalid maintenance user ID")
        c["assigned_to"] = payload.assigned_to
        c["status"]      = "Assigned"
        notify_assigned(c, maint["email"])

    c["updated_at"] = datetime.utcnow().isoformat()

    # Notify student on status change
    if c["status"] != old_status:
        student = users_db.get(c["student_id"])
        if student:
            notify_status_change(c, student["email"])

    return c

@app.delete("/complaints/{cid}", tags=["Complaints"])
def delete_complaint(cid: str, user=Depends(require_role("warden"))):
    if cid not in complaints_db:
        raise HTTPException(404, "Complaint not found")
    del complaints_db[cid]
    comments_db.pop(cid, None)
    return {"message": "Deleted"}

# ─── Routes: Comments ─────────────────────────────────────────────────────────
@app.post("/complaints/{cid}/comments", tags=["Comments"])
def add_comment(cid: str, body: CommentIn, user=Depends(get_current_user)):
    if cid not in complaints_db:
        raise HTTPException(404, "Complaint not found")
    comment = {
        "id": str(uuid.uuid4())[:8],
        "author": user["name"],
        "role": user["role"],
        "text": body.text,
        "created_at": datetime.utcnow().isoformat()
    }
    comments_db.setdefault(cid, []).append(comment)
    return comment

@app.get("/complaints/{cid}/comments", tags=["Comments"])
def get_comments(cid: str, user=Depends(get_current_user)):
    if cid not in complaints_db:
        raise HTTPException(404, "Complaint not found")
    return comments_db.get(cid, [])

# ─── Routes: Users ────────────────────────────────────────────────────────────
@app.get("/users/maintenance", tags=["Users"])
def list_maintenance(user=Depends(require_role("warden"))):
    return [
        {"id": u["id"], "name": u["name"], "email": u["email"]}
        for u in users_db.values() if u["role"] == "maintenance"
    ]

@app.get("/users", tags=["Users"])
def list_users(user=Depends(require_role("warden"))):
    return [
        {k: v for k, v in u.items() if k != "password"}
        for u in users_db.values()
    ]

# ─── Routes: Stats ────────────────────────────────────────────────────────────
@app.get("/stats", tags=["Stats"])
def stats(user=Depends(require_role("warden"))):
    all_c = list(complaints_db.values())
    by_status   = {}
    by_category = {}
    by_priority = {}
    for c in all_c:
        by_status[c["status"]]     = by_status.get(c["status"], 0) + 1
        by_category[c["category"]] = by_category.get(c["category"], 0) + 1
        by_priority[c["priority"]] = by_priority.get(c["priority"], 0) + 1
    return {
        "total": len(all_c),
        "by_status": by_status,
        "by_category": by_category,
        "by_priority": by_priority
    }

# ─── Health ───────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "api": "Hostel CMS", "version": "1.0.0"}
