# Hostel Complaint Management System

A full-stack complaint tracking system for hostels — FastAPI backend + HTML/JS frontend
with photo attachments, email notifications, and role-based access.

---

## Roles

| Role        | Credentials (demo)              | Capabilities |
|-------------|---------------------------------|-------------|
| Student     | aarav@hostel.edu / student123   | Submit complaints with photos, track status |
| Warden      | warden@hostel.edu / warden123   | Review all complaints, assign to maintenance, update status |
| Maintenance | maintenance@hostel.edu / maint123 | View assigned tasks, update progress, mark resolved |

---

## Backend Setup (FastAPI)

### 1. Install dependencies
```bash
cd hostel-cms
pip install -r requirements.txt
```

### 2. Configure email (Gmail recommended)
```bash
cp .env.example .env
# Edit .env with your Gmail credentials
# Enable 2FA on Gmail → create an App Password at:
# https://myaccount.google.com/apppasswords
export $(cat .env | xargs)
```

### 3. Run the server
```bash
uvicorn main:app --reload --port 8000
```

API docs will be at: http://localhost:8000/docs

---

## Frontend Setup

Open `index.html` in any modern browser. It will:
- Try to connect to `http://localhost:8000` automatically
- Fall back to offline demo mode if the backend isn't running
- Show a toast indicating which mode is active

---

## API Endpoints

### Auth
| Method | Path           | Access | Description |
|--------|----------------|--------|-------------|
| POST   | /auth/register | Public | Register new user |
| POST   | /auth/login    | Public | Login → JWT token |
| GET    | /auth/me       | Any    | Get current user profile |

### Complaints
| Method | Path                    | Access             | Description |
|--------|-------------------------|--------------------|-------------|
| POST   | /complaints             | Student            | Submit complaint (multipart/form-data with photos) |
| GET    | /complaints             | All (filtered)     | List complaints (role-filtered automatically) |
| GET    | /complaints/{id}        | All                | Get single complaint with comments |
| PATCH  | /complaints/{id}        | Warden/Maintenance | Update status, assign, add note |
| DELETE | /complaints/{id}        | Warden             | Delete complaint |

### Comments
| Method | Path                          | Access | Description |
|--------|-------------------------------|--------|-------------|
| POST   | /complaints/{id}/comments     | Any    | Add comment/update |
| GET    | /complaints/{id}/comments     | Any    | Get all comments |

### Users & Stats
| Method | Path               | Access | Description |
|--------|--------------------|--------|-------------|
| GET    | /users/maintenance | Warden | List maintenance staff |
| GET    | /users             | Warden | List all users |
| GET    | /stats             | Warden | Complaint statistics |

---

## Email Notifications

Emails are sent automatically on these events:

| Event                  | Recipient      |
|------------------------|----------------|
| Complaint submitted    | Student        |
| Status changed         | Student        |
| Assigned to maintenance| Maintenance staff |

Configure SMTP in `.env`. The system uses Gmail SMTP by default.
Set `SMTP_USER=your@gmail.com` and `SMTP_PASS=your-app-password`.

---

## Production Checklist

- [ ] Replace in-memory `users_db` / `complaints_db` with PostgreSQL via SQLAlchemy
- [ ] Set a strong random `SECRET_KEY` (see `.env.example`)
- [ ] Restrict `allow_origins` in CORS to your frontend domain
- [ ] Use `python-dotenv` to load `.env` automatically
- [ ] Add file size limits and virus scanning for uploads
- [ ] Deploy with `gunicorn -k uvicorn.workers.UvicornWorker main:app`
- [ ] Serve `uploads/` directory via nginx or a CDN (not FastAPI's StaticFiles in production)

---

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, python-jose (JWT), passlib (bcrypt)
- **Frontend**: Vanilla HTML/CSS/JS, DM Sans font, no framework dependencies
- **Auth**: OAuth2 + JWT Bearer tokens
- **Email**: SMTP via smtplib (Gmail / any SMTP provider)
- **Storage**: Local filesystem (swap for S3/GCS in production)
