# Architecture: TASK-001

<!-- Owner: ARCHITECT. Security notes: SECURITY. A few bullets, not a design document. -->

## Approach

- New endpoint `POST /repositories` with a thin handler in `app/server.py` and the logic in a new `service.register_repository(store, username, body)`.
- Order of checks: caller (401), then body and fields (400), then duplicate URL (409). Nothing is written to the store until every check has passed (AC4, AC5, AC6).
- On success, take `store.next_id`, add 1 to it, save the repository with `owner` = caller, and create its analysis at once with `analyzer.analyze(repo, registered_at)` (AC1, AC2).
- Reuse `require_user`, the error classes and the existing `_get_owned` / `list_repositories` code, so access to new repositories works exactly like the seed ones (AC3). Add one error class, `Conflict` (409), for "already registered".
- AC6 is taken literally: on this endpoint, a request **without** an `X-User` header is refused with 401 instead of defaulting to `alice`. All other endpoints keep the `alice` default.

## Parts that change

- `app/service.py`: new class `Conflict(ServiceError)` with `status = 409`; new function `register_repository`.
- `app/server.py`: `Request` also keeps the raw `X-User` header (`None` when absent), for example `req.user_header`; new handler `@route("POST", "/repositories")` that passes `req.user_header` (not `req.user`) to the service and returns `201`.
- `tests/test_service.py`, `tests/test_api.py`: tests for every rule below.
- `docs/api.md`: add the new row to "Endpoints today".

## Interface

- `POST /repositories`, caller from `X-User` (required here, no `alice` default)
  - Body: a JSON object. Unknown fields are ignored.
  - `name` (string, required): trimmed; not empty; at most 100 characters after trimming.
  - `url` (string, required): trimmed; not empty; no spaces inside; `urllib.parse.urlsplit(url)` gives scheme `http` or `https` and a non-empty `hostname`. A `ValueError` from `urlsplit` (for example `http://[`) is also a 400, never a 500.
  - `description` (string or `null`, optional): trimmed; at most 500 characters after trimming; stored as `""` when absent or `null`.
  - **201:** the full repository, the same shape as `GET /repositories/{id}`: `{"id", "name", "url", "description", "owner", "registered_at", "last_scanned_at"}`. `registered_at` and `last_scanned_at` are the same `now_utc()` value.
  - **400** `Invalid`: no body, body is not a JSON object, a field has the wrong type, or any rule above is broken. The message names the field, for example `{"error": "name must be at most 100 characters"}`.
  - **401** `Unauthorized`: no `X-User` header, an empty one, or an unknown user (AC6).
  - **409** `Conflict`: the trimmed URL exactly matches the `url` of any repository already in the store, seed repositories included, whoever owns it: `{"error": "This URL is already registered"}` (AC5). The message must not say who owns it.
- After a 201, the existing endpoints work for the new id with no changes: `GET /repositories` lists it for the owner only, `GET /repositories/{id}` and `GET /repositories/{id}/analysis` return 200 for the owner and 403 for anyone else (AC2, AC3).

| AC | Covered by |
|---|---|
| AC1 | 201 response, new id from `store.next_id`, `owner` = caller |
| AC2 | Analysis created in the same call, before the 201 |
| AC3 | Existing `_get_owned` and `list_repositories`, unchanged |
| AC4 | 400 rules for `name`, `url`, `description`; checks run before any write |
| AC5 | 409 on an exact match of the trimmed URL, across all users |
| AC6 | 401 for a missing, empty or unknown `X-User`; checked first |

## Risks and limits

- Data is in memory only. Registered repositories are lost when the app restarts.
- The duplicate check and the id counter are safe only because `HTTPServer` handles one request at a time. A threaded server would need a lock.
- The URL is only checked for its format and is never fetched (out of scope). The analysis is the existing pretend one.
- URL matching is exact text: `https://x.org/a` and `https://x.org/a/` count as different URLs, as the Product Owner's assumption says.
- No length limit on the URL was decided. It is bounded only by the request size. Say so if the Product Owner wants one.
- Decision to confirm at acceptance: without an `X-User` header, registration is refused (AC6), while GET endpoints still default to `alice`.

## Security notes

<!-- Filled in by SECURITY when a risk is reported: what was found, where, and what must change. -->
