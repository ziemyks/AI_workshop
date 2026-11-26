"""Business logic for the repository registry.

Every function takes the store and the current user's username. The HTTP layer
in server.py only turns requests into calls to these functions, so new
features usually start here.
"""

from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import analyzer


class ServiceError(Exception):
    """Base class for errors the API returns to the caller."""

    status = 400


class Invalid(ServiceError):
    status = 400


class Unauthorized(ServiceError):
    status = 401


class Forbidden(ServiceError):
    status = 403


class NotFound(ServiceError):
    status = 404


class Conflict(ServiceError):
    status = 409


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_user(store, username):
    user = store.users.get(username)
    if user is None:
        raise Unauthorized(f"Unknown user: {username}")
    return user


def _summary(repo):
    return {"id": repo["id"], "name": repo["name"], "url": repo["url"], "owner": repo["owner"]}


def _get_owned(store, username, repository_id):
    require_user(store, username)
    repo = store.repositories.get(repository_id)
    if repo is None:
        raise NotFound(f"Repository {repository_id} not found")
    if repo["owner"] != username:
        raise Forbidden("You don't have access to this repository")
    return repo


def list_repositories(store, username):
    """The repositories the user owns, oldest first."""
    require_user(store, username)
    return [
        _summary(repo)
        for repo in sorted(store.repositories.values(), key=lambda r: r["id"])
        if repo["owner"] == username
    ]


def get_repository(store, username, repository_id):
    return dict(_get_owned(store, username, repository_id))


def get_analysis(store, username, repository_id):
    _get_owned(store, username, repository_id)
    return dict(store.analyses[repository_id])


def scan_repository(store, username, repository_id):
    """Run the (pretend) analysis again now and return the new result."""
    repo = _get_owned(store, username, repository_id)
    scanned_at = now_utc()
    repo["last_scanned_at"] = scanned_at
    store.analyses[repository_id] = analyzer.analyze(repo, scanned_at)
    return dict(store.analyses[repository_id])


def _text_field(body, field, max_length=None, required=True):
    value = body.get(field)
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise Invalid(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise Invalid(f"{field} is required")
    if max_length is not None and len(value) > max_length:
        raise Invalid(f"{field} must be at most {max_length} characters")
    return value


def _valid_url(url):
    if any(char.isspace() for char in url):
        return False
    try:
        parts = urlsplit(url)
        return parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:
        return False


def register_repository(store, username, body):
    """Register a new repository for the caller and analyse it straight away."""
    if not username:
        raise Unauthorized("The X-User header is required")
    require_user(store, username)
    if not isinstance(body, dict):
        raise Invalid("Send a JSON object with name and url")
    name = _text_field(body, "name", max_length=100)
    url = _text_field(body, "url")
    if not _valid_url(url):
        raise Invalid("url must be an http:// or https:// address with a host")
    description = _text_field(body, "description", max_length=500, required=False)
    if any(repo["url"] == url for repo in store.repositories.values()):
        raise Conflict("This URL is already registered")

    repository_id = store.next_id
    store.next_id += 1
    registered_at = now_utc()
    repo = {
        "id": repository_id,
        "name": name,
        "url": url,
        "description": description,
        "owner": username,
        "registered_at": registered_at,
        "last_scanned_at": registered_at,
    }
    store.repositories[repository_id] = repo
    store.analyses[repository_id] = analyzer.analyze(repo, registered_at)
    return dict(repo)
