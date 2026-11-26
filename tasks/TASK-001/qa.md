# QA: TASK-001

<!-- Owner: QA. Check against requirements.md, not against implementation.md. -->

## Attempt

### Attempt 1

All checks go through the real HTTP API (`POST /repositories` and the existing GET/scan endpoints), in `tests/test_qa_task001.py`, written from `requirements.md` and `architecture.md`. A refused request is also checked for "nothing created": `next_id`, the repository ids and the analysis ids are the same before and after.

## Checks from the acceptance criteria

| Criterion | My test (in `tests/test_qa_task001.py`) | Result | Evidence |
|---|---|---|---|
| AC1 | `test_ac1_register_with_description`, `test_ac1_register_without_description`, `test_ac1_each_registration_gets_a_new_id`, `test_ac1_limits_are_inclusive` | PASS | 201 with exactly `id, name, url, description, owner, registered_at, last_scanned_at`; new ids 5, 6; owner = caller; name, URL and description trimmed; missing or `null` description stored as `""`; 100-char name and 500-char description accepted |
| AC2 | `test_ac2_analysis_without_scan` | PASS | `GET /repositories/{id}/analysis` returns 200 straight after registering, no scan, `repository_id` matches |
| AC3 | `test_ac3_owner_lists_it_others_cannot_see_or_open` | PASS | Owner bob sees it in his list; alice and chen don't; repository, analysis and scan give 403 for them; GET without `X-User` (alice) also 403 |
| AC4 | `test_ac4_invalid_name`, `test_ac4_invalid_url`, `test_ac4_invalid_description`, `test_ac4_bad_bodies`, `test_ac4_error_names_the_field` | PASS | 400 with an error naming the field, nothing created, for: missing, empty, blank, non-string and 101-char names; missing, empty, no scheme, `ftp://`, `file://`, `javascript:`, no host, inner space or tab, `http://[` (no 500) URLs; 501-char and non-string descriptions; no body, JSON array, JSON string, invalid JSON |
| AC5 | `test_ac5_duplicate_of_seed_url_any_owner`, `test_ac5_duplicate_of_new_url_same_and_other_user`, `test_ac5_only_exact_text_counts_as_same` | PASS | 409 "This URL is already registered" for a seed URL (its owner and another user) and for a newly registered URL (same user, other user, with surrounding spaces); the message doesn't name the owner; nothing created. A trailing `/` counts as a different URL, as the PO assumption says |
| AC6 | `test_ac6_missing_empty_or_unknown_user`, `test_ac6_user_checked_before_body` | PASS | 401 for no `X-User`, an empty `X-User` and an unknown user, same status as `GET /repositories` gives an unknown user today; the user is checked before the body; nothing created |

## Other checks

- **Wrong input:** 16 bad URLs, 6 bad names, 4 bad descriptions and 4 malformed bodies are all refused with 400, and none of them creates anything (AC4 tests above).
- **Worked before this change:** `test_regression_seed_data_unchanged_after_registering`: the four seed repositories are unchanged after a registration; `GET /repositories` without `X-User` still defaults to alice; bob can still open repository 3; chen can still scan repository 4; an unknown id is still 404. `test_regression_other_methods_on_collection`: `DELETE /repositories` is still 405.
- **Whole suite:** `python -m unittest` → `Ran 48 tests in 1.961s` / `OK` (QA's 18 plus the existing 30).
- **QA tests on their own:** `python -m unittest tests.test_qa_task001 -v` → `Ran 18 tests in 0.810s` / `OK`.

Notes for the Product Owner (not failures, already listed in architecture.md):

- Without an `X-User` header, registering is refused (401), while GET endpoints still default to alice. This is how AC6 was read; confirm it at acceptance.
- Data is in memory only, so registered repositories are lost on restart. No URL length limit was decided.

## Verdict

PASSED

## Failure type

Not applicable.
