# Secure Coding Rules

## Core Principle

> *Security is not a feature — it is a property of the entire system. Every developer is responsible for it.*

These rules define mandatory secure coding practices for all code written in this project. Violations found during code review MUST be resolved before merge.

---

## 1. Input Validation

### Rules

- [ ] All external input MUST be validated against an explicit allowlist (whitelist) of expected values, types, and patterns.
- [ ] Reject unknown input — do not try to sanitize it into validity.
- [ ] Validate on **both** client and server side — never trust the client.
- [ ] Use parameterized queries or ORM-level escaping for all database interactions.
- [ ] Validate file uploads: check extension, MIME type, file size, and content signature.

### Patterns

```python
# GOOD: validate against known allowed values
ALLOWED_ROLES = {"admin", "editor", "viewer"}
if role not in ALLOWED_ROLES:
    raise ValidationError(f"Invalid role: {role}")

# BAD: try to sanitize bad input
role = role.strip().lower()  # still might be "admin; DROP TABLE users"
```

### Checklist

- [ ] Is every external input source accounted for? (HTTP params, headers, file uploads, webhooks, CLI args, env vars)
- [ ] Is the validation based on allowlist, not blocklist?
- [ ] Are boundary values (empty strings, negative numbers, max-length strings) tested?

---

## 2. Authentication & Authorization

### Rules

- [ ] Use a well-vetted authentication library — never roll your own crypto or auth.
- [ ] Store passwords using a strong adaptive hashing algorithm (bcrypt, argon2, scrypt) — NEVER plaintext, MD5, SHA-1, or unsalted SHA-2.
- [ ] All authentication-required endpoints MUST enforce authentication at the framework/entry level, not in individual handlers.
- [ ] Authorization checks MUST use the **principle of least privilege** — grant the minimum permissions needed.
- [ ] Session tokens, API keys, and JWTs MUST be revocable — implement a token blacklist or short expiry.
- [ ] JWTs MUST be validated: verify signature, expiry (`exp`), not-before (`nbf`), issuer (`iss`), and audience (`aud`).

### Example

```python
# GOOD: bcrypt with cost factor
import bcrypt
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
if bcrypt.checkpw(password.encode(), hashed):
    ...

# BAD: unsupported or weak hash
import hashlib
hashed = hashlib.sha256(password.encode()).hexdigest()  # too fast, no salt
```

---

## 3. Injection Prevention

### Rules

- [ ] NEVER concatenate user input into SQL, NoSQL, LDAP, shell commands, or HTML — always use parameterized APIs.
- [ ] SQL: use parameterized queries or an ORM that handles escaping. Never use `f-strings` or `format()` for query building.
- [ ] Shell: avoid `os.system()`, `subprocess(shell=True)`. Use `subprocess.run()` with a list argument.
- [ ] Command injection is CRITICAL severity — any occurrence blocks merge.

### Patterns

```python
# SQL Injection — GOOD
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))

# SQL Injection — BAD (block merge)
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")

# Shell Injection — GOOD
subprocess.run(["ffmpeg", "-i", input_file, output_file])

# Shell Injection — BAD (block merge)
subprocess.run(f"ffmpeg -i {input_file} {output_file}", shell=True)
```

### Injection attack surface

| Vector              | Safe approach                  |
|---------------------|--------------------------------|
| SQL / NoSQL queries | Parameterized queries, ORM     |
| Shell commands      | `subprocess.run([...])` (list) |
| HTML templates      | Auto-escaping templates (Jinja, Mako) |
| LDAP queries        | Escape/encode LDAP filter values |
| XML/XXE             | Disable DTDs, external entities |
| YAML                | Use `yaml.safe_load()` not `yaml.load()` |
| Deserialization     | Avoid `pickle`; use JSON or safe alternatives |

---

## 4. Secrets Management

### Rules

- [ ] NEVER hardcode secrets, API keys, tokens, passwords, or certificates in source code.
- [ ] All secrets MUST be read from environment variables, a secrets vault (e.g., HashiCorp Vault, AWS Secrets Manager), or a secrets file excluded from version control.
- [ ] `.env` files MUST be in `.gitignore`. They are for local development only.
- [ ] CI/CD secrets MUST use the CI platform's built-in secret store — never pass them as plaintext env vars in config files.
- [ ] If a secret is accidentally committed, rotate it immediately and rewrite git history.
- [ ] Use `.gitignore` with global patterns for common secret file names.

### Good Practices

```python
# GOOD: read from environment
import os
API_KEY = os.environ["API_KEY"]

# BAD: hardcoded in source
API_KEY = "sk-abc123def456ghijklmno"  # NEVER
```

---

## 5. Logging & Monitoring

### Rules

- [ ] NEVER log secrets, passwords, tokens, PII, or sensitive personal data.
- [ ] Log security-relevant events: authentication failures, authorization denials, input validation failures, rate-limit hits.
- [ ] Use structured logging (JSON) with consistent fields for automated analysis.
- [ ] Implement rate-limiting and consider adding a log of failed auth attempts per user/IP.

### What to Log

| Event                        | Severity | Include                          |
|------------------------------|----------|----------------------------------|
| Successful login             | INFO     | user_id, timestamp, IP           |
| Failed login                 | WARN     | username (attempted), IP, reason |
| Authorization denial         | WARN     | user_id, resource, action        |
| Input validation failure     | WARN     | field, reason, IP                |
| Rate-limit triggered         | WARN     | user_id or IP, threshold         |
| Exception / stack trace      | ERROR    | full exception, request_id       |

### What NOT to Log

```
❌ Passwords, password hashes
❌ API keys, tokens, session IDs
❌ Credit card numbers, SSNs
❌ Full database rows containing PII
❌ Private keys, certificates
```

---

## 6. Dependency Security

### Rules

- [ ] All third-party dependencies MUST be pinned to exact versions (not ranges) in `pyproject.toml` / `requirements.txt`.
- [ ] Run `pip-audit` or `safety check` in CI for known-vulnerability scanning.
- [ ] Dependencies with critical or high CVEs MUST be updated or replaced before merge.
- [ ] Review transitive dependencies — use `pipdeptree` to audit the full tree.
- [ ] Avoid dependencies with no recent maintenance history (>1 year without updates).
- [ ] Use a lockfile (`poetry.lock`, `Pipfile.lock`, or `uv.lock`) for deterministic builds.

### CI Enforcement

```yaml
# Example CI step
- name: Check dependencies for vulnerabilities
  run: pip-audit --strict --require-hashes
```

---

## 7. Error Handling

### Rules

- [ ] NEVER expose stack traces, internal paths, or debug information in production error responses.
- [ ] Always return a generic error message to the client; log the detailed error server-side.
- [ ] Fail securely — if a security check fails (e.g., unreadable config, unparseable token), deny access by default.
- [ ] Implement a global exception handler that catches unhandled exceptions and returns a sanitized response.

### Patterns

```python
# GOOD: generic user-facing error, detailed server log
try:
    process_payment(card_info)
except PaymentError as e:
    logger.error(f"Payment failed: {e}", exc_info=True)
    return {"error": "Payment processing failed. Please try again."}, 500

# BAD: leaking internals
except Exception as e:
    return {"error": repr(e)}, 500  # exposes internal details
```

---

## 8. Cross-Site Scripting (XSS) & Output Encoding

### Rules

- [ ] Any user-controlled data rendered in HTML, JSON, or JavaScript MUST be properly escaped/encoded.
- [ ] Use template engines with auto-escaping enabled by default (Jinja2, Mako).
- [ ] Set appropriate Content-Security-Policy (CSP) headers.
- [ ] Set `X-Content-Type-Options: nosniff` to prevent MIME-type sniffing.
- [ ] For API responses containing user input, ensure JSON encoding escapes HTML-unsafe characters.

### HTTP Security Headers

| Header                           | Recommended Value                        |
|----------------------------------|------------------------------------------|
| `Content-Security-Policy`        | `default-src 'self'`                     |
| `X-Content-Type-Options`         | `nosniff`                                |
| `X-Frame-Options`                | `DENY`                                   |
| `Strict-Transport-Security`      | `max-age=31536000; includeSubDomains`    |
| `X-XSS-Protection`               | `0` (deprecated; rely on CSP)            |
| `Referrer-Policy`                | `strict-origin-when-cross-origin`        |

---

## 9. File System Security

### Rules

- [ ] Validate and sanitize all file paths derived from user input to prevent path traversal attacks.
- [ ] Use `os.path.abspath()` and verify the resolved path is within the allowed directory.
- [ ] Never use `eval()`, `exec()`, or `__import__()` with user-controlled input.
- [ ] Temporary files MUST be created in secure temp directories with restricted permissions.
- [ ] Restrict file permissions — 0644 for files, 0755 for directories; never 0777.

### Path Traversal Prevention

```python
import os

BASE_DIR = "/app/uploads/"

def safe_path(user_input: str) -> str:
    # Resolve and validate
    full_path = os.path.abspath(os.path.join(BASE_DIR, user_input))
    if not full_path.startswith(BASE_DIR):
        raise SecurityError("Path traversal detected")
    return full_path
```

---

## 10. Rate Limiting & Denial of Service Protection

### Rules

- [ ] All public API endpoints MUST have rate limiting configured.
- [ ] Implement request size limits for request bodies and file uploads.
- [ ] Set connection timeouts for all outbound HTTP calls and database connections.
- [ ] Paginate all list endpoints with a maximum page size.
- [ ] Avoid unbounded loops or recursion that depend on user-controlled input.

### Configuration Example

```python
# Rate limiting (using slowapi or similar)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/resource")
@limiter.limit("100/minute")
async def get_resource():
    ...
```

---

## Audit Checklist (Pre-Merge)

- [ ] Are all inputs validated against an allowlist?
- [ ] Is authentication enforced for protected endpoints?
- [ ] Are authorization checks in place for every sensitive action?
- [ ] Are parameterized queries used everywhere (no string formatting in SQL)?
- [ ] Are secrets properly externalized (env vars, vault)?
- [ ] Are logs free of passwords, tokens, and PII?
- [ ] Are error responses sanitized (no stack traces)?
- [ ] Are dependencies scanned for known vulnerabilities?
- [ ] Are HTTP security headers set?
- [ ] Is rate limiting applied to public endpoints?
- [ ] Are file path operations safe against traversal?
- [ ] Are temporary files handled securely?

---

## References

- [OWASP Top 10 (2021)](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [CWE/SANS Top 25](https://www.sans.org/top25-software-errors/)
- [Python Security Best Practices](https://snyk.io/blog/python-security-best-practices-cheat-sheet/)
