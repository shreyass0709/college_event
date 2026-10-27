# NMAMIT Campus Event & Venue Booking

A website where NMAMIT users (`@nmamit.in`, `@nitte.edu.in`) book events and venues by looking at one **common calendar**.

## Run it

```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. The database (`nmamit.db`) is created and filled with sample data on first run.

| Demo account | Password |
|---|---|
| admin@nmamit.in (admin) | Admin@123 |
| incharge@nmamit.in (in-charge of the ISE seminar hall + ISE lab) | Incharge@123 |
| demo@nmamit.in (student) | Demo@123 |

Tests: `python -m unittest test_app -v`

## Features
- **College-only sign-up**: only `@nmamit.in` / `@nitte.edu.in` emails, verified with a 6-digit code (5 tries max).
  Required details: name, Student/Faculty/Staff, department, USN or employee ID, and mobile number.
- **My Profile**: edit your details and change your password. Accounts missing details must complete them before continuing.
- **Venue in-charge approval**: the admin assigns an in-charge (e.g. the HoD) to each venue. Requests for that venue go to the in-charge's
  **Approvals** tab, which shows the requester's USN/ID, phone and email. Venues without an in-charge go to the Admin.
  An in-charge's bookings for their own venue are approved instantly.
- **Common calendar**: month, week, day and list views of every booking, filterable by venue. Drag across empty time to book it.
- **Booking with no double-booking**: checks hours, capacity and past times, and holds the slot while a request is pending. The check and insert happen in one transaction, so two simultaneous requests can't take the same slot.
- **Approval workflow**: the approver accepts or rejects (with a reason). Users see who they're waiting on, track status, and can cancel.
- **Admin panel**: stats, adding or disabling venues, and assigning each venue's in-charge.
- ✨ **Smart Slot Finder (highlight feature)**: enter date, duration, headcount and needs (projector, stage…). It lists every venue that fits, with a visual timeline, best fit first. On a clash, the booking form suggests the nearest free time or another free venue in one click.

## Deploy on Vercel (with a free Neon Postgres database)
Locally the app uses SQLite. When `DATABASE_URL` is set, it uses Postgres instead. Vercel needs Postgres because its servers keep no files between requests.

1. **Import the repo:** in Vercel, choose *Add New → Project*, then import this GitHub repo. Vercel detects Flask automatically, so leave all build settings as they are.
2. **Add the database:** in the project, go to *Storage → Create Database → Neon* (free plan) and connect it to the project.
   This adds a `DATABASE_URL` environment variable. Check that it exists under *Settings → Environment Variables*.
3. **Add a secret key:** add `SECRET_KEY` with a long random value. You can generate one with `python -c "import secrets; print(secrets.token_hex(32))"`.
4. **Add email settings:** add `SMTP_HOST`, `SMTP_USER` and `SMTP_PASS` (see below) so new users receive their verification code by email.
   Without them, codes only appear in Vercel's *Logs* tab.
5. **Deploy:** click *Redeploy*. The first visit creates the tables and the demo data automatically.

The app refuses to start on Vercel if `DATABASE_URL` or `SECRET_KEY` is missing, so a deployment can never quietly lose data.

Test against Postgres locally (this **drops all tables**, so use a throwaway database):
`DATABASE_URL=postgresql://postgres:test@127.0.0.1:54329/postgres python -m unittest test_app`

## Demo mode (no email needed)
Set `DEMO_OTP=123456` (any 6 digits). Every new sign-up then uses that code, no email is sent, and the verify page shows the code.
⚠️ While it's on, anyone can register with any college address, so remove it for real use.

## Sending real verification emails
With no mail server set, the code is printed in the terminal running `app.py` (dev mode). To send real emails (for example with a Gmail App Password):
```powershell
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_USER="you@gmail.com"; $env:SMTP_PASS="app-password"; python app.py
```
Also set `$env:SECRET_KEY` to a fixed random string in production, so logins survive restarts.

Make someone an admin: `flask --app app make-admin someone@nmamit.in`

## Stack
Flask · Postgres via psycopg 3 (production, e.g. Neon) or SQLite (local) · Jinja templates · vanilla JS · FullCalendar (CDN) · Montserrat font · deployed on Vercel.
