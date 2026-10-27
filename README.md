# NMAMIT Campus Event & Venue Booking

**🌐 Live site: https://college-event-silk.vercel.app/**

A website where NMAMIT users (`@nmamit.in`, `@nitte.edu.in`) book events and venues by looking at one **common calendar**.
It follows the NMAMIT website's look: navy and yellow, the NITTE logo, and campus photos. It works on both phones and desktops.

---

## Contents
- [Features](#features)
- [Who does what (roles)](#who-does-what-roles)
- [How a booking works](#how-a-booking-works)
- [Demo accounts](#demo-accounts)
- [Run it on your computer](#run-it-on-your-computer)
- [Environment variables](#environment-variables)
- [Deploy on Vercel with Neon Postgres](#deploy-on-vercel-with-neon-postgres)
- [Adding admins and venue in-charges](#adding-admins-and-venue-in-charges)
- [Verification emails and demo mode](#verification-emails-and-demo-mode)
- [Security](#security)
- [Tests](#tests)
- [Project structure](#project-structure)
- [Pages and API](#pages-and-api)
- [Stack](#stack)

---

## Features

### Core
- **College-only sign-up:** only `@nmamit.in` and `@nitte.edu.in` emails can register. Each one is verified with a 6-digit code, with at most 5 tries.
- **Required profile details:** name, Student / Faculty / Staff, department (16 NMAMIT departments), USN or employee ID, and a 10-digit Indian mobile number.
  Older accounts with missing details are sent to *My Profile* until they fill them in.
- **My Profile:** edit your details, change your password, see your booking counts, and see the venues you manage.
- **Common calendar:** month, week, day and list views of every booking, colour-coded by venue.
  - Filter it by venue.
  - Click an event to see its details and approver.
  - Drag across empty time to book it.
  - Phones get a list view automatically.
- **Booking with no double-booking:** each request is checked for opening hours (7 AM–9 PM), venue capacity, past times and clashes.
  - A pending request holds the slot.
  - The clash check and the save happen in one database transaction, so two people can't take the same slot even if they press *Book* at the same moment.
- **Approval workflow:**
  - Requests go to the venue's in-charge, or to the admin if the venue has none.
  - The approver approves or rejects. A rejection needs a reason, and the requester sees it.
  - Users see who they're waiting on, track the status, and can cancel.
- **Venue in-charge approval:**
  - The admin gives each venue an in-charge, e.g. the HoD.
  - The in-charge's *Approvals* tab lists requests for their venues only, with the requester's USN/ID, phone and email.
  - An in-charge's own bookings for their venues are approved instantly.
- **Admin panel:**
  - Totals: pending requests, upcoming events, active venues, verified users.
  - Add venues (name, building, capacity, facilities, colour, in-charge).
  - Enable or disable venues.
  - Assign in-charges.

### ✨ Highlight: Smart Slot Finder
- Enter a date, how long you need, how many people, and what the room must have (projector, stage, AC…).
- It lists every venue that fits, with a visual day timeline of free and busy times. The smallest venue that fits comes first, marked **Best fit**.
- Click a free slot to book it.
- If your chosen time clashes, the booking form offers the **nearest free time at the same venue** or **another free venue**, each one click away.

### Design and ease of use
- **Confirmation dialogs** in the site's own style (not browser pop-ups) for:
  - logging out,
  - cancelling a booking,
  - rejecting (requires a reason),
  - approving,
  - disabling a venue.
- **Mobile:**
  - a slide-in ☰ menu with your profile, every page, the pending-approvals count and Log out,
  - a floating **＋ Book** button,
  - a collapsible venue filter on the calendar,
  - the admin venues table shown as cards,
  - 16px text boxes so iPhones don't zoom in.
- **Feedback:**
  - spinners on buttons while saving, with no double submits,
  - pop-up messages with icons that stay when hovered and close when clicked,
  - a message that survives the page reload after approve, reject or cancel.
- **Forms:**
  - a Show/Hide button on passwords,
  - a warning before leaving a half-filled booking or profile form,
  - live checks for phone and USN format.
- **Accessibility:** clear keyboard focus outlines, labels on every control, animations turned off when the system asks for reduced motion.
- The NITTE shield is the browser tab icon and the phone home-screen icon.

---

## Who does what (roles)

| Role | How you get it | What you can do |
|---|---|---|
| **Member** (student, faculty, staff) | Register with a college email | View the calendar, find slots, request bookings, track and cancel your own bookings, edit your profile |
| **Venue in-charge** | The admin picks you for a venue in the Admin Panel | Everything a member can do, plus the **Approvals** tab: approve or reject requests for *your* venues. Your own bookings there are approved instantly |
| **Admin** | `make-admin` command (see below) | Everything, for all venues, plus the **Admin Panel**: add or disable venues and assign in-charges. Admin bookings are approved instantly |

---

## How a booking works

1. A member picks a venue, date and time. They can use the calendar (drag), the *Book a Venue* form, or the *Smart Slot Finder*.
2. The server checks hours, capacity, past times and clashes in one transaction.
   - If there is a clash, it suggests the nearest free time or another venue.
3. The booking is saved as **pending**, and the slot is held so nobody else can take it. The member sees *"Awaiting approval from …"*.
4. The venue's in-charge (or the admin) **approves** it, or **rejects** it with a reason.
5. An approved booking shows as solid on the common calendar. A pending one shows striped.
6. The member can **cancel** at any time before the event, which frees the slot.

---

## Demo accounts

A **fresh** database is filled with these accounts, 11 NMAMIT venues and sample bookings:

| Account | Password | Role |
|---|---|---|
| admin@nmamit.in | Admin@123 | Admin |
| incharge@nmamit.in | Incharge@123 | In-charge of *Seminar Hall – ISE* and *Computer Lab – ISE* |
| demo@nmamit.in | Demo@123 | Student |

> ⚠️ These passwords are public. On the live site, change them (*My Profile → Change password*) or replace these accounts with real people as soon as real users join.

---

## Run it on your computer

Needs Python 3.10+.

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

- With no `DATABASE_URL`, it uses a local SQLite file (`nmamit.db`), created and filled with demo data on first run.
- With `DATABASE_URL` in `.env`, it uses that Postgres database instead.
- For auto-reload while editing: `FLASK_DEBUG=1 python app.py`.

---

## Environment variables

Copy `.env.example` to `.env` and fill it in. `.env` is git-ignored and never uploaded to Vercel. Real environment variables (e.g. Vercel's) override `.env`.

| Variable | Needed? | What it does |
|---|---|---|
| `DATABASE_URL` | Required on Vercel | Postgres connection string (e.g. from Neon). If empty, SQLite is used |
| `SECRET_KEY` | Required on Vercel | Signs login cookies. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` | Optional | Send real verification emails (see below) |
| `SMTP_PORT`, `SMTP_FROM` | Optional | Defaults are `587` and `SMTP_USER` |
| `DEMO_OTP` | Optional, demos only | One fixed 6-digit code for every sign-up |
| `DB_PATH` | Optional | Location of the SQLite file when not using Postgres |

The app **refuses to start on Vercel** if `DATABASE_URL` or `SECRET_KEY` is missing, so a deployment can never quietly lose data or log everyone out.

---

## Deploy on Vercel with Neon Postgres

Live deployment: **https://college-event-silk.vercel.app/**

Vercel needs Postgres because its servers keep no files between requests, so SQLite would lose data.

1. **Import the repo:** in Vercel, choose *Add New → Project* and import this GitHub repo. Vercel detects Flask automatically, so leave the build settings as they are.
2. **Add the database:**
   - Either go to *Storage → Create Database → Neon* (free plan) and connect it to the project,
   - or paste an existing Neon connection string as `DATABASE_URL`.
   - Use the **pooled** connection string (its host contains `-pooler`).
3. **Add `SECRET_KEY`** under *Settings → Environment Variables*.
4. **Optional:** add the `SMTP_*` variables for real emails, or `DEMO_OTP` for a demo.
5. **Redeploy.** The first visit creates the tables and the demo data automatically.

Other details:
- `vercel.json` pins the server to **Singapore (`sin1`)**, next to the Neon database in `ap-southeast-1`, which keeps pages fast.
- Static files live in `public/static` so Vercel serves them from its CDN.
- `.vercelignore` keeps `.env`, the local database and the tests out of the upload.

---

## Adding admins and venue in-charges

**Make someone an admin**
1. They register on the live site and verify their email.
2. On your computer, with the **same** `DATABASE_URL` as Vercel in your `.env`, run:
   ```bash
   flask --app app make-admin theiremail@nmamit.in
   ```
   It should print `theiremail@nmamit.in is now an admin.`

**Make someone a venue in-charge**
1. They register and verify. Only verified users can be picked.
2. An admin opens **Admin Panel → Venues & in-charges** and picks them in that venue's **In-charge (approver)** dropdown. It saves immediately.
3. That venue's requests now appear in their **Approvals** tab.
   - One person can manage several venues.
   - Choosing *Admin* sends that venue's requests back to the admins.

---

## Verification emails and demo mode

**No email settings:** the 6-digit code is printed in the server log. Locally that's the terminal. On Vercel it's the project's *Logs* tab.

**Real emails** (e.g. with a Gmail App Password):
```powershell
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_USER="you@gmail.com"; $env:SMTP_PASS="app-password"; python app.py
```
On Vercel, add the same values as environment variables instead.

**Demo mode:**
- Set `DEMO_OTP=123456` (any 6 digits).
- Every new sign-up then uses that code, no email is sent, and the verify page shows the code.
- ⚠️ While it's on, anyone can register with any college address without owning it. Remove it for real use.

---

## Security
- Only official college emails can register, and each must be verified (6-digit code, at most 5 tries).
- Passwords are stored as salted hashes (Werkzeug).
- Login cookies are `HttpOnly` and `SameSite=Lax`. Data-changing API calls accept JSON only, which blocks cross-site form attacks.
- Login redirects only go to pages on this site.
- Database queries use bound parameters, which prevents SQL injection.
- Every approve, reject or cancel is checked on the server: owner, the venue's in-charge, or an admin.
- No double-booking:
  - Postgres takes a per-venue advisory lock for each booking.
  - SQLite uses `BEGIN IMMEDIATE`.
  - Tested with 8 requests for the same slot at once; exactly one succeeds.
- Secrets live only in `.env` (git-ignored) or Vercel's environment variables.
- Not yet added: rate limiting on login, register and booking.

---

## Tests

```bash
python -m unittest test_app -v
```

5 tests:
- **Full booking flow:** clashes, suggestions, capacity, hours, approve, cancel.
- **In-charge permissions.**
- **Register and profile:** validation, verify, edit, change password.
- **8 simultaneous bookings, one winner.**
- **Old accounts must complete their profile.**

The tests always use a temporary SQLite database and **never touch `DATABASE_URL` from `.env`**, so the live data is safe.

To run them on Postgres, point `TEST_DATABASE_URL` at a **throwaway** database. Its tables are dropped.
```bash
TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:54329/postgres python -m unittest test_app
```

---

## Project structure

```
app.py                  Flask app: settings, database (SQLite/Postgres), booking logic, Smart Slot Finder, routes, API
test_app.py             Tests
requirements.txt        Flask, psycopg
vercel.json             Vercel region (sin1)
.env.example            Template for .env
.vercelignore           Files kept out of the Vercel upload
public/static/
  style.css             All styles (NMAMIT navy/yellow theme, responsive)
  app.js                Shared JS: confirm dialogs, pop-up messages, mobile menu, timelines, form helpers
  img/                  NITTE logo, favicon, campus photos
templates/
  base.html             Header, tabs, mobile menu, messages, footer
  index.html            Home page
  login.html, register.html, verify.html
  calendar.html         Common calendar (FullCalendar)
  book.html             Booking form with live availability and clash suggestions
  finder.html           Smart Slot Finder
  venues.html           Venue list with in-charges
  my.html               My Bookings
  approvals.html        In-charge/admin approval queue
  admin.html            Admin Panel
  profile.html          My Profile
  _booking.html         Shared booking card
  _profile_fields.html  Shared profile form fields
```

---

## Pages and API

| Page | Path | Who |
|---|---|---|
| Home | `/` | Everyone |
| Log in / Register / Verify | `/login`, `/register`, `/verify` | Everyone |
| Common Calendar | `/calendar` | Logged in |
| Book a Venue | `/book` | Logged in |
| Smart Slot Finder | `/finder` | Logged in |
| Venues | `/venues` | Logged in |
| My Bookings | `/my` | Logged in |
| My Profile | `/profile` | Logged in |
| Approvals | `/approvals` | In-charges and admins |
| Admin Panel | `/admin` | Admins |

| API | Method | What it does |
|---|---|---|
| `/api/events?start=&end=&venues=` | GET | Bookings for the calendar |
| `/api/availability?day=&duration=&attendees=&facility=&venue=` | GET | Free and busy times per venue (Smart Slot Finder) |
| `/api/bookings` | POST (JSON) | Create a booking. Returns `409` with suggestions on a clash |
| `/api/bookings/<id>/status` | POST (JSON) | `approve`, `reject` (with `note`) or `cancel` |
| `/admin/venues` | POST | Add a venue |
| `/admin/venues/<id>/toggle` | POST | Enable or disable a venue |
| `/admin/venues/<id>/incharge` | POST | Set a venue's in-charge |

---

## Stack
- **Backend:** Flask 3 (Python)
- **Database:** Postgres via psycopg 3 in production (Neon), SQLite locally
- **Frontend:** Jinja templates, plain JavaScript, FullCalendar 6 (CDN), Montserrat (Google Fonts)
- **Hosting:** Vercel (Singapore region) + Neon Postgres
