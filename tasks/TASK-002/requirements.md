# Requirements: TASK-002

<!-- Owner: PRODUCT_BA. Decisions and acceptance: PRODUCT_OWNER. Keep it to one page. -->

## The request in one sentence

An owner can permanently remove one of their own repositories, and after that the repository and its analysis are gone everywhere in the app.

## Acceptance criteria

- **AC1:** Given a user owns a repository, when they remove it, then the removal succeeds and the repository no longer appears in their list of repositories.
- **AC2:** Given a repository was removed, when its former owner asks for that repository, its analysis or a new scan, then each request answers "not found", the same as for an id that never existed. Removing it a second time also answers "not found".
- **AC3:** Given a repository owned by someone else, when a user tries to remove it, then it is refused the same way the app refuses access to another user's repository today (403), and the repository and its analysis are unchanged for the owner.
- **AC4:** Given a missing or unknown user, when they try to remove any repository, then it is refused the same way registering a repository refuses them (401), and nothing is removed.
- **AC5:** Given a repository was removed, when anyone (including the former owner) registers the same URL again, then it is accepted as a new repository with a new id and its own fresh analysis.
- **AC6:** Given one repository is removed, then every other repository (of the same owner and of other users) and its analysis are unchanged.

## Assumptions

- Ids of removed repositories are not reused for new repositories.
- Removal only affects the running app's data. Restarting the app brings back the seed data, as it does today.

## Open questions

- None left. All answered by the Product Owner below.

## Decisions

- **Product Owner:** Removal is permanent. There is no undo. Why: Business asked for it to be "gone everywhere".
- **Product Owner:** Once removed, its URL is free and can be registered again by anyone. Why: the repository was registered by mistake and may need to be registered correctly.
- **Product Owner:** Removing requires the caller to name themselves (`X-User`). There is no default user. Why: nobody should remove someone's data by leaving out a header.
- **Product Owner:** Trying to remove someone else's repository gets 403, the same as opening it today. Why: consistent with the rest of the app.

## Out of scope

- Removing several repositories at once.
- Undo, a recycle bin, or an audit log of removals.
- Admins or other users removing repositories they don't own.
- Editing a repository.

## Product Owner decision

<!-- Filled in at acceptance: ACCEPTED, CHANGES_REQUESTED or REJECTED, and a one-line reason. -->
