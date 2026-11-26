import unittest

from app import analyzer, service
from app.store import Store


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()

    def test_list_shows_only_my_repositories(self):
        names = [repo["name"] for repo in service.list_repositories(self.store, "alice")]
        self.assertEqual(names, ["payments-api", "web-portal"])

    def test_unknown_user_is_rejected(self):
        with self.assertRaises(service.Unauthorized):
            service.list_repositories(self.store, "mallory")

    def test_cannot_open_someone_elses_repository(self):
        with self.assertRaises(service.Forbidden):
            service.get_repository(self.store, "bob", 1)

    def test_missing_repository(self):
        with self.assertRaises(service.NotFound):
            service.get_repository(self.store, "alice", 999)

    def test_scan_updates_time_and_analysis(self):
        before = service.get_repository(self.store, "alice", 1)["last_scanned_at"]
        analysis = service.scan_repository(self.store, "alice", 1)
        after = service.get_repository(self.store, "alice", 1)["last_scanned_at"]
        self.assertNotEqual(before, after)
        self.assertEqual(analysis["scanned_at"], after)

    def test_analysis_is_stable_for_the_same_url(self):
        repo = self.store.repositories[1]
        first = analyzer.analyze(repo, "2026-01-01T00:00:00Z")
        second = analyzer.analyze(repo, "2026-01-01T00:00:00Z")
        self.assertEqual(first, second)
        self.assertEqual(sum(first["languages"].values()), 100)

    # --- TASK-002: remove a repository ---

    def test_remove_deletes_repository_and_analysis(self):
        self.assertIsNone(service.remove_repository(self.store, "alice", 1))
        self.assertNotIn(1, self.store.repositories)
        self.assertNotIn(1, self.store.analyses)
        names = [repo["name"] for repo in service.list_repositories(self.store, "alice")]
        self.assertEqual(names, ["web-portal"])

    def test_removed_repository_is_not_found_everywhere(self):
        service.remove_repository(self.store, "alice", 1)
        for call in (service.get_repository, service.get_analysis,
                     service.scan_repository, service.remove_repository):
            with self.assertRaises(service.NotFound):
                call(self.store, "alice", 1)

    def test_remove_someone_elses_repository_is_forbidden_and_changes_nothing(self):
        before = dict(self.store.analyses[3])
        with self.assertRaises(service.Forbidden):
            service.remove_repository(self.store, "alice", 3)
        self.assertIn(3, self.store.repositories)
        self.assertEqual(self.store.analyses[3], before)

    def test_remove_needs_a_known_user(self):
        for user in (None, "", "mallory"):
            with self.assertRaises(service.Unauthorized):
                service.remove_repository(self.store, user, 1)
        self.assertIn(1, self.store.repositories)

    def test_remove_unknown_id_is_not_found(self):
        with self.assertRaises(service.NotFound):
            service.remove_repository(self.store, "alice", 999)

    def test_url_can_be_registered_again_with_a_new_id(self):
        url = self.store.repositories[1]["url"]
        service.remove_repository(self.store, "alice", 1)
        new = service.register_repository(self.store, "bob", {"name": "again", "url": url})
        self.assertEqual(new["url"], url)
        self.assertNotEqual(new["id"], 1)
        self.assertIn(new["id"], self.store.analyses)

    def test_removal_leaves_other_repositories_unchanged(self):
        others = {i: (dict(self.store.repositories[i]), dict(self.store.analyses[i])) for i in (2, 3, 4)}
        service.remove_repository(self.store, "alice", 1)
        for i, (repo, analysis) in others.items():
            self.assertEqual(self.store.repositories[i], repo)
            self.assertEqual(self.store.analyses[i], analysis)


if __name__ == "__main__":
    unittest.main()
