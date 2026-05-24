# Clean Code: Naming & Structure

> **Purpose:** Enforce consistent, intention-revealing naming and logical file/module structure across the codebase.

---

## 1. Intention-Revealing Names

### 1.1 Pronounceable & Searchable
- Names must be **pronounceable** and **easily searchable**.
- Avoid single-letter names except for trivial loop counters (`i`, `j`, `k`) or mathematically conventional variables (`x`, `y`, `z` in geometry).

**Bad:**
```typescript
const d = 86400000; // what is "d"?
const fn = (a: string, b: string) => a + b;
```

**Good:**
```typescript
const MILLISECONDS_IN_A_DAY = 86_400_000;
const concatStrings = (left: string, right: string) => left + right;
```

### 1.2 Avoid Disinformation
- Do not use names that imply something they are not (e.g., `accountList` when the type is not a `List`; use `accounts` or `accountGroup`).
- Avoid names that differ only in casing (`getUser` vs `getuser`).
- Avoid leading/trailing underscores for visibility — use language-native access modifiers.

### 1.3 Meaningful Distinctions
- Names must make the distinction between different entities obvious.
- Avoid noise words: `Data`, `Info`, `Manager`, `Object` when they add no semantic value.

**Bad:** `getData()` / `processData()` / `handleData()`
**Good:** `fetchUserProfile()` / `normalizeEmail()` / `onLoginComplete()`

### 1.4 Use Problem-Domain Names
- Prefer **domain vocabulary** over computer-science terms when the reader is a domain expert.
- A `CreditAccount` is better than a `LedgerEntryContainer`.

---

## 2. Class & Type Naming

| Construct    | Convention                            | Example                         |
|-------------|---------------------------------------|---------------------------------|
| Class       | PascalCase, noun/noun-phrase          | `Customer`, `HttpClient`        |
| Interface   | PascalCase, no `I` prefix             | `Cacheable`, `UserRepository`   |
| Type Alias  | PascalCase, descriptive               | `JsonPrimitive`, `UserRole`     |
| Enum        | PascalCase for type, PascalCase for members | `OrderStatus.Pending`     |
| Record/DTO  | PascalCase, suffixed purposefully     | `CreateUserRequest`, `UserDto`  |

> **Note:** Do **not** prefix interfaces with `I`. It is a Hungarian-notation leftover that adds noise.

---

## 3. Function & Method Naming

- **Verbs or verb phrases:** `save()`, `deleteById()`, `isActive()`.
- **Boolean-returning:** prefix with `is`, `has`, `should`, `can`, `will`.
  - `isValid()`, `hasPermission()`, `shouldRetry()`, `canPublish()`.
- **Command-query separation:** Either perform an action (command) or return data (query), not both.
  - Avoid `processAndGetResult()` — split into `process()` + `getResult()`.

---

## 4. Variable & Property Naming

- **camelCase** for local variables, parameters, and properties.
- **SCREAMING_SNAKE_CASE** for constants and compile-time known values.
- **Descriptive but not redundant:** `user.name` not `user.userName`.

| Scope            | Convention       | Example                     |
|------------------|------------------|-----------------------------|
| Local variables  | camelCase        | `lastLogin`, `items`        |
| Parameters       | camelCase        | `request`, `userId`         |
| Constants        | SCREAMING_SNAKE  | `MAX_RETRY_COUNT`           |
| Private members  | camelCase, no `_`| `this.cache`                |

> Language-specific: In TypeScript/JavaScript, use `#` for truly private fields, not `_` prefix.

---

## 5. File & Module Structure

### 5.1 One Concept Per File
- One **primary export** per file (the concept the file represents).
- Group closely related helpers in the same file.

### 5.2 Consistent Module Organization
```
src/
  module/
    feature.controller.ts      # HTTP handlers
    feature.service.ts         # Business logic
    feature.repository.ts      # Data access
    feature.schema.ts          # Validation / DTO schemas
    feature.types.ts           # Types / interfaces
    feature.test.ts            # Unit tests
    __snapshots__/             # (for snapshot tests)
```

### 5.3 Import Ordering
1. Node built-ins (`fs`, `path`)
2. Third-party libraries (`express`, `lodash`)
3. Internal modules (`../core/`, `./feature.service`)
4. Relative imports (`./types`)
   → Separate groups with a blank line.

### 5.4 Avoid Deep Nesting
- Maximum **3 levels** of indentation per method.
- Extract inner blocks into named helper functions.

---

## 6. Folder Organization

- **Domain-driven:** Group by business capability, not by technical layer.
- Follow **consistent naming** within a monorepo:
  ```
  packages/
    billing/          # billing domain
    identity/         # authentication / authorization
    notifications/    # emails, push, SMS
  ```

- **Do** use `index.ts` (barrel files) to re-export public API.
- **Do not** create generic `/utils` folders — place utilities inside the domain they support.

---

## 7. Code Formatting & Conventions

- Enforce formatting with **Prettier** or equivalent auto-formatter.
- Maximum **80–100 characters** per line.
- Use **2-space indentation** (TypeScript/JavaScript) or **4-space** (Python, Java) — configured via `.editorconfig`.
- Trailing commas where syntactically valid (cleaner diffs).

---

## 8. Comment Discipline

### 8.1 Comments Must Explain "Why", Not "What"
- If code needs a comment to explain *what* it does, extract it into a well-named function.

**Comments that add no value:**
```typescript
// increment i by 1
i += 1;
```

**Useful comments:**
```typescript
// Use write-through cache because stale reads can cause double-billing.
const result = await cache.fetchWithWriteThrough(key, fetcher);
```

### 8.2 Keep Comments Close to the Code They Describe
- A comment at the top of a function that describes an inner block is a signal to extract that block.

### 8.3 Structured Doc Comments (JSDoc/TSDoc)
- Use for public APIs, exported functions, and complex types.
- Include `@param`, `@returns`, `@throws`, `@example` where helpful.
- Omit obvious doc comments (`/** Sets the name */ setName(...)`).

---

## 9. Enforcement

| Rule                       | Tool / Approach                               |
|----------------------------|-----------------------------------------------|
| Naming conventions         | ESLint `@typescript-eslint/naming-convention`  |
| Max line length            | Prettier `printWidth`                         |
| Import ordering            | `eslint-plugin-import` `import/order`         |
| File naming consistency    | Code review / `ls-lint`                       |
| No `I` prefix interfaces   | ESLint `@typescript-eslint/interface-name-prefix` (or forbid pattern) |
