# Requirements: TASK-001

<!-- Owner: PRODUCT_BA. Decisions and acceptance: PRODUCT_OWNER. Keep it to one page. -->

## The request in one sentence

A signed-in user can register a new repository (name, URL, optional description). It becomes theirs, and its analysis is available immediately.

## Acceptance criteria

- **AC1:** Given a known user, when they register a repository with a valid name and URL (with or without a description), then it is created with a new id, its owner is that user, and the response shows the name, URL, description and owner.
- **AC2:** Given a repository was just registered, when its owner asks for its analysis straight away (no scan requested first), then an analysis is returned.
- **AC3:** Given a newly registered repository, when its owner lists their repositories, then it appears in the list. Other users don't see it in their list and can't open it or its analysis, the same as existing repositories.
- **AC4:** Given a registration where the name is missing or empty, the URL is missing or empty, the URL doesn't start with `http://` or `https://` followed by a host, the name is longer than 100 characters, or the description is longer than 500 characters, then it is refused with a clear validation error and nothing is created.
- **AC5:** Given any user has already registered a URL, when anyone (including the same user) tries to register the same URL again, then it is refused with a clear "already registered" error and nothing is created.
- **AC6:** Given an unknown or missing user, when they try to register a repository, then it is refused the same way the app refuses unknown users today, and nothing is created.

## Assumptions

- "Same URL" means an exact text match after trimming spaces at the start and end.
- Leading and trailing spaces in the name and description are trimmed.
- The four demo repositories keep working unchanged.

## Open questions

- None left. All answered by the Product Owner below.

## Decisions

- **Product Owner:** A URL can be registered only once across all users. Why: one repository should have one owner and one analysis.
- **Product Owner:** A valid URL is any `http://` or `https://` web address with a host. Any host is allowed.
- **Product Owner:** The name is at most 100 characters and the description at most 500. Longer input is refused.

## Out of scope

- Editing or deleting registered repositories.
- Checking that the URL actually exists or can be reached.
- Sharing a repository with other users.

## Product Owner decision

<!-- Filled in at acceptance: ACCEPTED, CHANGES_REQUESTED or REJECTED, and a one-line reason. -->

**ACCEPTED** (Product Owner): people can register a repository with name, URL and optional description, it belongs to them and has an analysis straight away, exactly as Business asked; QA passed AC1-AC6. Refusing registration without a user (401) is accepted, because a repository must have an owner.
