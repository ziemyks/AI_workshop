# Repository registry API

The sample app keeps a list of code repositories that users have registered, and a pretend analysis of each one. It's a small JSON API built only on the Python standard library, so there's nothing to install.

- **Code:** `app/service.py` has the business logic, `app/server.py` the HTTP endpoints, `app/store.py` the in-memory data, and `app/analyzer.py` the pretend analysis.
- **Data:** everything is in memory. Restarting the app resets it to the seed data in `app/store.py`.
- **Who is calling:** send the header `X-User: <username>`. Without it, you are `alice`. Known users are `alice`, `bob` and `chen`.
- **Access:** a user can only see and use repositories they own.

## Endpoints today

| Method and path | What it does | Errors |
|---|---|---|
| `GET /health` | Returns `{"status": "ok"}` | |
| `GET /repositories` | Lists your repositories: `id`, `name`, `url`, `owner` | 401 unknown user |
| `POST /repositories` | Registers a repository for the caller (`X-User` required, no `alice` default). Body: `name` (max 100), `url` (`http://` or `https://` with a host), optional `description` (max 500). Returns 201 with the full repository; its analysis exists at once. | 400 invalid input, 401 missing or unknown user, 409 URL already registered |
| `GET /repositories/{id}` | One repository, with `description`, `registered_at` and `last_scanned_at` | 401, 403 not yours, 404 |
| `DELETE /repositories/{id}` | Permanently removes one of your repositories and its analysis (`X-User` required, no `alice` default). Returns 204 with no body. Its URL can be registered again, as a new repository with a new id. | 401 missing or unknown user, 403 not yours, 404 |
| `GET /repositories/{id}/analysis` | The latest analysis: languages, files, lines of code, open findings, health score, contributors, summary | 401, 403, 404 |
| `POST /repositories/{id}/scan` | Runs the analysis again now and returns it | 401, 403, 404 |

Errors come back as `{"error": "<message>"}`.

## Seed data

| id | name | owner |
|---|---|---|
| 1 | payments-api | alice |
| 2 | web-portal | alice |
| 3 | data-pipeline | bob |
| 4 | mobile-app | chen |

## Try it

```
python -m app.server
```

Then, in another terminal:

```
curl http://localhost:8000/repositories
curl -H "X-User: bob" http://localhost:8000/repositories
curl -X POST http://localhost:8000/repositories/1/scan
```

In Windows PowerShell, use `curl.exe` instead of `curl`.

## Adding an endpoint

1. Put the logic in `app/service.py`. Raise `Invalid`, `Forbidden` or `NotFound` for errors.
2. Add a small handler in `app/server.py` with the `@route("METHOD", r"/path")` decorator. The request's JSON body is in `req.body`, and the query string in `req.query`.
3. Add tests in `tests/`. Run them with `python -m unittest`.
