# Pipeline Standards

> **Purpose:** Define a consistent, reliable pipeline structure across all projects — from commit to production — ensuring fast feedback, security, and deployment confidence.

---

## 1. Pipeline as Code

- Every pipeline definition **must live in version control** alongside the code it builds.
- Use the project's agreed CI platform (GitHub Actions, GitLab CI, Jenkins, Buildkite, etc.).
- Pipeline YAML/DSL changes go through the same review process as application code.

### Required files

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` or equivalent | Main CI pipeline |
| `.github/workflows/deploy.yml` or equivalent | Deployment pipeline |
| `Dockerfile` or equivalent | Build artifact definition |
| `docker-compose.yml` / `compose.yaml` | Local and CI service topology |

---

## 2. Pipeline Stages

Every pipeline must follow this **standard stage progression**. Stages run sequentially within their phase; parallelization is encouraged inside a phase.

```
┌─────────────┐
│   Lint      │ ◄── Phase 1: Static Analysis (fastest)
├─────────────┤
│   Build     │ ◄── Phase 2: Compilation / Assembly
├─────────────┤
│   Unit      │ ◄── Phase 3: Fast tests
├─────────────┤
│  Integrate  │ ◄── Phase 4: Integration & contract tests
├─────────────┤
│   Secure    │ ◄── Phase 5: Security scanning
├─────────────┤
│   Package   │ ◄── Phase 6: Artifact creation
├─────────────┤
│   Deploy    │ ◄── Phase 7: Environment release
└─────────────┘
```

### Stage details

#### Phase 1 — Lint & Static Analysis

- **Run first** — fails fast on trivial issues.
- Tools: linters (ESLint, ruff, pylint), formatters (Prettier, black), type checkers (mypy, TypeScript).
- Gate: **All lint checks must pass** before subsequent stages run.

#### Phase 2 — Build

- Compile, bundle, or assemble the application.
- Validate that the project builds cleanly with zero warnings (where the toolchain supports warnings-as-errors).
- Cache dependencies between runs (e.g., `pip cache`, `npm cache`, Gradle cache).

#### Phase 3 — Unit Tests

- Execute the unit test suite (see [automated-testing.md](./automated-testing.md)).
- Must complete within **5 minutes** for most projects.
- No network or external service dependencies.

#### Phase 4 — Integration & Contract Tests

- Execute integration tests against real or containerized dependencies.
- Run contract tests (Pact, Spring Cloud Contract) for service boundaries.
- Use Docker Compose or Testcontainers to provision ephemeral infrastructure.

#### Phase 5 — Security Scanning

- **SAST** (Static Application Security Testing): Bandit, Semgrep, CodeQL, or SonarQube.
- **Dependency scanning**: Dependabot, Snyk, or `pip-audit` / `npm audit`.
- **Secrets detection**: Detect leaked credentials in the repository (truffleHog, Gitleaks).
- Gate: **Critical and High findings must be addressed** before deployment to production.

#### Phase 6 — Package & Artifact

- Build a deployable artifact (Docker image, compiled binary, tarball).
- Tag the artifact with a **unique, immutable identifier** (commit SHA + build number).
- Push artifact to a registry (Docker registry, Artifactory, S3).
- Gate: **Artifact must be scanned and signed** before promotion.

#### Phase 7 — Deploy

- Deploy to **ephemeral review environment** (on PR) or **staging** (on merge to main).
- Run smoke tests after deployment to verify the artifact is operational.
- Production deployment requires **manual approval gate** (unless the team explicitly opts for fully automated deploy with canary analysis).

---

## 3. Branch-Based Pipeline Behavior

| Branch | Trigger | Stages | Deploy To | Approval |
|--------|---------|--------|-----------|----------|
| Feature / PR | Push to branch | Lint → Build → Unit → Integrate → Secure | Review env (optional) | None |
| `main` / `master` | Merge commit | Lint → Build → Unit → Integrate → Secure → Package | Staging | None (automated) |
| `release/*` | Tag push | Full pipeline + Package | Staging → Prod (canary) | Manual prod gate |
| `hotfix/*` | Push | Full pipeline (expedited) | Production | Emergency approval |

---

## 4. Environment Parity

- **Development**, **CI**, **staging**, and **production** environments should be as similar as possible.
- Use the same **operating system**, **runtime version**, and **service versions** across environments.
- Environment-specific configuration is injected via **environment variables** or **secret stores**, never baked into artifacts.
- Database migrations run as a **separate step** before the new application version is deployed.

### Parity checklist

- [ ] Same language runtime version (pinned via `.nvmrc`, `.python-version`, `go.mod`)
- [ ] Same base Docker image for build and runtime
- [ ] Same OS package versions (pinned in `Dockerfile` or `apt.txt`)
- [ ] Same dependency lock files (`package-lock.json`, `poetry.lock`, `go.sum`)
- [ ] CI runs the same test suites that developers run locally
- [ ] Staging mirrors production data volume (sanitized subset)
- [ ] Feature flags control new behavior — not environment branches

---

## 5. Artifact Management

| Property | Standard |
|----------|----------|
| Format | Docker image (preferred) or compressed archive |
| Tagging | `{branch}-{commit_sha[:8]}-{build_number}` |
| Immutability | Once pushed, artifact tags are never overwritten |
| Retention | 30 days for non-production, 90 days for production |
| Signing | All production artifacts are signed (cosign / GPG) |
| SBOM | Software Bill of Materials generated and attached to each release |

---

## 6. Pipeline Gates

Gates are **hard checks** that block progression to the next stage.

| Gate | Stage | Enforcement |
|------|-------|-------------|
| Lint passing | Lint → Build | Pipeline fails if any lint error exists |
| Build succeeding | Build → Unit | Pipeline fails if build fails |
| Unit tests green | Unit → Integrate | Pipeline fails if any unit test fails |
| Integration tests green | Integrate → Secure | Pipeline fails if any integration test fails |
| No critical/high vulnerabilities | Secure → Package | Pipeline fails; exception process required |
| Artifact signed | Package → Deploy | Deployment fails if artifact is unsigned |
| Manual approval | Staging → Production | Deploy blocks until authorized user approves |
| Smoke tests passing | Post-deploy | Rollback triggered if smoke tests fail |

---

## 7. Pipeline Performance

### Timing targets

| Stage | Target Duration | Alert Threshold |
|-------|----------------|----------------|
| Lint & Static Analysis | ≤ 1 min | ≥ 3 min |
| Build | ≤ 3 min | ≥ 8 min |
| Unit Tests | ≤ 3 min | ≥ 5 min |
| Integration Tests | ≤ 5 min | ≥ 10 min |
| Security Scan | ≤ 4 min | ≥ 8 min |
| **Total CI (Phases 1–5)** | **≤ 15 min** | **≥ 25 min** |

### Optimization techniques

- [ ] **Dependency caching** — store downloaded packages between runs
- [ ] **Parallel stage execution** — run independent stages concurrently where possible (e.g., lint + type-check)
- [ ] **Test splitting** — distribute test files across multiple CI runners
- [ ] **Incremental builds** — only rebuild changed modules
- [ ] **Selective execution** — skip stages that are irrelevant to the change (e.g., docs-only PR skips integration tests)

---

## 8. Secrets and Credentials

- All secrets (API keys, database passwords, tokens) are stored in the CI platform's **secret store** — never in repository files.
- Secrets are scoped to the **minimum required environment** (no production secrets in PR pipelines).
- Rotate secrets on a **regular schedule** (quarterly minimum) and immediately after a compromise.
- Audit secret access — know which pipelines and users can read each secret.

---

## 9. Pipeline Observability

- Every pipeline run produces a **structured log** aggregated to a central location.
- Pipeline **duration, failure rate, and stage-level metrics** are tracked and reviewed weekly.
- Set up **alerts** for:
  - Pipeline failure rate > 10% over a 24-hour window
  - Stage duration exceeding 2× the alert threshold
  - Build queue wait time > 5 minutes
- Post the pipeline status to a team communication channel (Slack, Discord, Teams).

---

## 10. Failure Handling

| Scenario | Response |
|----------|----------|
| Flaky test failure | Tag test as flaky, quarantine it, file a bug within 24 hours |
| Infrastructure failure (runner, registry) | Retry the pipeline automatically (max 2 retries) |
| Security vulnerability found | Block pipeline, notify security team, evaluate severity |
| Deployment failure | Automatic rollback to previous artifact; page the on-call engineer |
| Pipeline timeout | Increase timeout or split stage; investigate bottleneck |

---

## 11. Enforcement

| Rule | Tool / Method |
|------|--------------|
| Pipeline as code | Code review enforces YAML changes |
| Stage ordering | CI platform enforces dependency graph |
| Required checks on PR | Branch protection rules (GitHub / GitLab) |
| Secrets not in repo | Pre-commit hook (detect-secrets) + CI scan |
| Artifact immutability | Registry policy (no overwrite tags) |
| Deployment approval | Manual environment approval in CI platform |
| Pipeline duration alerts | Monitoring dashboard + PagerDuty webhook |

---

## References

- [GitHub Actions — Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [GitLab CI — Pipeline Architecture](https://docs.gitlab.com/ee/ci/pipelines/)
- [Trunk-Based Development](https://trunkbaseddevelopment.com/)
- [Google SRE Book — Embracing Risk](https://sre.google/sre-book/embracing-risk/)
