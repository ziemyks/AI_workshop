import json
import threading
import unittest
import urllib.error
import urllib.request

from app.server import RegistryServer

# Ignore any system proxy: these requests go to a server on this machine.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = RegistryServer(("127.0.0.1", 0), quiet=True)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.server.store.reset()

    def call(self, method, path, user=None, body=None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, method=method)
        if user:
            request.add_header("X-User", user)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with OPENER.open(request, timeout=5) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"null")

    def test_health(self):
        self.assertEqual(self.call("GET", "/health"), (200, {"status": "ok"}))

    def test_list_defaults_to_alice(self):
        status, repos = self.call("GET", "/repositories")
        self.assertEqual(status, 200)
        self.assertEqual([repo["owner"] for repo in repos], ["alice", "alice"])

    def test_list_for_another_user(self):
        status, repos = self.call("GET", "/repositories", user="bob")
        self.assertEqual(status, 200)
        self.assertEqual([repo["name"] for repo in repos], ["data-pipeline"])

    def test_unknown_user(self):
        status, _ = self.call("GET", "/repositories", user="mallory")
        self.assertEqual(status, 401)

    def test_other_users_repository_is_forbidden(self):
        status, _ = self.call("GET", "/repositories/3", user="alice")
        self.assertEqual(status, 403)

    def test_missing_repository(self):
        status, _ = self.call("GET", "/repositories/999")
        self.assertEqual(status, 404)

    def test_analysis_and_scan(self):
        status, analysis = self.call("GET", "/repositories/1/analysis")
        self.assertEqual(status, 200)
        self.assertEqual(analysis["repository_id"], 1)

        status, rescanned = self.call("POST", "/repositories/1/scan")
        self.assertEqual(status, 200)
        self.assertNotEqual(rescanned["scanned_at"], analysis["scanned_at"])

    def test_unknown_endpoint(self):
        status, _ = self.call("GET", "/nope")
        self.assertEqual(status, 404)

    def test_wrong_method(self):
        status, _ = self.call("PUT", "/health")
        self.assertEqual(status, 405)

    def test_invalid_json_body(self):
        request = urllib.request.Request(
            self.base + "/repositories/1/scan", data=b"{not json", method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            OPENER.open(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)

    # TASK-001: register a repository

    NEW = {"name": "  docs-site ", "url": " https://github.com/example-org/docs-site ", "description": " Docs "}

    def test_register_creates_owned_repository_with_analysis(self):
        status, repo = self.call("POST", "/repositories", user="bob", body=self.NEW)
        self.assertEqual(status, 201)
        self.assertEqual(repo["id"], 5)
        self.assertEqual(
            (repo["name"], repo["url"], repo["description"], repo["owner"]),
            ("docs-site", "https://github.com/example-org/docs-site", "Docs", "bob"),
        )
        self.assertEqual(repo["registered_at"], repo["last_scanned_at"])
        self.assertEqual(self.call("GET", "/repositories/5/analysis", user="bob")[0], 200)
        self.assertIn("docs-site", [r["name"] for r in self.call("GET", "/repositories", user="bob")[1]])
        self.assertNotIn("docs-site", [r["name"] for r in self.call("GET", "/repositories", user="alice")[1]])
        self.assertEqual(self.call("GET", "/repositories/5", user="alice")[0], 403)
        self.assertEqual(self.call("GET", "/repositories/5/analysis", user="alice")[0], 403)

    def test_register_description_is_optional(self):
        status, repo = self.call("POST", "/repositories", user="alice", body={"name": "a", "url": "http://x.org"})
        self.assertEqual((status, repo["description"]), (201, ""))

    def test_register_rejects_invalid_input(self):
        bad_bodies = [
            {"url": "https://x.org/a"},
            {"name": "  ", "url": "https://x.org/a"},
            {"name": "a"},
            {"name": "a", "url": ""},
            {"name": "a", "url": "ftp://x.org/a"},
            {"name": "a", "url": "https://"},
            {"name": "a", "url": "http://["},
            {"name": "a", "url": "https://x.org/a b"},
            {"name": "n" * 101, "url": "https://x.org/a"},
            {"name": "a", "url": "https://x.org/a", "description": "d" * 501},
            {"name": 5, "url": "https://x.org/a"},
            ["not", "an", "object"],
        ]
        for body in bad_bodies:
            with self.subTest(body=body):
                self.assertEqual(self.call("POST", "/repositories", user="alice", body=body)[0], 400)
        self.assertEqual(len(self.server.store.repositories), 4)

    def test_register_limits_are_inclusive(self):
        body = {"name": "n" * 100, "url": "https://x.org/a", "description": "d" * 500}
        self.assertEqual(self.call("POST", "/repositories", user="alice", body=body)[0], 201)

    def test_register_duplicate_url_conflicts(self):
        self.assertEqual(self.call("POST", "/repositories", user="bob", body=self.NEW)[0], 201)
        for user in ("bob", "chen"):
            status, error = self.call("POST", "/repositories", user=user, body=self.NEW)
            self.assertEqual((status, error), (409, {"error": "This URL is already registered"}))
        seed_url = {"name": "copy", "url": "https://github.com/example-org/payments-api"}
        self.assertEqual(self.call("POST", "/repositories", user="chen", body=seed_url)[0], 409)
        self.assertEqual(len(self.server.store.repositories), 5)

    def test_register_requires_known_user(self):
        for user in (None, "mallory"):
            with self.subTest(user=user):
                self.assertEqual(self.call("POST", "/repositories", user=user, body=self.NEW)[0], 401)
        self.assertEqual(len(self.server.store.repositories), 4)
        # Other endpoints keep the alice default.
        self.assertEqual(self.call("GET", "/repositories")[0], 200)


if __name__ == "__main__":
    unittest.main()
