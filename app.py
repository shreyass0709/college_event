"""NMAMIT Event & Venue Booking — Flask on Postgres (DATABASE_URL, e.g. Vercel + Neon) or SQLite (local default)."""
import os
import re
import secrets
import smtplib
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from email.message import EmailMessage
from functools import wraps

import click
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))


def load_env(path):
    """Read KEY=value lines from .env (kept out of git). Real environment variables, e.g. Vercel's, take priority."""
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            key, sep, val = line.strip().partition("=")
            if sep and key and not key.startswith("#"):
                os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


load_env(os.path.join(BASE, ".env"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "nmamit.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PG = DATABASE_URL.startswith(("postgres://", "postgresql://"))
if PG:
    import psycopg
    from psycopg.rows import dict_row
if os.environ.get("VERCEL") and not (PG and os.environ.get("SECRET_KEY")):
    # serverless disks are wiped and every instance would mint its own session key
    raise RuntimeError("On Vercel, set the DATABASE_URL (Postgres) and SECRET_KEY environment variables.")
IntegrityError = psycopg.IntegrityError if PG else sqlite3.IntegrityError
# Demo mode: every sign-up uses this code and no email is sent. Anyone can then claim any college
# address, so leave it unset for real use.
DEMO_OTP = os.environ.get("DEMO_OTP", "") if re.fullmatch(r"\d{6}", os.environ.get("DEMO_OTP", "")) else ""
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@(nmamit\.in|nitte\.edu\.in)$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
IDNO_RE = re.compile(r"^[A-Z0-9/-]{3,20}$")
OPEN, CLOSE = "07:00", "21:00"  # bookable hours
USER_TYPES = ("Student", "Faculty", "Staff")
DEPTS = [
    ("CSE", "Computer Science & Engineering"), ("ISE", "Information Science & Engineering"),
    ("AIML", "Artificial Intelligence & Machine Learning"), ("AIDS", "Artificial Intelligence & Data Science"),
    ("CCE", "Computer & Communication Engineering"), ("ECE", "Electronics & Communication Engineering"),
    ("EEE", "Electrical & Electronics Engineering"), ("MECH", "Mechanical Engineering"),
    ("CIVIL", "Civil Engineering"), ("BT", "Biotechnology"), ("RAI", "Robotics & Artificial Intelligence"),
    ("MCA", "Master of Computer Applications"), ("MBA", "Master of Business Administration"),
    ("SCI", "Basic Sciences & Humanities"), ("ADMIN", "Administration / Office"), ("OTHER", "Other"),
]

app = Flask(__name__, static_folder="public/static")  # public/ is also served straight from Vercel's CDN
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_SAMESITE="Lax",  # with JSON-only API writes, this is the CSRF guard
    SESSION_COOKIE_HTTPONLY=True,
)
app.jinja_env.globals.update(DEPTS=DEPTS, DEPT_NAMES=dict(DEPTS), USER_TYPES=USER_TYPES, DEMO_OTP=DEMO_OTP)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, pw TEXT NOT NULL,
  dept TEXT, role TEXT NOT NULL DEFAULT 'user', verified INTEGER NOT NULL DEFAULT 0,
  code TEXT, tries INTEGER NOT NULL DEFAULT 0, utype TEXT, id_no TEXT, phone TEXT);
CREATE TABLE IF NOT EXISTS venues(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, building TEXT, capacity INTEGER NOT NULL,
  facilities TEXT NOT NULL DEFAULT '', color TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
  incharge_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  venue_id INTEGER NOT NULL REFERENCES venues(id), title TEXT NOT NULL, description TEXT,
  organizer TEXT, day TEXT NOT NULL, start_t TEXT NOT NULL, end_t TEXT NOT NULL,
  attendees INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', note TEXT,
  created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS ix_bookings ON bookings(venue_id, day);
"""

VENUES = [
    ("Main Auditorium", "Admin Block", 800, "Projector,Sound System,Stage,AC,Recording", "#2b2f8f"),
    ("Mini Auditorium", "Academic Block", 250, "Projector,Sound System,Stage,AC", "#7048e8"),
    ("Seminar Hall - ISE", "ISE Block", 120, "Projector,Sound System,AC,Smart Board", "#0ca678"),
    ("Seminar Hall - CSE", "CSE Block", 150, "Projector,Sound System,AC", "#e8590c"),
    ("Seminar Hall - ECE", "ECE Block", 120, "Projector,Sound System", "#d6336c"),
    ("Conference Room", "Admin Block", 30, "Projector,AC,Video Conferencing", "#1c7ed6"),
    ("Computer Lab - ISE", "ISE Block", 70, "Computers,Projector,AC", "#0b7285"),
    ("Library Discussion Room", "Central Library", 20, "Smart Board,AC", "#5c940d"),
    ("Open Air Theatre", "Campus Grounds", 1000, "Stage,Sound System", "#c2255c"),
    ("Indoor Stadium", "Sports Complex", 500, "Sound System,Seating", "#f08c00"),
    ("Main Ground", "Sports Complex", 2000, "Floodlights", "#2f9e44"),
]


def seed(con):
    con.executemany("INSERT INTO venues(name,building,capacity,facilities,color) VALUES(?,?,?,?,?)", VENUES)
    for row in [("Event Admin", "admin@nmamit.in", "Admin@123", "admin", "Staff", "ADMIN", "EMP001", "9876543210"),
                ("Demo Student", "demo@nmamit.in", "Demo@123", "user", "Student", "ISE", "NNM22IS001", "9876543211"),
                ("Dr. ISE In-charge", "incharge@nmamit.in", "Incharge@123", "user", "Faculty", "ISE", "EMP101", "9876543212")]:
        con.execute("INSERT INTO users(name,email,pw,role,utype,dept,id_no,phone,verified) VALUES(?,?,?,?,?,?,?,?,1)",
                    (row[0], row[1], generate_password_hash(row[2]), *row[3:]))
    con.execute("UPDATE venues SET incharge_id=3 WHERE id IN (3,7)")  # ISE seminar hall + ISE lab
    t = date.today().toordinal()
    demo = [  # venue_id, days from today, title, organizer, start, end, attendees, status
        (6, 0, "Board of Studies Meeting", "ISE Department", "15:00", "16:30", 20, "approved"),
        (3, 2, "Project Expo Briefing", "ISE Final Year", "10:00", "12:00", 100, "pending"),
        (1, 1, "Tech Talk: GenAI in Industry", "ISE Department", "10:00", "12:00", 400, "approved"),
        (3, 1, "IEEE Student Branch Meetup", "IEEE SB NMAMIT", "14:00", "16:00", 80, "approved"),
        (9, 2, "Cultural Night Rehearsal", "Cultural Committee", "17:00", "20:00", 200, "pending"),
        (4, 3, "Hackathon Orientation", "CSE Department", "09:00", "11:00", 140, "approved"),
        (10, 4, "Inter-branch Badminton", "Sports Club", "15:00", "18:00", 150, "approved"),
        (2, 5, "Alumni Interaction", "Alumni Cell", "11:00", "13:00", 200, "pending"),
        (1, 7, "Placement Pre-talk", "Training & Placement", "09:30", "12:30", 600, "approved"),
    ]
    for vid, off, title, org, s, e, n, st in demo:
        con.execute("INSERT INTO bookings(user_id,venue_id,title,organizer,day,start_t,end_t,attendees,status)"
                    " VALUES(2,?,?,?,?,?,?,?,?)", (vid, title, org, date.fromordinal(t + off).isoformat(), s, e, n, st))


class PgConn:
    """Lets the sqlite-style queries ('?' placeholders) run unchanged on Postgres."""

    def __init__(self):
        # prepare_threshold=None: required behind poolers like Neon's pgbouncer
        self.con = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row, prepare_threshold=None)

    def execute(self, q, args=()):
        return self.con.execute(q.replace("?", "%s"), args)

    def executemany(self, q, rows):
        with self.con.cursor() as c:
            c.executemany(q.replace("?", "%s"), rows)

    def close(self):
        self.con.close()


def init_db():
    if PG:
        con = PgConn()
        with con.con.transaction():
            con.execute("SELECT pg_advisory_xact_lock(0)")  # several cold starts may run this at once
            for stmt in SCHEMA.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY").split(";"):
                if stmt.strip():
                    con.execute(stmt)
            if not con.execute("SELECT 1 FROM venues").fetchone():
                seed(con)
        con.close()
        return
    con = sqlite3.connect(DB_PATH)
    for table, col, ddl in [("users", "utype", "TEXT"), ("users", "id_no", "TEXT"), ("users", "phone", "TEXT"),
                            ("venues", "incharge_id", "INTEGER REFERENCES users(id)")]:  # upgrade older DBs in place
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        if cols and col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
    con.executescript(SCHEMA)
    if not con.execute("SELECT 1 FROM venues").fetchone():
        seed(con)
    con.commit()
    con.close()


def db():
    if "db" not in g:
        if PG:
            g.db = PgConn()
        else:
            g.db = sqlite3.connect(DB_PATH, isolation_level=None, timeout=10)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def scalar(q, args=()):
    row = db().execute(q, args).fetchone()
    return next(iter(row.values())) if PG else row[0]


@contextmanager
def venue_lock(vid):
    """Serialize check-then-insert per venue so two requests can't grab the same slot."""
    con = db()
    if PG:
        with con.con.transaction():
            con.execute("SELECT pg_advisory_xact_lock(?)", (vid,))
            yield
    else:
        with con:
            con.execute("BEGIN IMMEDIATE")
            yield


@app.teardown_appcontext
def close_db(_):
    if (con := g.pop("db", None)) is not None:
        con.close()


# ---------- time helpers ----------
def mins(t):
    return int(t[:2]) * 60 + int(t[3:5])


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def venues(active_only=True):
    return db().execute("SELECT v.*, u.name iname, u.email iemail, u.phone iphone FROM venues v"
                        " LEFT JOIN users u ON u.id=v.incharge_id" + (" WHERE v.active=1" if active_only else "") +
                        " ORDER BY v.capacity").fetchall()


def review_scope():
    """SQL filter (on alias v) for venues whose requests the current user approves: all for admin, own for in-charges."""
    return ("1=1", ()) if g.user["role"] == "admin" else ("v.incharge_id=?", (g.user["id"],))


def can_review(vid):
    return g.user["role"] == "admin" or bool(
        db().execute("SELECT 1 FROM venues WHERE id=? AND incharge_id=?", (vid, g.user["id"])).fetchone())


def clean_profile(f):
    p = dict(name=f.get("name", "").strip()[:80], utype=f.get("utype", ""), dept=f.get("dept", ""),
             id_no=f.get("id_no", "").strip().upper(), phone=re.sub(r"[\s-]", "", f.get("phone", ""))[-10:])
    if not p["name"]:
        return "Please enter your full name.", p
    if p["utype"] not in USER_TYPES:
        return "Please choose whether you are a student, faculty or staff member.", p
    if p["dept"] not in dict(DEPTS):
        return "Please choose your department.", p
    if not IDNO_RE.match(p["id_no"]):
        return ("Please enter a valid USN." if p["utype"] == "Student" else "Please enter a valid employee ID."), p
    if not PHONE_RE.match(p["phone"]):
        return "Please enter a valid 10-digit mobile number.", p
    return None, p


def busy_blocks(vid, day):
    return db().execute("SELECT * FROM bookings WHERE venue_id=? AND day=? AND status IN ('pending','approved')"
                        " ORDER BY start_t", (vid, day)).fetchall()


def conflicts(vid, day, s, e):
    """Pending requests hold the slot too, so two people can't both be waiting on the same hall."""
    return db().execute("SELECT b.*, u.name uname FROM bookings b JOIN users u ON u.id=b.user_id"
                        " WHERE venue_id=? AND day=? AND status IN ('pending','approved')"
                        " AND start_t<? AND end_t>?", (vid, day, e, s)).fetchall()


def free_windows(busy, day):
    today = date.today().isoformat()
    if day < today:
        return []
    cur = OPEN
    if day == today:
        now = datetime.now()
        cur = max(cur, hhmm(-(-(now.hour * 60 + now.minute) // 15) * 15))  # next quarter hour
    out = []
    for b in busy:
        if b["start_t"] > cur:
            out.append((cur, b["start_t"]))
        cur = max(cur, b["end_t"])
    if cur < CLOSE:
        out.append((cur, CLOSE))
    return out


def suggest(v, day, s, e, n):
    """Smart suggestions: same venue at the nearest free time, or other big-enough venues free right then."""
    dur = mins(e) - mins(s)
    same = []
    if v["capacity"] >= n:
        for a, b in free_windows(busy_blocks(v["id"], day), day):
            if mins(b) - mins(a) >= dur:
                st = min(max(mins(s), mins(a)), mins(b) - dur)
                same.append(dict(venue_id=v["id"], venue=v["name"], day=day, start=hhmm(st), end=hhmm(st + dur)))
        same.sort(key=lambda x: abs(mins(x["start"]) - mins(s)))
    other = [dict(venue_id=x["id"], venue=x["name"], capacity=x["capacity"], day=day, start=s, end=e)
             for x in venues() if x["id"] != v["id"] and x["capacity"] >= n and not conflicts(x["id"], day, s, e)]
    return dict(same_venue=same[:3], other_venues=other[:4])


def validate(title, day, s, e, n, v):
    if not v:
        return "Please choose a valid venue."
    if not title:
        return "Please give your event a title."
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return "Please pick a valid date."
    if not (TIME_RE.match(s) and TIME_RE.match(e)):
        return "Please pick valid start and end times."
    if s >= e:
        return "End time must be after the start time."
    if s < OPEN or e > CLOSE:
        return f"Venues can be booked between {OPEN} and {CLOSE}."
    now = datetime.now()
    if d < now.date() or (d == now.date() and s <= now.strftime("%H:%M")):
        return "That slot is in the past."
    if n < 1:
        return "Expected attendees must be at least 1."
    return None


# ---------- auth ----------
@app.before_request
def load_user():
    uid = session.get("uid")
    g.user = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None
    # accounts created before the extra details existed must fill them in first
    if g.user and not g.user["phone"] and request.endpoint not in ("profile", "logout", "static") \
            and not request.path.startswith("/api/"):
        flash("Please complete your profile details to continue.", "info")
        return redirect(url_for("profile"))


@app.context_processor
def nav_counts():
    if not g.get("user"):
        return {}
    scope, args = review_scope()
    reviewer = g.user["role"] == "admin" or bool(db().execute(
        "SELECT 1 FROM venues v WHERE " + scope, args).fetchone())
    pending = scalar("SELECT COUNT(*) FROM bookings b JOIN venues v ON v.id=b.venue_id WHERE b.status='pending'"
                     " AND b.day>=? AND " + scope, (date.today().isoformat(), *args))
    return dict(is_reviewer=reviewer, pending_count=pending)


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in again."), 401
            return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return w


def admin_required(f):
    @wraps(f)
    @login_required
    def w(*a, **k):
        if g.user["role"] != "admin":
            abort(403)
        return f(*a, **k)
    return w


def send_code(email, code):
    host = os.environ.get("SMTP_HOST")
    if DEMO_OTP:
        return  # verify page shows the shared code
    if not host:
        print(f"\n  [DEV] Verification code for {email}: {code}\n", flush=True)
        flash("Dev mode: no mail server configured, so the code was printed in the server terminal.", "info")
        return
    msg = EmailMessage()
    msg["Subject"] = "Your NMAMIT Venue Booking verification code"
    msg["From"] = os.environ.get("SMTP_FROM", os.environ["SMTP_USER"])
    msg["To"] = email
    msg.set_content(f"Your verification code is {code}\n\nIf you didn't request this, ignore this email.")
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", form={})
    f = request.form
    email, pw = f.get("email", "").strip().lower(), f.get("password", "")
    if not EMAIL_RE.match(email):
        err = "Only official @nmamit.in or @nitte.edu.in email addresses can register."
    elif len(pw) < 8:
        err = "Password must be at least 8 characters."
    elif (row := db().execute("SELECT verified FROM users WHERE email=?", (email,)).fetchone()) and row["verified"]:
        err = "An account with this email already exists. Please log in."
    else:
        err, p = clean_profile(f)
    if err:
        flash(err, "error")
        return render_template("register.html", form=f)
    code = DEMO_OTP or f"{secrets.randbelow(10 ** 6):06d}"
    db().execute("INSERT INTO users(name,email,pw,utype,dept,id_no,phone,code) VALUES(?,?,?,?,?,?,?,?)"
                 " ON CONFLICT(email) DO UPDATE SET name=excluded.name, pw=excluded.pw, utype=excluded.utype,"
                 " dept=excluded.dept, id_no=excluded.id_no, phone=excluded.phone, code=excluded.code, tries=0",
                 (p["name"], email, generate_password_hash(pw), p["utype"], p["dept"], p["id_no"], p["phone"], code))
    send_code(email, code)
    session["verify"] = email
    return redirect(url_for("verify"))


@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("verify")
    if not email:
        return redirect(url_for("register"))
    if request.method == "POST":
        u = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if u and u["code"] and u["tries"] < 5 and secrets.compare_digest(u["code"], request.form.get("code", "").strip()):
            db().execute("UPDATE users SET verified=1, code=NULL WHERE id=?", (u["id"],))
            session.clear()
            session["uid"] = u["id"]
            flash(f"Welcome, {u['name'].split()[0]}! Your email is verified.", "success")
            return redirect(url_for("calendar"))
        db().execute("UPDATE users SET tries=tries+1 WHERE email=?", (email,))
        locked = not u or u["tries"] >= 4
        flash("Too many attempts. Please register again for a new code." if locked else "Incorrect code, try again.", "error")
    return render_template("verify.html", email=email)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not u or not check_password_hash(u["pw"], request.form.get("password", "")):
            flash("Invalid email or password.", "error")
        elif not u["verified"]:
            session["verify"] = email
            flash("Please verify your email first.", "info")
            return redirect(url_for("verify"))
        else:
            session.clear()
            session["uid"] = u["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("calendar"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- pages ----------
@app.route("/")
def index():
    today = date.today().isoformat()
    one = lambda q, *a: scalar(q, a)
    stats = dict(venues=one("SELECT COUNT(*) FROM venues WHERE active=1"),
                 upcoming=one("SELECT COUNT(*) FROM bookings WHERE status='approved' AND day>=?", today),
                 today=one("SELECT COUNT(*) FROM bookings WHERE status='approved' AND day=?", today))
    return render_template("index.html", stats=stats)


@app.route("/calendar")
@login_required
def calendar():
    return render_template("calendar.html", venues=venues())


@app.route("/book")
@login_required
def book():
    return render_template("book.html", venues=venues(), open=OPEN, close=CLOSE)


@app.route("/finder")
@login_required
def finder():
    facilities = sorted({f for v in venues() for f in v["facilities"].split(",") if f})
    return render_template("finder.html", facilities=facilities)


@app.route("/venues")
@login_required
def venue_list():
    return render_template("venues.html", venues=venues())


@app.route("/my")
@login_required
def my_bookings():
    rows = db().execute("SELECT b.*, v.name venue, v.color, COALESCE(i.name, 'the Admin') approver FROM bookings b"
                        " JOIN venues v ON v.id=b.venue_id LEFT JOIN users i ON i.id=v.incharge_id"
                        " WHERE user_id=? ORDER BY day DESC, start_t DESC", (g.user["id"],)).fetchall()
    return render_template("my.html", rows=rows, today=date.today().isoformat())


@app.route("/approvals")
@login_required
def approvals():
    scope, args = review_scope()
    q = ("SELECT b.*, v.name venue, v.color, v.capacity, u.name uname, u.email, u.utype, u.dept udept, u.id_no,"
         " u.phone FROM bookings b JOIN venues v ON v.id=b.venue_id JOIN users u ON u.id=b.user_id WHERE " + scope)
    today = date.today().isoformat()
    pending = db().execute(q + " AND status='pending' AND day>=? ORDER BY day, start_t", (*args, today)).fetchall()
    upcoming = db().execute(q + " AND status='approved' AND day>=? ORDER BY day, start_t", (*args, today)).fetchall()
    mine = [v for v in venues(False) if g.user["role"] == "admin" or v["incharge_id"] == g.user["id"]]
    if not mine:
        abort(403)
    return render_template("approvals.html", pending=pending, upcoming=upcoming, managed=mine)


@app.route("/admin")
@admin_required
def admin():
    count = lambda q: scalar(q, (date.today().isoformat(),))
    stats = dict(pending=count("SELECT COUNT(*) FROM bookings WHERE status='pending' AND day>=?"),
                 upcoming=count("SELECT COUNT(*) FROM bookings WHERE status='approved' AND day>=?"),
                 users=scalar("SELECT COUNT(*) FROM users WHERE verified=1"))
    users = db().execute("SELECT id, name, email, utype, dept FROM users WHERE verified=1 ORDER BY name").fetchall()
    return render_template("admin.html", stats=stats, venues=venues(False), users=users)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        f = request.form
        if f.get("action") == "password":
            if not check_password_hash(g.user["pw"], f.get("current", "")):
                flash("Your current password is incorrect.", "error")
            elif len(f.get("new", "")) < 8:
                flash("New password must be at least 8 characters.", "error")
            elif f.get("new") != f.get("confirm"):
                flash("The new passwords don't match.", "error")
            else:
                db().execute("UPDATE users SET pw=? WHERE id=?", (generate_password_hash(f["new"]), g.user["id"]))
                flash("Password changed.", "success")
        else:
            err, p = clean_profile(f)
            if err:
                flash(err, "error")
                return render_template("profile.html", form=f, **profile_extras())
            db().execute("UPDATE users SET name=?, utype=?, dept=?, id_no=?, phone=? WHERE id=?",
                         (p["name"], p["utype"], p["dept"], p["id_no"], p["phone"], g.user["id"]))
            flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", form=g.user, **profile_extras())


def profile_extras():
    stats = {r["status"]: r["n"] for r in db().execute(
        "SELECT status, COUNT(*) n FROM bookings WHERE user_id=? GROUP BY status", (g.user["id"],))}
    managed = db().execute("SELECT name, color FROM venues WHERE incharge_id=? ORDER BY name", (g.user["id"],)).fetchall()
    return dict(stats=stats, managed=managed)


@app.post("/admin/venues")
@admin_required
def add_venue():
    f = request.form
    try:
        cap = int(f.get("capacity", ""))
        assert cap > 0 and f.get("name", "").strip()
        db().execute("INSERT INTO venues(name,building,capacity,facilities,color,incharge_id) VALUES(?,?,?,?,?,?)",
                     (f["name"].strip(), f.get("building", "").strip(), cap,
                      ",".join(x.strip() for x in f.get("facilities", "").split(",") if x.strip()),
                      f.get("color") if re.fullmatch(r"#[0-9a-fA-F]{6}", f.get("color", "")) else "#2b2f8f",
                      verified_user(f.get("incharge_id"))))
        flash("Venue added.", "success")
    except (ValueError, AssertionError):
        flash("Enter a venue name and a positive capacity.", "error")
    except IntegrityError:
        flash("A venue with that name already exists.", "error")
    return redirect(url_for("admin") + "#venues")


@app.post("/admin/venues/<int:vid>/toggle")
@admin_required
def toggle_venue(vid):
    db().execute("UPDATE venues SET active=1-active WHERE id=?", (vid,))
    return redirect(url_for("admin") + "#venues")


def verified_user(uid):
    """Id of a verified user, or None (= admin approves)."""
    row = db().execute("SELECT id FROM users WHERE id=? AND verified=1", (int(uid),)).fetchone() if str(uid).isdigit() else None
    return row["id"] if row else None


@app.post("/admin/venues/<int:vid>/incharge")
@admin_required
def set_incharge(vid):
    uid = verified_user(request.form.get("incharge_id"))
    db().execute("UPDATE venues SET incharge_id=? WHERE id=?", (uid, vid))
    v = db().execute("SELECT v.name, u.name iname FROM venues v LEFT JOIN users u ON u.id=v.incharge_id WHERE v.id=?",
                     (vid,)).fetchone()
    flash(f"{v['name']}: requests now go to {v['iname'] or 'the Admin'}.", "success")
    return redirect(url_for("admin") + "#venues")


# ---------- JSON API ----------
@app.get("/api/events")
@login_required
def api_events():
    q = ("SELECT b.*, v.name venue, v.color, v.incharge_id, u.name uname, u.email, i.name iname FROM bookings b"
         " JOIN venues v ON v.id=b.venue_id JOIN users u ON u.id=b.user_id LEFT JOIN users i ON i.id=v.incharge_id"
         " WHERE b.status IN ('pending','approved') AND b.day>=? AND b.day<?")
    args = [request.args.get("start", "")[:10], request.args.get("end", "")[:10]]
    if "venues" in request.args:
        ids = [int(x) for x in request.args["venues"].split(",") if x.isdigit()]
        q += f" AND b.venue_id IN ({','.join('?' * len(ids)) or 'NULL'})"
        args += ids
    return jsonify([dict(
        id=r["id"], title=r["title"], start=f"{r['day']}T{r['start_t']}", end=f"{r['day']}T{r['end_t']}",
        backgroundColor=r["color"], borderColor=r["color"], classNames=[r["status"]],
        extendedProps=dict(venue=r["venue"], status=r["status"], organizer=r["organizer"], attendees=r["attendees"],
                           description=r["description"], by=r["uname"], email=r["email"], incharge=r["iname"] or "Admin",
                           can_cancel=r["user_id"] == g.user["id"] or g.user["role"] == "admin"
                           or r["incharge_id"] == g.user["id"]),
    ) for r in db().execute(q, args)])


@app.get("/api/availability")
@login_required
def api_availability():
    day = request.args.get("day", "")
    try:
        date.fromisoformat(day)
    except ValueError:
        return jsonify(error="Please pick a valid date."), 400
    dur = max(15, request.args.get("duration", 60, type=int))
    n = request.args.get("attendees", 1, type=int)
    fac = request.args.get("facility", "").strip()
    vid = request.args.get("venue", type=int)
    out = []
    for v in venues():
        if (vid and v["id"] != vid) or v["capacity"] < n or (fac and fac not in v["facilities"].split(",")):
            continue
        busy = busy_blocks(v["id"], day)
        out.append(dict(
            id=v["id"], name=v["name"], building=v["building"], capacity=v["capacity"], color=v["color"],
            incharge=v["iname"] or "Admin",
            facilities=[x for x in v["facilities"].split(",") if x],
            busy=[dict(start=b["start_t"], end=b["end_t"], title=b["title"], status=b["status"]) for b in busy],
            free=[dict(start=a, end=b) for a, b in free_windows(busy, day) if mins(b) - mins(a) >= dur]))
    out.sort(key=lambda v: (not v["free"], v["capacity"]))  # smallest venue that fits = best fit
    return jsonify(day=day, venues=out)


@app.post("/api/bookings")
@login_required
def api_book():
    d = request.get_json(silent=True) or {}
    title = str(d.get("title", "")).strip()[:120]
    day, s, e = str(d.get("day", "")), str(d.get("start", "")), str(d.get("end", ""))
    try:
        vid, n = int(d.get("venue_id")), int(d.get("attendees"))
    except (TypeError, ValueError):
        return jsonify(error="Please choose a venue and enter the expected attendees."), 400
    v = db().execute("SELECT * FROM venues WHERE id=? AND active=1", (vid,)).fetchone()
    if err := validate(title, day, s, e, n, v):
        return jsonify(error=err), 400
    if n > v["capacity"]:
        return jsonify(error=f"{v['name']} seats only {v['capacity']}. These venues fit {n} people:",
                       conflicts=[], suggestions=suggest(v, day, s, e, n)), 409
    with venue_lock(vid):
        clash = conflicts(vid, day, s, e)
        if not clash:
            status = "approved" if can_review(vid) else "pending"  # admins / the venue's in-charge skip approval
            bid = scalar(
                "INSERT INTO bookings(user_id,venue_id,title,description,organizer,day,start_t,end_t,attendees,status)"
                " VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING id",
                (g.user["id"], vid, title, str(d.get("description", "")).strip()[:1000],
                 str(d.get("organizer", "")).strip()[:120], day, s, e, n, status))
    if clash:
        return jsonify(error=f"{v['name']} is already booked during that time.",
                       conflicts=[dict(title=c["title"], start=c["start_t"], end=c["end_t"], status=c["status"],
                                       by=c["uname"]) for c in clash],
                       suggestions=suggest(v, day, s, e, n)), 409
    return jsonify(id=bid, status=status), 201


@app.post("/api/bookings/<int:bid>/status")
@login_required
def api_status(bid):
    d = request.get_json(silent=True) or {}
    action = d.get("action")
    b = db().execute("SELECT * FROM bookings WHERE id=?", (bid,)).fetchone()
    if not b:
        return jsonify(error="Booking not found."), 404
    reviewer = can_review(b["venue_id"])
    if action == "cancel":
        if b["user_id"] != g.user["id"] and not reviewer:
            return jsonify(error="You can only cancel your own bookings."), 403
        if b["status"] not in ("pending", "approved"):
            return jsonify(error="This booking is already closed."), 400
    elif action in ("approve", "reject"):
        if not reviewer:
            return jsonify(error="Only this venue's in-charge or an admin can review this request."), 403
        if b["status"] != "pending":
            return jsonify(error="Only pending requests can be reviewed."), 400
    else:
        return jsonify(error="Unknown action."), 400
    new = {"cancel": "cancelled", "approve": "approved", "reject": "rejected"}[action]
    db().execute("UPDATE bookings SET status=?, note=? WHERE id=?", (new, str(d.get("note") or "").strip()[:300] or None, bid))
    return jsonify(status=new)


@app.cli.command("make-admin")
@click.argument("email")
def make_admin(email):
    """Promote a registered user to admin:  flask --app app make-admin someone@nmamit.in"""
    with app.app_context():
        n = db().execute("UPDATE users SET role='admin' WHERE email=?", (email.lower(),)).rowcount
    click.echo(f"{email} is now an admin." if n else f"No user {email}.")


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
