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
| demo@nmamit.in (user) | Demo@123 |

Tests: `python -m unittest test_app -v`

## Features
- **College-only sign-up**: only `@nmamit.in` / `@nitte.edu.in` emails, verified with a 6-digit code (5 tries max).
- **Common calendar**: month, week, day and list views of every booking, filterable by venue. Drag across empty time to book it.
- **Booking with no double-booking**: checks hours, capacity and past times, and holds the slot while a request is pending. The check and insert happen in one transaction, so two simultaneous requests can't take the same slot.
- **Approval workflow**: admin approves or rejects (with a reason). Users track status and can cancel.
- **Admin panel**: stats, pending queue, upcoming events, and adding or disabling venues.
- ✨ **Smart Slot Finder (highlight feature)**: enter date, duration, headcount and needs (projector, stage…). It lists every venue that fits, with a visual timeline, best fit first. On a clash, the booking form suggests the nearest free time or another free venue in one click.

## Sending real verification emails
With no mail server set, the code is printed in the terminal running `app.py` (dev mode). To send real emails (for example with a Gmail App Password):
```powershell
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_USER="you@gmail.com"; $env:SMTP_PASS="app-password"; python app.py
```
Also set `$env:SECRET_KEY` to a fixed random string in production, so logins survive restarts.

Make someone an admin: `flask --app app make-admin someone@nmamit.in`

## Stack
Flask + SQLite (Python stdlib) · Jinja templates · vanilla JS · FullCalendar (CDN) · Montserrat font.
