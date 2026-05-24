# Clean Code: Function Design

> **Purpose:** Write small, focused, composable functions that do one thing well and communicate intent through their signature.

---

## 1. Small! Functions Must Be Small

- A function should fit entirely in your field of vision — ideally **≤ 20 lines**, rarely exceeding **40 lines**.
- If a function cannot fit on one screen, it is doing too much.

### What counts as "a line"?
- Every statement, control-flow construct body, and blank line separating logical blocks counts.
- Naturally, a function handling a complex domain rule may be slightly longer, but **extract helpers** ruthlessly.

---

## 2. Do One Thing (The Single Responsibility Principle for Functions)

A function does **one thing** if you cannot meaningfully extract another function from it.

**Test:** Can you describe what the function does in a single **non-connective** sentence?
- ❌ *"It validates the input **and** saves the record **and** sends a notification."* → 3 things.
- ✅ *"It persists an order after validation."* → 1 thing.

**Bad:**
```typescript
function processOrder(order: Order) {
  validateOrder(order);                       // validation
  const total = computeTotal(order.items);    // computation
  const saved = db.orders.save(order);        // persistence
  mailer.sendConfirmation(order.email, total);// side effect
  return saved;
}
```

**Good:**
```typescript
function processOrder(order: Order): Order {
  const validated = validateOrder(order);
  const persisted = persistOrder(validated);
  sendConfirmation(persisted);
  return persisted;
}
```

Each inner function is also independently testable.

---

## 3. One Level of Abstraction Per Function

- Statements within a function must be at the **same level of abstraction**.
- Mixing high-level intent with low-level details makes the function unreadable.

**Bad (mixed abstraction):**
```typescript
function renderPage(user: User) {
  const header = `<header>${user.name}</header>`;   // low-level string concat
  render("page", { user });                         // high-level rendering call
  fs.writeFileSync("/tmp/log", "rendered");         // low-level I/O
}
```

**Good:**
```typescript
function renderPage(user: User): string {
  const header = buildHeader(user);
  const body = buildBody(user);
  return assemblePage(header, body);
}
```

---

## 4. Command-Query Separation (CQS)

- **Commands** (procedures that change state) → return `void`.
- **Queries** (functions that return data) → have no side effects.

**Violation:**
```typescript
function setAndGetName(name: string): string {
  this.name = name;   // command
  return this.name;   // query
}
```

**Fixed:**
```typescript
setName(name: string): void { this.name = name; }
getName(): string { return this.name; }
```

---

## 5. Prefer Fewer Arguments

| Argument count | Guideline                              |
|---------------|----------------------------------------|
| **0**         | Ideal — niladic                        |
| **1**         | Good — monadic                         |
| **2**         | Acceptable — dyadic                    |
| **3**         | Consider extracting into an object     |
| **4+**        | Never — refactor into a parameter object |

**Why?**
- More arguments → harder to reason about, harder to test (combinatorial explosion).
- Temporal coupling between arguments is invisible.

**Bad:**
```typescript
function createUser(name: string, email: string, role: Role, isActive: boolean, notify: boolean) { ... }
```

**Good:**
```typescript
interface CreateUserOptions {
  name: string;
  email: string;
  role: Role;
  isActive?: boolean;
  notify?: boolean;
}

function createUser(options: CreateUserOptions): User { ... }
```

---

## 6. Avoid Side Effects (Pure Functions Where Possible)

- **Pure functions** (no side effects, same output for same input) are trivially testable and composable.
- Isolate I/O, mutations, and state changes at the boundaries of your system.

### Common side effects to isolate:
- Writing to disk / database
- Network calls
- Mutating global state / singletons
- Mutating input parameters
- Generating random numbers
- Accessing system clock

```typescript
// Impure — hard to test
function isExpired(item: Item): boolean {
  return item.expiresAt < Date.now(); // hidden dependency on system clock
}

// Pure — inject the clock
function isExpired(item: Item, now: Date = new Date()): boolean {
  return item.expiresAt < now;
}
```

---

## 7. Use Descriptive Names (Function Naming Recap)

| Pattern       | Use For                                  | Example                     |
|---------------|------------------------------------------|-----------------------------|
| `is/has/can`  | Boolean queries                          | `isValid()`, `hasAccess()`  |
| `get/fetch`   | Retrieval (query)                        | `getProfile()`, `fetchOrders()` |
| `set/update`  | Mutation (command)                       | `setName()`, `updateStatus()` |
| `create/build`| Object construction                     | `createUser()`, `buildQuery()` |
| `handle/on`   | Event/callback                           | `onSubmit()`, `handleError()` |
| `to*`         | Conversion                               | `toDto()`, `toPrimitive()`  |
| `ensure`      | Idempotent setup                         | `ensureDir()`, `ensureInitialized()` |

---

## 8. Don't Repeat Yourself (DRY)

- Extract repeated code into named functions — even if it's just 2–3 lines.
- But beware of **incidental duplication** (duplicate *structure* with different *meaning*); that may be two different things that happen to look the same today.

---

## 9. Structured Error Handling Within Functions

- Validate preconditions at the **top** of the function (fail fast).
- Handle errors at the appropriate abstraction level — don't catch an error just to rethrow the same type.
- Prefer **guard clauses** over nested `if` blocks.

**Guard clause pattern:**
```typescript
function withdraw(amount: number): void {
  if (amount <= 0) throw new ValidationError('Amount must be positive');
  if (amount > this.balance) throw new InsufficientFundsError(amount, this.balance);

  this.balance -= amount;
  this.transactions.push(new Transaction('withdraw', amount));
}
```

---

## 10. Function Composition

- Favor composing small functions over large procedural blocks.
- Use pipe/compose patterns where the language supports them.

```typescript
// Declarative composition
const processOrder = pipe(
  validateOrder,
  applyDiscounts,
  computeTax,
  persistOrder,
  sendConfirmation
);
```

---

## 11. Avoid Flag Arguments

- Boolean flags in function signatures indicate the function does two things.

**Bad:**
```typescript
function render(isAdmin: boolean) { ... }
// render(true) — What does true mean?
```

**Good:**
```typescript
function renderAdmin() { ... }
function renderUser() { ... }
```

Or use an options object:
```typescript
function render(options: { role: 'admin' | 'user' }) { ... }
```

---

## 12. Testing Functions

- Every function should be testable **in isolation** (dependency injection).
- Aim for **1 test per logical path** through the function.
- Pure functions require no mocking — they are the easiest to test.

```typescript
it('computes total with tax', () => {
  const result = computeTotal([{ price: 100, quantity: 2 }], 0.08);
  expect(result).toBe(216); // 200 + 8% tax
});

it('throws when amount exceeds balance', () => {
  expect(() => account.withdraw(9999)).toThrow(InsufficientFundsError);
});
```

---

## 13. Enforcement

| Rule                              | Tool / Approach                       |
|-----------------------------------|---------------------------------------|
| Max function length (≤ 20 lines)  | ESLint `max-lines-per-function` / Sonar |
| Max parameters (≤ 3)              | ESLint `max-params`                   |
| No boolean flags                  | ESLint custom rule / code review      |
| Cyclomatic complexity (≤ 5)       | ESLint `complexity` / Sonar           |
| Command-query separation          | Code review / architecture tests      |
| Pure function isolation            | Code review / dependency analysis     |
