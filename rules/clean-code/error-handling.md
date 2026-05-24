# Clean Code: Error Handling

> **Purpose:** Establish a consistent, predictable error-handling strategy that makes failures transparent and debuggable without obscuring business logic.

---

## 1. Use Exceptions, Not Return Codes

- **Do not** use sentinel return values (`-1`, `null`, `undefined`) to signal errors.
- Throw exceptions or return discriminated result types, depending on language idioms.

**Bad:**
```typescript
function withdraw(amount: number): number {
  if (amount > balance) return -1; // sentinel
  balance -= amount;
  return 0;
}
```

**Good (exception):**
```typescript
function withdraw(amount: number): void {
  if (amount > balance) throw new InsufficientFundsError(amount, balance);
  balance -= amount;
}
```

**Good (result type — Rust/Go/functional-style):**
```typescript
function withdraw(amount: number): Result<void, InsufficientFundsError> {
  if (amount > balance) return Err(new InsufficientFundsError(amount, balance));
  balance -= amount;
  return Ok(undefined);
}
```

---

## 2. Error Types & Hierarchy

### 2.1 Define Custom Error Classes
- Extend the built-in `Error` class.
- Add context properties (`statusCode`, `code`, `details`, `cause`).

```typescript
class AppError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly statusCode: number = 500,
    options?: { cause?: Error; details?: unknown }
  ) {
    super(message, options);
    this.name = this.constructor.name;
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super(`${resource} with id '${id}' not found`, 'NOT_FOUND', 404);
  }
}
```

### 2.2 Error Hierarchy
```
Error
 └─ AppError
      ├─ NotFoundError        (404)
      ├─ ValidationError      (400)
      ├─ UnauthorizedError    (401)
      ├─ ForbiddenError       (403)
      ├─ ConflictError        (409)
      └─ ExternalServiceError (502) — wraps upstream failures
```

---

## 3. Fail Fast & Fail Safe

### 3.1 Fail Fast
- Validate inputs **at the boundary** (API handlers, constructors, public methods).
- Throw immediately when preconditions are violated — never carry corrupted state forward.

### 3.2 Fail Safe
- Provide sensible defaults for recoverable failures.
- Circuit-breaker / retry patterns for transient external failures.
- Always have a `catch` boundary at the outermost layer of every request/transaction to prevent unhandled rejections.

---

## 4. Write Your Try-Catch-Finally

### 4.1 One try per "unit of work"
- A `try` block should encompass a single logical operation.

**Bad:**
```typescript
try {
  const user = await db.findUser(id);
  const invoice = await billing.createInvoice(user);
  await mailer.send(invoice);
} catch (err) {
  // Which step failed? Hard to tell.
}
```

**Good:**
```typescript
const user = await db.findUser(id).catch(err => { throw new NotFoundError('User', id, { cause: err }); });
const invoice = await billing.createInvoice(user).catch(err => { throw new BillingError('createInvoice failed', { cause: err }); });
await mailer.send(invoice).catch(err => { throw new NotificationError('Invoice email failed', { cause: err }); });
```

Or use a functional error wrapper:

```typescript
function wrap<T>(promise: Promise<T>, errorFactory: (cause: Error) => AppError): Promise<T> {
  return promise.catch(err => { throw errorFactory(err); });
}
```

### 4.2 Avoid Empty Catch Blocks
- Every `catch` must either **handle**, **wrap**, or **log** the error.
- Empty `catch` silently swallows failures — never acceptable.

---

## 5. Error Propagation Boundaries

| Layer            | Handling Strategy                              |
|------------------|------------------------------------------------|
| Repository/DAO   | Wrap DB errors into domain errors; re-throw    |
| Service layer    | Throw domain errors; do not catch except to wrap with context |
| Controller       | Catch domain errors → format HTTP response     |
| Middleware        | Global catch-all; log structured error; return 500 |
| Event handlers   | Catch → log → ack (dead-letter if permanent)    |
| CLI entry points | Catch → log to stderr → exit with non-zero     |

---

## 6. Logging Errors

### 6.1 Log at the Boundary
- Log errors once at the **outermost** catch boundary, not at every intermediate layer.
- Include: error message, stack trace, correlation ID, request context, and any relevant business IDs.

### 6.2 Structured Logging
```json
{
  "level": "error",
  "message": "Failed to create invoice for user",
  "error": {
    "name": "BillingError",
    "code": "INVOICE_CREATION_FAILED",
    "stack": "..."
  },
  "context": {
    "userId": "usr_abc123",
    "correlationId": "req_xyz789"
  }
}
```

### 6.3 Log Levels
| Level   | When to use                                       |
|---------|---------------------------------------------------|
| `error` | Recoverable or unrecoverable failure; needs alert |
| `warn`  | Unexpected but handled (retry, fallback)           |
| `info`  | Normal operation; significant state changes        |
| `debug` | Detailed diagnostic info (not in production)       |

---

## 7. Don't Return Null / Undefined

- **Never return `null` or `undefined`** from a function that promises a value.
- Use `Option<T>` / `Maybe<T>` / `Optional<T>` types where available, or throw.
- Accepting `null` is acceptable only at **public API boundaries** with immediate validation.

**Preferred patterns:**
```typescript
// Option type
function findUser(id: string): Option<User> {
  const user = db.query(...);
  return user ? Some(user) : None;
}

// Default / Null Object
function getLogger(config?: LoggerConfig): Logger {
  return config ?? new NullLogger();
}
```

---

## 8. Special Cases: Wrapping Third-Party Errors

- Never leak third-party exception types through your domain boundaries.
- Wrap them in your own `AppError` subtypes.

```typescript
async function fetchUser(id: string): Promise<User> {
  try {
    return await axios.get(`/users/${id}`);
  } catch (err) {
    // Axios errors → domain errors
    if (axios.isAxiosError(err)) {
      throw new ExternalServiceError('UserService', err.message, {
        cause: err,
        details: { status: err.response?.status, url: err.config?.url }
      });
    }
    throw err; // rethrow if not an Axios error
  }
}
```

---

## 9. Asynchronous Error Handling

### 9.1 Always Handle Promise Rejections
```typescript
// Bad: unhandled rejection crashes the process
doSomethingAsync();

// Good: await with try-catch, or attach .catch()
await doSomethingAsync().catch(err => logger.error('doSomethingAsync failed', err));
```

### 9.2 Unhandled Rejection Handler
- Register a global handler in application startup that logs and exits gracefully.
- Node.js: `process.on('unhandledRejection', ...)`.
- Browsers: `window.addEventListener('unhandledrejection', ...)`.

---

## 10. Testing Error Paths

- Every error branch must have at least one test.
- Test **that** the error is thrown, and **what** type/context it carries.

```typescript
it('throws InsufficientFundsError when balance is too low', () => {
  const account = new Account({ balance: 50 });
  assert.throws(() => account.withdraw(100), InsufficientFundsError);
});
```

---

## 11. Enforcement

| Rule                              | Tool / Approach                       |
|-----------------------------------|---------------------------------------|
| No empty catch blocks             | ESLint `no-empty`                     |
| No return null from public APIs   | ESLint custom rule / code review      |
| Custom error class hierarchy      | Architecture test (`archunit`-style)   |
| Unhandled promise rejections      | ESLint `@typescript-eslint/no-floating-promises` |
| Error logged once per boundary    | Code review                           |
