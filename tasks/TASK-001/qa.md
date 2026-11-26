# QA: TASK-001

<!-- Owner: QA. Check against requirements.md, not against implementation.md. -->

## Attempt

### Attempt 1

## Checks from the acceptance criteria

| Criterion | My test (in `tests/test_qa_task001.py`) | Result | Evidence |
|---|---|---|---|
| AC1 | `test_ac1_register_with_description`, `test_ac1_register_without_description_and_ids_increase` | PASS | 201, new id 5 then 6, `owner` = caller, trimmed name/URL/description returned; missing or `null` description gives `""` |
| AC2 | `test_ac2_analysis_available_without_scan` | PASS | `GET /repositories/5/analysis` right after registering returns 200 with `repository_id` 5, no scan called |
| AC3 | `test_ac3_visible_to_owner_only` | PASS | Owner's list contains it; other user's list doesn't; other users get 403 on GET, analysis and scan |
| AC4 | `test_ac4_invalid_bodies_are_refused`, `test_ac4_body_not_a_json_object`, `test_ac4_limits_are_inclusive_after_trimming` | PASS | 19 bad inputs (missing/empty/space-only name, wrong types, 101-char name, ftp/no scheme/no host/`http://[`/inner space URL, 501-char description, no body, JSON array/string, non-JSON) all 400 with an `error` message; store ids, analyses and `next_id` unchanged; 100/500 chars after trimming accepted |
| AC5 | `test_ac5_duplicate_url_same_user`, `test_ac5_duplicate_url_other_user_and_seed` | PASS | Same URL (also with spaces around it) by same user, by another user, and a seed repo's URL: 409 "This URL is already registered"; message names no owner; nothing created |
| AC6 | `test_ac6_missing_empty_or_unknown_user`, `test_ac6_unknown_user_refused_like_existing_endpoints`, `test_ac6_user_check_comes_before_validation` | PASS | Missing, empty and unknown `X-User` give 401, same status as `GET /repositories` for an unknown user; user is checked before the body; nothing created |

Command and output:

```
> python -m unittest tests.test_qa_task001 -v
...
Ran 14 tests in 1.043s
OK

> python -m unittest
Ran 44 tests in 2.042s
OK
```

## Other checks

- Wrong input: `http://[` (ValueError in `urlsplit`) gives 400, not 500. Non-JSON body gives 400.
- Worked before the change: GET endpoints without `X-User` still default to `alice` (`test_regression_get_endpoints_keep_alice_default`). Seed repositories 1–4 still return 200/403/404 as before, and scan still works (`test_regression_seed_repositories_unchanged`).
- Not changed by QA: application code. Notes for the Product Owner, not failures: URL match is exact text (`/a` vs `/a/` differ), no URL length limit, data is lost on restart. All were accepted as limits in requirements/architecture.

## Verdict

PASSED

## Failure type

None.
