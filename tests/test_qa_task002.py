"""QA checks for TASK-002: remove an owned repository (DELETE /repositories/{id}).

Written by QA from requirements.md and architecture.md, independently of the
Developer's tests. Every check goes through the real HTTP API.
"""

import json
import threading
import unittest
import urllib.error
import urllib.request
from copy import deepcopy

from app.server import RegistryServer

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Seed data: alice owns 1 and 2, bob owns 3, chen owns 4.
PAYMENTS_URL = "https://github.com/example-org/payments-api"


class QaTask002(unittest.TestCase):
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
        data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
        request = urllib.request.Request(self.base + path, data=data, method=method)
        if user is not None:
            request.add_header("X-User", user)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with OPENER.open(request, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def json_call(self, method, path, user=None, body=None):
        status, raw = self.call(method, path, user=user, body=body)
        return status, json.loads(raw or b"null")

    def remove(self, repository_id, user="alice"):
        return self.call("DELETE", f"/repositories/{repository_id}", user=user)

    def snapshot(self):
        store = self.server.store
        return deepcopy((store.next_id, store.repositories, store.analyses))

    def assert_refused(self, status_expected, repository_id, user):
        before = self.snapshot()
        status, raw = self.remove(repository_id, user=user)
        self.assertEqual(status, status_expected, raw)
        payload = json.loads(raw)
        self.assertTrue(payload.get("error"), f"no clear error message: {payload}")
        self.assertEqual(self.snapshot(), before, "something changed on a refused removal")
        return payload

    # --- AC1: owner removes it; it leaves their list --------------------------

    def test_ac1_owner_removes_seed_repository(self):
        status, raw = self.remove(2, user="alice")
        self.assertEqual(status, 204)
        self.assertEqual(raw, b"")
        _, repos = self.json_call("GET", "/repositories", user="alice")
        self.assertEqual([r["id"] for r in repos], [1])

    def test_ac1_owner_removes_newly_registered_repository(self):
        _, repo = self.json_call("POST", "/repositories", user="bob",
                                 body={"name": "oops", "url": "https://oops.example"})
        self.assertEqual(self.remove(repo["id"], user="bob")[0], 204)
        _, repos = self.json_call("GET", "/repositories", user="bob")
        self.assertEqual([r["id"] for r in repos], [3])

    # --- AC2: gone everywhere, answers like a never-existing id ---------------

    def test_ac2_removed_repository_answers_not_found(self):
        self.assertEqual(self.remove(1, user="alice")[0], 204)
        _, never = self.json_call("GET", "/repositories/999", user="alice")
        checks = {
            "get": self.json_call("GET", "/repositories/1", user="alice"),
            "analysis": self.json_call("GET", "/repositories/1/analysis", user="alice"),
            "scan": self.json_call("POST", "/repositories/1/scan", user="alice"),
            "second delete": (self.remove(1, user="alice")[0], json.loads(self.remove(1, user="alice")[1])),
        }
        for name, (status, payload) in checks.items():
            with self.subTest(request=name):
                self.assertEqual(status, 404, payload)
                # Same wording as an id that never existed, only the id differs.
                self.assertEqual(payload["error"], never["error"].replace("999", "1"))
        self.assertNotIn(1, self.server.store.analyses)

    # --- AC3: someone else's repository is refused with 403 -------------------

    def test_ac3_other_users_repository_is_forbidden_and_unchanged(self):
        _, opened = self.json_call("GET", "/repositories/3", user="alice")  # today's refusal
        payload = self.assert_refused(403, 3, user="alice")
        self.assertEqual(payload["error"], opened["error"])
        self.assertNotIn("bob", payload["error"])  # doesn't leak the owner
        self.assertEqual(self.json_call("GET", "/repositories/3", user="bob")[0], 200)
        self.assertEqual(self.json_call("GET", "/repositories/3/analysis", user="bob")[0], 200)

    def test_ac3_cannot_remove_another_users_new_repository(self):
        _, repo = self.json_call("POST", "/repositories", user="chen",
                                 body={"name": "chen-new", "url": "https://chen.example"})
        for other in ("alice", "bob"):
            with self.subTest(user=other):
                self.assert_refused(403, repo["id"], user=other)

    # --- AC4: missing, empty or unknown user gets 401 ---------------------------

    def test_ac4_missing_empty_or_unknown_user(self):
        for user in (None, "", "mallory"):
            for repository_id in (1, 3, 999):  # own-by-alice, someone else's, missing
                with self.subTest(user=user, repository_id=repository_id):
                    self.assert_refused(401, repository_id, user=user)

    def test_ac4_same_refusal_as_registering(self):
        _, registering = self.json_call("POST", "/repositories", user=None,
                                        body={"name": "x", "url": "https://x.example"})
        payload = self.assert_refused(401, 1, user=None)
        self.assertEqual(payload["error"], registering["error"])

    # --- AC5: the URL is free again ---------------------------------------------

    def test_ac5_url_can_be_registered_again_by_anyone(self):
        self.assertEqual(self.remove(1, user="alice")[0], 204)
        status, again = self.json_call("POST", "/repositories", user="chen",
                                       body={"name": "payments-api", "url": PAYMENTS_URL})
        self.assertEqual(status, 201, again)
        self.assertEqual(again["id"], 5)  # new id, old id 1 not reused
        self.assertEqual(again["owner"], "chen")
        status, analysis = self.json_call("GET", "/repositories/5/analysis", user="chen")
        self.assertEqual(status, 200)
        self.assertEqual(analysis["repository_id"], 5)
        # The old id stays gone.
        self.assertEqual(self.json_call("GET", "/repositories/1", user="alice")[0], 404)

    def test_ac5_former_owner_can_register_it_again(self):
        _, first = self.json_call("POST", "/repositories", user="bob",
                                  body={"name": "typo", "url": "https://again.example"})
        self.assertEqual(self.remove(first["id"], user="bob")[0], 204)
        status, second = self.json_call("POST", "/repositories", user="bob",
                                        body={"name": "fixed", "url": "https://again.example"})
        self.assertEqual(status, 201, second)
        self.assertEqual(second["id"], first["id"] + 1)

    # --- AC6: nothing else changes ----------------------------------------------

    def test_ac6_other_repositories_and_analyses_unchanged(self):
        store = self.server.store
        before_repos = deepcopy(store.repositories)
        before_analyses = deepcopy(store.analyses)
        self.assertEqual(self.remove(2, user="alice")[0], 204)
        for rid in (1, 3, 4):
            self.assertEqual(store.repositories[rid], before_repos[rid], rid)
            self.assertEqual(store.analyses[rid], before_analyses[rid], rid)
        self.assertEqual(self.json_call("GET", "/repositories/1", user="alice")[0], 200)
        _, bob_list = self.json_call("GET", "/repositories", user="bob")
        _, chen_list = self.json_call("GET", "/repositories", user="chen")
        self.assertEqual(([r["id"] for r in bob_list], [r["id"] for r in chen_list]), ([3], [4]))

    # --- Wrong input and regression ---------------------------------------------

    def test_wrong_input_non_numeric_or_bad_body(self):
        self.assertEqual(self.remove("abc", user="alice")[0], 404)  # no such endpoint
        status, _ = self.call("DELETE", "/repositories/1", user="alice", raw=b"{not json")
        self.assertEqual(status, 400)
        self.assertIn(1, self.server.store.repositories)

    def test_regression_collection_delete_and_get_default(self):
        self.assertEqual(self.call("DELETE", "/repositories", user="alice")[0], 405)
        status, repos = self.json_call("GET", "/repositories")  # GET still defaults to alice
        self.assertEqual(status, 200)
        self.assertEqual([r["id"] for r in repos], [1, 2])
        self.assertEqual(self.json_call("POST", "/repositories/4/scan", user="chen")[0], 200)


if __name__ == "__main__":
    unittest.main()
