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


if __name__ == "__main__":
    unittest.main()
