# QA: TASK-002

<!-- Owner: QA. Check against requirements.md, not against implementation.md. -->

## Attempt

### Attempt 1

All checks go through the real HTTP API in `tests/test_qa_task002.py`, written from `requirements.md` and `architecture.md`. Every refused removal is also checked for "nothing changed": `next_id`, all repositories and all analyses are identical before and after.

## Checks from the acceptance criteria

| Criterion | My test (in `tests/test_qa_task002.py`) | Result | Evidence |
|---|---|---|---|
| AC1 | `test_ac1_owner_removes_seed_repository`, `test_ac1_owner_removes_newly_registered_repository` | PASS | `DELETE /repositories/2` as alice → 204, empty body; alice's list is now `[1]`. A repository bob just registered → 204; bob's list is back to `[3]` |
| AC2 | `test_ac2_removed_repository_answers_not_found` | PASS | After removing 1: GET, analysis, scan and a second DELETE all give 404 with exactly the same message as id 999 that never existed; the analysis is gone from the store |
| AC3 | `test_ac3_other_users_repository_is_forbidden_and_unchanged`, `test_ac3_cannot_remove_another_users_new_repository` | PASS | alice removing bob's 3 → 403 with the same message as opening it today, owner not named, nothing changed; bob still gets 200 on it and its analysis. alice and bob can't remove chen's new repository |
| AC4 | `test_ac4_missing_empty_or_unknown_user`, `test_ac4_same_refusal_as_registering` | PASS | No `X-User`, empty `X-User` and `mallory` → 401 for an own, someone else's and a missing id (9 cases), nothing changed. Missing header gives the same message as registering: "The X-User header is required" |
| AC5 | `test_ac5_url_can_be_registered_again_by_anyone`, `test_ac5_former_owner_can_register_it_again` | PASS | After removing 1, chen registers its URL → 201, new id 5 (1 not reused), owner chen, analysis 200 straight away; id 1 stays 404. The former owner can also re-register a removed URL, with the next new id |
| AC6 | `test_ac6_other_repositories_and_analyses_unchanged` | PASS | After removing 2, repositories 1, 3 and 4 and their analyses are identical to before; bob and chen's lists unchanged |

## Other checks

- **Wrong input:** `DELETE /repositories/abc` → 404 (no such endpoint); a DELETE with a body that isn't JSON → 400 and nothing removed (`test_wrong_input_non_numeric_or_bad_body`).
- **Worked before this change:** `DELETE /repositories` (the collection) still 405; `GET /repositories` without `X-User` still defaults to alice; chen can still scan 4 (`test_regression_collection_delete_and_get_default`). The TASK-001 QA tests still pass.
- **QA tests on their own:** `python -m unittest tests.test_qa_task002 -v` → `Ran 12 tests in 0.703s` / `OK`.
- **Whole suite:** `python -m unittest` → `Ran 73 tests in 2.479s` / `OK` (61 before + QA's 12).

Notes for the Product Owner (not failures, already in the requirements and design): removal is permanent with no undo; data is in memory, so a restart brings back the seed repositories.

## Verdict

PASSED

## Failure type

Not applicable.
