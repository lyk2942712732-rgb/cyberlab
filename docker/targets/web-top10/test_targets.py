"""Run using python -m unittest -v in this directory; no Docker required."""
import base64
import html
import json
import threading
import unittest
from contextlib import contextmanager
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener
from app import InternalHandler, LabServer, SCENARIOS

FLAG = "flag{test_only}"


@contextmanager
def target(scenario):
    server = LabServer(("127.0.0.1", 0), scenario, FLAG)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
    def request(path, form=None):
        try:
            response = browser.open(f"http://127.0.0.1:{server.server_port}" + path, None if form is None else urlencode(form).encode(), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, html.unescape(response.read().decode())
    try:
        yield request, server
    finally:
        server.shutdown(); server.server_close(); thread.join()


class TargetTests(unittest.TestCase):
    def test_all_homepages_and_health(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario), target(scenario) as (get, _):
                self.assertEqual(get("/health"), (200, "ok"))
                self.assertNotIn(FLAG, get("/")[1])
                self.assertEqual(get("/nonexistent")[0], 404)

    def test_access(self):
        with target("access") as (get, _):
            self.assertNotIn(FLAG, get("/orders?id=1001")[1])
            self.assertIn(FLAG, get("/orders?id=1002")[1])

    def test_config(self):
        with target("config") as (get, _):
            self.assertIn("/backup/config.json", get("/robots.txt")[1])
            self.assertIn(FLAG, get("/backup/config.json")[1])

    def test_supply(self):
        with target("supply") as (get, _):
            self.assertNotIn(FLAG, get("/install", {"source": "official", "package": "lesson-theme"})[1])
            self.assertIn(FLAG, get("/install", {"source": "community", "package": "lesson-theme"})[1])

    def test_crypto(self):
        with target("crypto") as (get, _):
            secret = json.loads(get("/backup")[1])["encrypted_secret"]
            self.assertEqual(base64.b64decode(secret).decode(), FLAG)

    def test_sqli(self):
        with target("sqli") as (get, _):
            self.assertEqual(get("/login", {"username": "admin", "password": "wrong"})[0], 403)
            self.assertIn(FLAG, get("/login", {"username": "admin' -- ", "password": "wrong"})[1])

    def test_design(self):
        with target("design") as (get, _):
            self.assertNotIn(FLAG, get("/buy", {})[1])
            get("/redeem", {"coupon": "WELCOME"})
            self.assertNotIn(FLAG, get("/buy", {})[1])
            get("/redeem", {"coupon": "WELCOME"})
            self.assertIn(FLAG, get("/buy", {})[1])

    def test_auth(self):
        with target("auth") as (get, _):
            self.assertNotIn(FLAG, get("/reset-password", {"username": "student"})[1])
            self.assertIn(FLAG, get("/reset-password", {"username": "admin"})[1])

    def test_integrity(self):
        with target("integrity") as (get, _):
            token = get("/token")[1]
            self.assertNotIn(FLAG, get("/profile", {"token": token})[1])
            token = base64.b64encode(b'{"user":"student","role":"admin"}').decode()
            self.assertIn(FLAG, get("/profile", {"token": token})[1])
            self.assertEqual(get("/profile", {"token": "!!!"})[0], 400)

    def test_logging(self):
        with target("logging") as (get, _):
            for pin in ("00", "01", "02"):
                self.assertEqual(get("/pin", {"pin": pin})[0], 403)
            audit = json.loads(get("/audit")[1])
            self.assertEqual(audit["failed_logins"], [])
            self.assertEqual(audit["alerts"], [])
            self.assertIn(FLAG, get("/pin", {"pin": "03"})[1])

    def test_exception(self):
        with target("exception") as (get, _):
            self.assertEqual(get("/vault", {"policy_version": "1"})[0], 403)
            self.assertIn(FLAG, get("/vault", {"policy_version": "oops"})[1])

    def test_xss_reflection(self):
        with target("xss") as (get, _):
            payload = '<script>document.title="xss-proved"</script>'
            self.assertIn(payload, get("/search?" + urlencode({"q": payload}))[1])

    def test_ssrf(self):
        internal = ThreadingHTTPServer(("127.0.0.1", 0), InternalHandler)
        internal.flag = FLAG
        thread = threading.Thread(target=internal.serve_forever, daemon=True); thread.start()
        try:
            with target("ssrf") as (get, server):
                server.internal_port = internal.server_port
                self.assertEqual(get("/preview?" + urlencode({"url": "http://example.com/"}))[0], 400)
                self.assertIn(FLAG, get("/preview?" + urlencode({"url": f"http://127.0.0.1:{internal.server_port}/admin"}))[1])
        finally:
            internal.shutdown(); internal.server_close(); thread.join()


if __name__ == "__main__":
    unittest.main()
