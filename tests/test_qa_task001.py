"""QA checks for TASK-001: register a new repository (POST /repositories).

Written by QA from requirements.md and architecture.md, independently of the
Developer's tests.
"""

import http.client
import json
import threading
import unittest

from app.server import RegistryServer


class QaTask001Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = RegistryServer(("127.0.0.1", 0), quiet=True)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.server.store.reset()

    # --- helpers -----------------------------------------------------------

    def raw(self, method, path, headers=None, data=None):
        """Send a raw request; returns (status, parsed JSON or None)."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, body=data, headers=headers or {})
            response = conn.getresponse()
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
        finally:
            conn.close()

    def call(self, method, path, user=None, body=None):
        headers = {}
        if user is not None:
            headers["X-User"] = user
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self.raw(method, path, headers, data)

    def register(self, body, user="alice"):
        return self.call("POST", "/repositories", user=user, body=body)

    def snapshot(self):
        store = self.server.store
        return (sorted(store.repositories), sorted(store.analyses), store.next_id)

    def assert_nothing_created(self, before):
        self.assertEqual(self.snapshot(), before, "store changed after a refused registration")

    # --- AC1: created, new id, owner is caller, response fields -----------

    def test_ac1_register_with_description(self):
        status, repo = self.register(
            {"name": "  qa-service  ", "url": " https://example.com/qa/service ", "description": "  QA demo  "},
            user="bob",
        )
        self.assertEqual(status, 201, repo)
        self.assertEqual(repo["id"], 5)
        self.assertEqual(repo["owner"], "bob")
        self.assertEqual(repo["name"], "qa-service")
        self.assertEqual(repo["url"], "https://example.com/qa/service")
        self.assertEqual(repo["description"], "QA demo")
        for field in ("registered_at", "last_scanned_at"):
            self.assertIn(field, repo)

    def test_ac1_register_without_description_and_ids_increase(self):
        status, first = self.register({"name": "one", "url": "http://host-one.test/a"})
        self.assertEqual(status, 201, first)
        self.assertEqual(first["description"], "")
        status, second = self.register({"name": "two", "url": "http://host-two.test/b", "description": None})
        self.assertEqual(status, 201, second)
        self.assertEqual(second["description"], "")
        self.assertEqual(second["id"], first["id"] + 1)

    # --- AC2: analysis available straight away ------------------------------

    def test_ac2_analysis_available_without_scan(self):
        _, repo = self.register({"name": "fresh", "url": "https://example.com/fresh"}, user="chen")
        status, analysis = self.call("GET", f"/repositories/{repo['id']}/analysis", user="chen")
        self.assertEqual(status, 200, analysis)
        self.assertEqual(analysis["repository_id"], repo["id"])
        self.assertIn("health_score", analysis)

    # --- AC3: in owner's list, hidden from others ---------------------------

    def test_ac3_visible_to_owner_only(self):
        _, repo = self.register({"name": "mine", "url": "https://example.com/mine"}, user="bob")
        new_id = repo["id"]

        status, bob_list = self.call("GET", "/repositories", user="bob")
        self.assertEqual(status, 200)
        self.assertIn(new_id, [r["id"] for r in bob_list])

        status, alice_list = self.call("GET", "/repositories", user="alice")
        self.assertEqual(status, 200)
        self.assertNotIn(new_id, [r["id"] for r in alice_list])

        self.assertEqual(self.call("GET", f"/repositories/{new_id}", user="bob")[0], 200)
        self.assertEqual(self.call("GET", f"/repositories/{new_id}", user="alice")[0], 403)
        self.assertEqual(self.call("GET", f"/repositories/{new_id}/analysis", user="chen")[0], 403)
        self.assertEqual(self.call("POST", f"/repositories/{new_id}/scan", user="alice")[0], 403)

    # --- AC4: validation, nothing created -----------------------------------

    def test_ac4_invalid_bodies_are_refused(self):
        cases = {
            "name missing": {"url": "https://example.com/x"},
            "name empty": {"name": "", "url": "https://example.com/x"},
            "name only spaces": {"name": "   ", "url": "https://example.com/x"},
            "name not a string": {"name": 123, "url": "https://example.com/x"},
            "name 101 chars": {"name": "n" * 101, "url": "https://example.com/x"},
            "url missing": {"name": "x"},
            "url empty": {"name": "x", "url": "   "},
            "url ftp": {"name": "x", "url": "ftp://example.com/x"},
            "url no scheme": {"name": "x", "url": "example.com/x"},
            "url no host": {"name": "x", "url": "https://"},
            "url only port": {"name": "x", "url": "http://:8080/x"},
            "url broken ipv6": {"name": "x", "url": "http://["},
            "url inner space": {"name": "x", "url": "https://exa mple.com/x"},
            "description 501 chars": {"name": "x", "url": "https://example.com/x", "description": "d" * 501},
            "description not a string": {"name": "x", "url": "https://example.com/x", "description": 5},
        }
        for label, body in cases.items():
            with self.subTest(label):
                before = self.snapshot()
                status, payload = self.register(body)
                self.assertEqual(status, 400, f"{label}: {payload}")
                self.assertIsInstance(payload.get("error"), str)
                self.assertTrue(payload["error"])
                self.assert_nothing_created(before)

    def test_ac4_body_not_a_json_object(self):
        for label, data in {
            "no body": None,
            "json array": b'["name", "url"]',
            "json string": b'"hello"',
            "not json": b"name=x&url=y",
        }.items():
            with self.subTest(label):
                before = self.snapshot()
                headers = {"X-User": "alice", "Content-Type": "application/json"}
                status, payload = self.raw("POST", "/repositories", headers, data)
                self.assertEqual(status, 400, f"{label}: {payload}")
                self.assertIn("error", payload)
                self.assert_nothing_created(before)

    def test_ac4_limits_are_inclusive_after_trimming(self):
        status, repo = self.register(
            {"name": "  " + "n" * 100 + "  ", "url": "https://example.com/limit", "description": " " + "d" * 500 + " "}
        )
        self.assertEqual(status, 201, repo)
        self.assertEqual(len(repo["name"]), 100)
        self.assertEqual(len(repo["description"]), 500)

    # --- AC5: duplicate URL across all users --------------------------------

    def test_ac5_duplicate_url_same_user(self):
        self.assertEqual(self.register({"name": "a", "url": "https://example.com/dup"})[0], 201)
        before = self.snapshot()
        status, payload = self.register({"name": "b", "url": "  https://example.com/dup  "})
        self.assertEqual(status, 409, payload)
        self.assertIn("already registered", payload["error"])
        self.assert_nothing_created(before)

    def test_ac5_duplicate_url_other_user_and_seed(self):
        self.assertEqual(self.register({"name": "a", "url": "https://example.com/shared"}, user="alice")[0], 201)
        before = self.snapshot()
        status, payload = self.register({"name": "b", "url": "https://example.com/shared"}, user="chen")
        self.assertEqual(status, 409, payload)
        self.assertNotIn("alice", payload["error"])
        self.assert_nothing_created(before)

        # A seed repository's URL, owned by bob, registered by alice.
        status, payload = self.register({"name": "copy", "url": "https://github.com/example-org/data-pipeline"})
        self.assertEqual(status, 409, payload)
        self.assertNotIn("bob", payload["error"])
        self.assert_nothing_created(before)

    # --- AC6: unknown or missing user ---------------------------------------

    def test_ac6_missing_empty_or_unknown_user(self):
        body = {"name": "x", "url": "https://example.com/who"}
        for label, user in {"missing": None, "empty": "", "unknown": "mallory"}.items():
            with self.subTest(label):
                before = self.snapshot()
                status, payload = self.register(body, user=user)
                self.assertEqual(status, 401, f"{label}: {payload}")
                self.assertIn("error", payload)
                self.assert_nothing_created(before)

    def test_ac6_unknown_user_refused_like_existing_endpoints(self):
        existing_status, _ = self.call("GET", "/repositories", user="mallory")
        new_status, _ = self.register({"name": "x", "url": "https://example.com/who"}, user="mallory")
        self.assertEqual(new_status, existing_status)

    def test_ac6_user_check_comes_before_validation(self):
        status, _ = self.register({"name": ""}, user="mallory")
        self.assertEqual(status, 401)

    # --- regression: things that worked before the change -------------------

    def test_regression_get_endpoints_keep_alice_default(self):
        status, repos = self.call("GET", "/repositories")
        self.assertEqual(status, 200)
        self.assertEqual(sorted(r["id"] for r in repos), [1, 2])

    def test_regression_seed_repositories_unchanged(self):
        self.register({"name": "extra", "url": "https://example.com/extra"}, user="alice")
        status, repo = self.call("GET", "/repositories/1", user="alice")
        self.assertEqual(status, 200)
        self.assertEqual(repo["name"], "payments-api")
        self.assertEqual(self.call("GET", "/repositories/3", user="bob")[0], 200)
        self.assertEqual(self.call("POST", "/repositories/4/scan", user="chen")[0], 200)
        self.assertEqual(self.call("GET", "/repositories/3", user="alice")[0], 403)
        self.assertEqual(self.call("GET", "/repositories/99", user="alice")[0], 404)


if __name__ == "__main__":
    unittest.main()
