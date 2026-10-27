"""Run:  python -m unittest test_app -v"""
import os
import tempfile
import unittest
from datetime import date, timedelta

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
from app import app  # noqa: E402

DAY = (date.today() + timedelta(days=10)).isoformat()


class BookingTest(unittest.TestCase):
    def client(self, email="demo@nmamit.in", pw="Demo@123"):
        c = app.test_client()
        c.post("/login", data={"email": email, "password": pw})
        return c

    def book(self, c, s, e, venue=5, n=50):
        return c.post("/api/bookings", json=dict(title="T", venue_id=venue, day=DAY, start=s, end=e, attendees=n))

    def test_flow(self):
        c = self.client()
        # outsiders can't register
        r = app.test_client().post("/register", data=dict(name="X", email="x@gmail.com", password="password1"))
        self.assertIn(b"Only official", r.data)
        # every page renders
        for p in ["/", "/calendar", "/book", "/finder", "/venues", "/my"]:
            self.assertEqual(c.get(p).status_code, 200, p)
        self.assertEqual(c.get("/admin").status_code, 403)

        self.assertEqual(self.book(c, "10:00", "12:00").json["status"], "pending")
        r = self.book(c, "11:00", "13:00")  # overlaps
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json["suggestions"]["same_venue"][0]["start"], "12:00")  # nearest free time
        self.assertTrue(r.json["suggestions"]["other_venues"])
        self.assertEqual(self.book(c, "12:00", "13:00").status_code, 201)  # touching is fine
        self.assertEqual(self.book(c, "13:00", "14:00", n=9999).status_code, 409)  # over capacity
        self.assertEqual(self.book(c, "14:00", "13:00").status_code, 400)  # end before start
        self.assertEqual(self.book(c, "06:00", "08:00").status_code, 400)  # outside hours

        # finder hides the busy 10-13 block and too-small venues
        v = c.get(f"/api/availability?day={DAY}&venue=5&duration=60").json["venues"][0]
        self.assertEqual(v["free"], [{"start": "07:00", "end": "10:00"}, {"start": "13:00", "end": "21:00"}])
        self.assertFalse(c.get(f"/api/availability?day={DAY}&attendees=5000").json["venues"])

        # admin approves; user cancel frees the slot
        a = self.client("admin@nmamit.in", "Admin@123")
        self.assertEqual(a.get("/admin").status_code, 200)
        bid = self.book(c, "15:00", "16:00").json["id"]
        self.assertEqual(c.post(f"/api/bookings/{bid}/status", json={"action": "approve"}).status_code, 403)
        self.assertEqual(a.post(f"/api/bookings/{bid}/status", json={"action": "approve"}).json["status"], "approved")
        self.assertEqual(c.post(f"/api/bookings/{bid}/status", json={"action": "cancel"}).json["status"], "cancelled")
        self.assertEqual(self.book(c, "15:00", "16:00").status_code, 201)
        events = c.get(f"/api/events?start={DAY}&end=9999-01-01&venues=5").json
        self.assertEqual(len(events), 3)

    def test_incharge(self):
        c, ic = self.client(), self.client("incharge@nmamit.in", "Incharge@123")
        self.assertEqual(c.get("/approvals").status_code, 403)
        self.assertIn(b"Project Expo Briefing", ic.get("/approvals").data)  # seeded pending on ISE hall
        mine = self.book(c, "09:00", "10:00", venue=3).json["id"]       # ISE hall: in-charge's venue
        other = self.book(c, "09:00", "10:00", venue=4).json["id"]      # CSE hall: admin's
        self.assertEqual(ic.post(f"/api/bookings/{other}/status", json={"action": "approve"}).status_code, 403)
        self.assertEqual(ic.post(f"/api/bookings/{mine}/status", json={"action": "approve"}).json["status"], "approved")
        self.assertEqual(self.book(ic, "11:00", "12:00", venue=7).json["status"], "approved")  # own venue: instant
        # admin hands CSE hall to the in-charge too
        a = self.client("admin@nmamit.in", "Admin@123")
        a.post("/admin/venues/4/incharge", data={"incharge_id": "3"})
        self.assertEqual(ic.post(f"/api/bookings/{other}/status", json={"action": "reject", "note": "x"}).json["status"], "rejected")

    def test_register_and_profile(self):
        c = app.test_client()
        base = dict(name="Asha K", email="asha@nitte.edu.in", password="password1", utype="Student", dept="ISE",
                    id_no="nnm23is010", phone="+91 98450 12345")
        self.assertIn(b"valid 10-digit", c.post("/register", data={**base, "phone": "12345"}).data)
        self.assertIn(b"choose your department", c.post("/register", data={**base, "dept": "XYZ"}).data)
        self.assertEqual(c.post("/register", data=base).status_code, 302)
        from app import db
        with app.app_context():
            u = db().execute("SELECT * FROM users WHERE email='asha@nitte.edu.in'").fetchone()
        self.assertEqual((u["id_no"], u["phone"]), ("NNM23IS010", "9845012345"))
        c.post("/verify", data={"code": u["code"]})
        self.assertEqual(c.get("/calendar").status_code, 200)
        c.post("/profile", data={**base, "name": "Asha Kumari", "action": "profile"})
        self.assertIn(b"Asha Kumari", c.get("/profile").data)
        c.post("/profile", data={"action": "password", "current": "password1", "new": "newpass99", "confirm": "newpass99"})
        c2 = self.client("asha@nitte.edu.in", "newpass99")
        self.assertEqual(c2.get("/my").status_code, 200)

    def test_old_account_must_complete_profile(self):
        from app import db
        with app.app_context():
            db().execute("INSERT INTO users(name,email,pw,verified) VALUES('Old','old@nmamit.in',"
                         "(SELECT pw FROM users WHERE id=2),1)")
        c = self.client("old@nmamit.in")
        self.assertIn("/profile", c.get("/calendar").headers["Location"])


if __name__ == "__main__":
    unittest.main()
