"""QA checks for TASK-001: register a new repository (POST /repositories).

Written by QA from requirements.md and architecture.md, independently of the
Developer's tests. Every check goes through the real HTTP API.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request

from app.server import RegistryServer

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SEED_URLS = {
    1: "https://github.com/example-org/payments-api",
    3: "https://github.com/example-org/data-pipeline",
}
REPO_KEYS = {"id", "name", "url", "description", "owner", "registered_at", "last_scanned_at"}


class QaTask001(unittest.TestCase):
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

    # --- helpers ------------------------------------------------------------

    def call(self, method, path, user=None, body=None, raw=None):
        """user=None sends no X-User header; user="" sends an empty one."""
        if raw is not None:
            data = raw
        else:
            data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, method=method)
        if user is not None:
            request.add_header("X-User", user)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with OPENER.open(request, timeout=5) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"null")

    def register(self, body, user="alice"):
        return self.call("POST", "/repositories", user=user, body=body)

    def snapshot(self):
        store = self.server.store
        return (store.next_id, sorted(store.repositories), sorted(store.analyses))

    def assert_refused(self, status_expected, body=None, user="alice", raw=None):
        before = self.snapshot()
        status, payload = self.call("POST", "/repositories", user=user, body=body, raw=raw)
        self.assertEqual(status, status_expected, f"body={body!r} raw={raw!r} -> {payload}")
        self.assertIsInstance(payload, dict)
        self.assertTrue(payload.get("error"), f"no clear error message: {payload}")
        self.assertEqual(self.snapshot(), before, "something was created on a refused request")
        return payload

    # --- AC1: created with a new id, owned by the caller ----------------------

    def test_ac1_register_with_description(self):
        status, repo = self.register(
            {"name": "  qa-service  ", "url": "  https://example.com/qa/service  ", "description": "  QA tool  "},
            user="bob",
        )
        self.assertEqual(status, 201, repo)
        self.assertEqual(set(repo), REPO_KEYS)
        self.assertEqual(repo["id"], 5)
        self.assertEqual(repo["name"], "qa-service")
        self.assertEqual(repo["url"], "https://example.com/qa/service")
        self.assertEqual(repo["description"], "QA tool")
        self.assertEqual(repo["owner"], "bob")
        self.assertEqual(repo["registered_at"], repo["last_scanned_at"])

    def test_ac1_register_without_description(self):
        status, repo = self.register({"name": "no-desc", "url": "http://host.example"})
        self.assertEqual(status, 201, repo)
        self.assertEqual(repo["description"], "")
        self.assertEqual(repo["owner"], "alice")
        status, repo = self.register({"name": "null-desc", "url": "http://host2.example", "description": None})
        self.assertEqual(status, 201, repo)
        self.assertEqual(repo["description"], "")

    def test_ac1_each_registration_gets_a_new_id(self):
        _, first = self.register({"name": "a", "url": "https://a.example"})
        _, second = self.register({"name": "b", "url": "https://b.example"}, user="chen")
        self.assertEqual((first["id"], second["id"]), (5, 6))
        status, fetched = self.call("GET", "/repositories/5", user="alice")
        self.assertEqual(status, 200)
        self.assertEqual(fetched, first)

    def test_ac1_limits_are_inclusive(self):
        status, repo = self.register({"name": "n" * 100, "url": "https://limits.example", "description": "d" * 500})
        self.assertEqual(status, 201, repo)
        self.assertEqual((len(repo["name"]), len(repo["description"])), (100, 500))

    # --- AC2: analysis available straight away --------------------------------

    def test_ac2_analysis_without_scan(self):
        _, repo = self.register({"name": "fresh", "url": "https://fresh.example/repo"}, user="chen")
        status, analysis = self.call("GET", f"/repositories/{repo['id']}/analysis", user="chen")
        self.assertEqual(status, 200, analysis)
        self.assertEqual(analysis["repository_id"], repo["id"])

    # --- AC3: owner sees it; others can't -------------------------------------

    def test_ac3_owner_lists_it_others_cannot_see_or_open(self):
        _, repo = self.register({"name": "private", "url": "https://private.example"}, user="bob")
        rid = repo["id"]

        status, bob_list = self.call("GET", "/repositories", user="bob")
        self.assertEqual(status, 200)
        self.assertIn(rid, [r["id"] for r in bob_list])

        for other in ("alice", "chen"):
            _, other_list = self.call("GET", "/repositories", user=other)
            self.assertNotIn(rid, [r["id"] for r in other_list], other)
            self.assertEqual(self.call("GET", f"/repositories/{rid}", user=other)[0], 403, other)
            self.assertEqual(self.call("GET", f"/repositories/{rid}/analysis", user=other)[0], 403, other)
            self.assertEqual(self.call("POST", f"/repositories/{rid}/scan", user=other)[0], 403, other)

        # No X-User on GET defaults to alice, who must not see bob's repository.
        self.assertEqual(self.call("GET", f"/repositories/{rid}")[0], 403)

    # --- AC4: validation, nothing created -------------------------------------

    def test_ac4_invalid_name(self):
        for body in (
            {"url": "https://x.example"},
            {"name": "", "url": "https://x.example"},
            {"name": "   ", "url": "https://x.example"},
            {"name": None, "url": "https://x.example"},
            {"name": 42, "url": "https://x.example"},
            {"name": "n" * 101, "url": "https://x.example"},
        ):
            with self.subTest(body=body):
                self.assert_refused(400, body)

    def test_ac4_invalid_url(self):
        for url in (
            None, "", "   ", 123,
            "example.com", "www.example.com/repo",
            "ftp://example.com/repo", "file:///etc/passwd", "javascript:alert(1)",
            "https://", "http:///path-only", "http://:8080",
            "https://exa mple.com", "https://example.com/a\tb",
            "http://[", "https://[::1",
        ):
            body = {"name": "bad-url"} if url is None else {"name": "bad-url", "url": url}
            with self.subTest(url=url):
                self.assert_refused(400, body)

    def test_ac4_invalid_description(self):
        for description in ("d" * 501, 7, ["list"], {"a": 1}):
            with self.subTest(description=description):
                self.assert_refused(400, {"name": "x", "url": "https://desc.example", "description": description})

    def test_ac4_bad_bodies(self):
        self.assert_refused(400, body=None)                   # no body at all
        self.assert_refused(400, raw=b"[1, 2]")               # JSON, but not an object
        self.assert_refused(400, raw=b'"just a string"')
        self.assert_refused(400, raw=b"{not json")            # not JSON

    def test_ac4_error_names_the_field(self):
        payload = self.assert_refused(400, {"name": "n" * 101, "url": "https://x.example"})
        self.assertIn("name", payload["error"])
        payload = self.assert_refused(400, {"name": "x", "url": "nope"})
        self.assertIn("url", payload["error"])
        payload = self.assert_refused(400, {"name": "x", "url": "https://x.example", "description": "d" * 501})
        self.assertIn("description", payload["error"])

    # --- AC5: a URL can be registered only once --------------------------------

    def test_ac5_duplicate_of_seed_url_any_owner(self):
        for user in ("alice", "chen"):  # alice owns seed 1; chen owns neither
            with self.subTest(user=user):
                payload = self.assert_refused(409, {"name": "copy", "url": SEED_URLS[1]}, user=user)
                self.assertIn("already registered", payload["error"].lower())
                self.assertNotIn("alice", payload["error"])  # must not leak the owner

    def test_ac5_duplicate_of_new_url_same_and_other_user(self):
        status, _ = self.register({"name": "orig", "url": "https://dup.example/r"}, user="bob")
        self.assertEqual(status, 201)
        self.assert_refused(409, {"name": "again", "url": "https://dup.example/r"}, user="bob")
        self.assert_refused(409, {"name": "again", "url": "  https://dup.example/r  "}, user="chen")

    def test_ac5_only_exact_text_counts_as_same(self):
        # Product Owner's assumption: exact text match after trimming.
        status, _ = self.register({"name": "slash", "url": SEED_URLS[3] + "/"}, user="bob")
        self.assertEqual(status, 201)

    # --- AC6: unknown or missing user ------------------------------------------

    def test_ac6_missing_empty_or_unknown_user(self):
        body = {"name": "anon", "url": "https://anon.example"}
        self.assert_refused(401, body, user=None)       # no X-User header
        self.assert_refused(401, body, user="")         # empty X-User header
        self.assert_refused(401, body, user="mallory")  # unknown user
        # Same as today: an unknown user on an existing endpoint is also 401.
        self.assertEqual(self.call("GET", "/repositories", user="mallory")[0], 401)

    def test_ac6_user_checked_before_body(self):
        self.assert_refused(401, {"name": ""}, user="mallory")
        self.assert_refused(401, {"name": "x", "url": SEED_URLS[1]}, user=None)

    # --- Regression: what worked before still works ----------------------------

    def test_regression_seed_data_unchanged_after_registering(self):
        before = {rid: dict(r) for rid, r in self.server.store.repositories.items()}
        self.register({"name": "new", "url": "https://new.example"})
        for rid, repo in before.items():
            self.assertEqual(self.server.store.repositories[rid], repo)

        status, repos = self.call("GET", "/repositories")  # GET still defaults to alice
        self.assertEqual(status, 200)
        self.assertEqual([r["id"] for r in repos], [1, 2, 5])
        self.assertEqual(self.call("GET", "/repositories/3", user="bob")[0], 200)
        self.assertEqual(self.call("POST", "/repositories/4/scan", user="chen")[0], 200)
        self.assertEqual(self.call("GET", "/repositories/999")[0], 404)

    def test_regression_other_methods_on_collection(self):
        status, _ = self.call("DELETE", "/repositories", user="alice")
        self.assertEqual(status, 405)


if __name__ == "__main__":
    unittest.main()
