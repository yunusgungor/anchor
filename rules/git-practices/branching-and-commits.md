# Branching & Commit Rules

## Core Principle

> *Every commit is a logical unit of change. Every branch tells a clear story of feature, fix, or experiment.*

These rules govern how we structure branches and write commits in this project. Consistency in version control is a force multiplier — it makes code review faster, debugging easier, and release notes automated.

---

## 1. Branch Naming Convention

### Rules

- [ ] Branch names MUST follow the pattern: `<type>/<short-description>`
- [ ] Use `/` as separator (no other separators like `-` or `_` for type/scope separation)
- [ ] Description MUST be kebab-case (lowercase, hyphen-separated words)
- [ ] Branch names SHOULD be kept under 50 characters total

### Branch Types

| Type       | When to use                              | Example                               |
|------------|------------------------------------------|---------------------------------------|
| `feat/`    | New feature or enhancement               | `feat/user-oauth-login`               |
| `fix/`     | Bug fix                                  | `fix/null-pointer-in-validator`       |
| `refactor/`| Code restructuring without behavior change | `refactor/extract-payment-service`   |
| `chore/`   | Tooling, config, dependencies, CI        | `chore/upgrade-pydantic-v2`           |
| `docs/`    | Documentation-only changes               | `docs/api-contract-typo`              |
| `test/`    | Adding or improving tests                | `test/coverage-edge-cases`            |
| `perf/`    | Performance optimization                 | `perf/cache-embedding-lookup`         |
| `style/`   | Formatting, whitespace, linting fixes    | `style/ruff-format-pass`              |
| `revert/`  | Reverting a previous commit              | `revert/rollback-auth-changes`        |

### Examples

```
feat/rate-limiting-middleware
fix/user-id-race-condition
refactor/extract-domain-service
chore/docker-compose-dev
docs/adr-012-caching-strategy
```

---

## 2. Commit Message Convention

All commits MUST follow [Conventional Commits](https://www.conventionalcommits.org/) v1.0.

### Format

```
<type>(<optional-scope>): <short-summary>

<optional-body>

<optional-footer>
```

### Rules

- [ ] The `<type>` MUST be one of: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `perf`, `style`, `revert`
- [ ] `<short-summary>` MUST be imperative mood, present tense, capitalized, no trailing period
- [ ] `<short-summary>` MUST be ≤ 72 characters
- [ ] The `(<scope>)` is optional but RECOMMENDED when the change crosses a clear module boundary
- [ ] The body is OPTIONAL but REQUIRED when the short summary alone cannot fully explain the change
- [ ] The body MUST wrap at 72 characters per line
- [ ] A blank line MUST separate the summary from the body and the body from the footer
- [ ] Use `BREAKING CHANGE:` in the footer (or `!` after type/scope) for breaking changes

### Examples

```
feat(auth): implement OAuth2 PKCE flow

Adds the Proof Key for Code Exchange extension to the
authorization flow for mobile clients.

Closes #142
```

```
fix(parser): handle null frontmatter in empty files

The rule parser crashed when encountering markdown files
with an empty frontmatter block. Now returns default
configuration instead of raising.

Fixes #89
```

```
refactor(store)!: migrate from JSON to SQLite storage

BREAKING CHANGE: All persistent data must be migrated
using the `migrate-v2` script before upgrading.
```

```
docs: fix typo in rate-limiting config example
```

---

## 3. Commit Granularity

### Rules

- [ ] Each commit MUST represent a **single logical change** — one concern, one purpose
- [ ] Do NOT mix unrelated changes in a single commit (e.g., a bug fix + a refactor + a formatting change)
- [ ] If you're tempted to write "and" in the commit summary, split the commit
- [ ] Tests SHOULD be committed in the same commit as the code they test

### Good vs. Bad

| Good (one concern)                                    | Bad (mixed concerns)                                                    |
|-------------------------------------------------------|-------------------------------------------------------------------------|
| `feat: add user rate-limiting middleware`             | `fix: update config and refactor parser and add tests`                  |
| `fix: handle empty request body in validation`        | `chore: bump deps + fix lint + update readme`                           |
| `refactor: extract email service from user model`     | `docs,test: update api docs and add unit tests`                         |

---

## 4. Pull Request & Merge Rules

### Rules

- [ ] Squash-merge is the DEFAULT strategy for feature/fix branches into `main`
- [ ] Rebase-merge is ACCEPTABLE for commits that are already well-structured atomic commits
- [ ] Pure merge commits are DISCOURAGED except for long-running integration branches
- [ ] PR title MUST follow the same Conventional Commits format as commit messages
- [ ] PR description MUST include:
  - **What** — summary of the change
  - **Why** — motivation or issue reference
  - **How** — high-level approach (optional for small changes)
  - **Testing** — what tests were added or how it was verified
- [ ] PR SHOULD target `main` unless it's a release branch or hotfix

### PR Template Structure

```markdown
## What
<brief description of the change>

## Why
<motivation, issue link, or context>

## How
<approach taken, design decisions (optional)>

## Testing
- [ ] Unit tests added/passed
- [ ] Integration tests added/passed
- [ ] Manual testing performed
```

---

## 5. Main Branch Protection

### Rules

- [ ] `main` is PROTECTED — no direct commits, no force push
- [ ] All changes MUST go through a pull request
- [ ] At least one approving review is REQUIRED before merge
- [ ] All CI checks MUST pass before merge
- [ ] The branch MUST be up-to-date with `main` (rebase or merge) before merge
- [ ] Signed commits are REQUIRED on `main`

### Branch Lifecycle

```
         feature branch
         ┌──────────────┐
         │  feat/foo    │──── squash-merge ──┐
         └──────────────┘                    │
         ┌──────────────┐                    ▼
         │  fix/bar     │──── squash-merge ──► main (protected)
         └──────────────┘                    │
         ┌──────────────┐                    │
         │  docs/baz    │──── rebase-merge ──┘
         └──────────────┘
```

---

## 6. Commit Signing

### Rules

- [ ] All commits on `main` MUST be signed with a GPG or SSH key
- [ ] Commits on feature branches SHOULD be signed
- [ ] The Git config `user.signingkey` MUST be set to a valid key
- [ ] `git config commit.gpgsign true` is REQUIRED for automated tooling

### Quick Setup

```bash
# List existing GPG keys
gpg --list-secret-keys --keyid-format=long

# Configure Git to sign
git config --global user.signingkey <KEY-ID>
git config --global commit.gpgsign true

# Verify signing
git log --show-signature -1
```

---

## 7. Git Hygiene

### Rules

- [ ] Do NOT commit generated files, build artifacts, or binary blobs
- [ ] Keep `.gitignore` up to date; use global gitignore for OS/IDE files
- [ ] Do NOT commit `.env`, secrets, API keys, or credentials (use environment variables or vaults)
- [ ] Use `git rebase -i` locally to clean up commit history before pushing
- [ ] Do NOT rewrite history on shared branches (`main`, release branches, long-lived feature branches with multiple contributors)
- [ ] Delete local and remote branches after merge
- [ ] `git pull --rebase` is PREFERRED over `git pull` (avoids merge commits)

### Pre-Push Checklist

- [ ] Are there any debug statements, print/logging, or WIP code?
- [ ] Are `.env`, secrets, or credentials included?
- [ ] Are generated files or build artifacts included?
- [ ] Are commit messages well-formed and meaningful?
- [ ] Have I squashed fixup/squash commits?

---

## 8. Release & Tagging

### Rules

- [ ] Tags MUST follow Semantic Versioning: `v<major>.<minor>.<patch>`
- [ ] Tags MUST be annotated (`git tag -a`) — not lightweight
- [ ] Tags SHOULD be signed
- [ ] Release branches use the pattern `release/v<major>.<minor>`
- [ ] Version bumps are done in a dedicated commit/chore PR

### Tag Examples

```
v1.0.0          # Initial public release
v1.2.3          # Patch release
v2.0.0-rc.1     # Release candidate
v2.0.0          # Major release
```

---

## References

- [Conventional Commits v1.0](https://www.conventionalcommits.org/)
- [Semantic Versioning 2.0](https://semver.org/)
- [Git Branching — Atlassian](https://www.atlassian.com/git/tutorials/using-branches)
