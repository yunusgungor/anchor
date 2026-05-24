# Mocking Guide

## Core Principle

> *Mock only what you own. Prefer fakes and stubs for external dependencies. Over-mocking makes tests brittle and painful to maintain.*

Mocking is a technique for **isolating the system under test** by replacing real dependencies with controllable test doubles. Use it sparingly and deliberately.

---

## The Test Double Spectrum

```
Real Object ──→ Fake ──→ Stub ──→ Spy ──→ Mock
(Most faithful)                          (Most controlled)
```

| Type | Description | When to use |
|------|-------------|-------------|
| **Real Object** | The actual implementation | Fast, deterministic, no side effects |
| **Fake** | Lightweight working implementation (e.g., in-memory database, test file system) | When real object is slow, stateful, or side-effectful |
| **Stub** | Returns pre-configured values | When you need indirect input to the SUT |
| **Spy** | Records calls for later verification | When you need to verify that something was called |
| **Mock** | Pre-programmed with expectations (calls + return values + verification) | When you need to verify interaction protocols |

---

## Rules of Thumb

### Do NOT mock when you can use the real thing

```python
# ✅ Do: use real value objects
order = Order(items=[item1, item2])
assert order.total == Decimal("25.50")

# ❌ Don't: mock value objects
mocked_order = Mock(spec=Order)
mocked_order.total = Decimal("25.50")
```

### Do NOT mock what you don't own

```python
# ❌ Avoid: mocking third-party library internals
requests_mock.get("https://api.example.com/data", json={"key": "value"})

# ✅ Better: wrap third-party in an adapter, then mock the adapter
class PaymentGateway:
    def charge(self, amount: Decimal) -> PaymentResult:
        return requests.post(...)  # real call

# In tests: mock PaymentGateway, not requests
mock_gateway = Mock(spec=PaymentGateway)
mock_gateway.charge.return_value = PaymentResult.success()
```

### DO mock at the architectural boundary

Mock at **service boundaries** — not deep inside the implementation:

```
[Controller] → [Service] → [Repository] → [Database]
                             ↑
                      Mock here, not here
```

Mock the **interface/abstraction**, not the concrete class:

```python
# ✅ Good: mock the abstraction
mock_repo = Mock(spec=UserRepository)

# ❌ Bad: mock the concrete database class
mock_db = Mock(spec=PostgreSQLConnection)
```

---

## When to Mock

| Scenario | Mock? | Alternative |
|----------|-------|-------------|
| Database calls | ❌ | Use a fake (in-memory DB) or test database |
| HTTP API calls | ❌ | Use a fake API server (WireMock, VCR) |
| File system I/O | ❌ | Use temp files or in-memory filesystem |
| Time/Clock | ✅ | Mock `datetime.now()`, `time.sleep()` |
| Random/ID generation | ✅ | Mock UUID generators, random functions |
| Message queues | ❌ | Use fake broker (in-memory) |
| Logging | ✅ | Use spy on logger |
| Email sending | ❌ | Use fake mail server (MailHog, papercut) |
| Payment gateway | ❌ | Use sandbox/test mode of the provider |
| Authentication | ❌ | Override auth middleware in test config |

---

## Mocking Anti-Patterns

### 1. Mocking Value Objects

```python
# ❌ Wrong
mock_user = Mock()
mock_user.is_admin.return_value = True

# ✅ Right
user = User(name="Alice", roles=["admin"])
```

### 2. Overspecifying Interactions

```python
# ❌ Wrong — brittle, tests implementation
mock_service.do_something.assert_called_once_with(
    arg1=1, arg2=2, arg3=3, arg4=4
)

# ✅ Better — test behavior, not specific calls
result = service.process(data)
assert result.status == "completed"
```

### 3. Mocking Everything (The Mockery)

```python
# ❌ Wrong — everything is mocked, tests nothing real
mock_db = Mock()
mock_cache = Mock()
mock_queue = Mock()
mock_logger = Mock()

# ✅ Right — mock the boundary, use real objects for domain logic
repo = InMemoryOrderRepository()  # fake
service = OrderService(repo)
```

### 4. Mocking Too Deeply (Chain of Mocks)

```python
# ❌ Wrong — fragile, breaks on refactoring
mock_user.get_profile().get_address().city

# ✅ Right — return concrete objects from mocks
mock_profile = Profile(city="New York")
mock_user.get_profile.return_value = mock_profile
```

### 5. Partial Mocks of the SUT

```python
# ❌ Wrong — don't mock the system under test
order = Mock(spec=Order)
order.calculate_tax.return_value = 10.00   # testing a mock, not real code

# ✅ Right — use the real object
order = Order(items=[item])
order.calculate_tax()   # real behavior
```

---

## Language-Specific Guidelines

### Python (unittest.mock / pytest-mock)

```python
# Basic mock
from unittest.mock import Mock, patch

def test_send_notification(mocker):
    mock_email = mocker.patch("app.services.email.send")
    mock_email.return_value = {"status": "ok"}

    result = notification_service.notify(user_id=1)

    mock_email.assert_called_once_with(
        to="user@example.com",
        subject="Your notification"
    )
    assert result is True

# Fake (preferred over mock for databases)
class FakeUserRepository(UserRepository):
    def __init__(self):
        self._users = {}
    
    def save(self, user):
        self._users[user.id] = user
    
    def find_by_id(self, user_id):
        return self._users.get(user_id)
```

### JavaScript/TypeScript (Jest, Vitest)

```javascript
// Basic mock
jest.mock('../services/email');
import { sendEmail } from '../services/email';

test('sends notification', async () => {
    sendEmail.mockResolvedValue({ status: 'ok' });
    
    const result = await notificationService.notify({ userId: 1 });
    
    expect(sendEmail).toHaveBeenCalledWith({
        to: 'user@example.com',
        subject: 'Your notification',
    });
    expect(result).toBe(true);
});

// Stub a module
jest.spyOn(Date, 'now').mockReturnValue(1234567890);
```

### Go (gomock / testify)

```go
// Generate mock from interface
// mockgen -source=repository.go -destination=mock_repository.go -package=repository

func TestCreateUser(t *testing.T) {
    ctrl := gomock.NewController(t)
    defer ctrl.Finish()

    mockRepo := NewMockUserRepository(ctrl)
    mockRepo.EXPECT().Save(gomock.Any()).Return(nil)

    service := NewUserService(mockRepo)
    user, err := service.CreateUser("Alice", "alice@example.com")
    
    assert.NoError(t, err)
    assert.Equal(t, "Alice", user.Name)
}
```

---

## Mocking Strategy Decision Flow

```
Is the dependency fast and deterministic?
├── Yes → Use the real object
└── No → Is it a value object / data structure?
        ├── Yes → Use the real object
        └── No → Do you own the interface?
                ├── No → Wrap in an adapter, then mock the adapter
                └── Yes → Does it have side effects (I/O)?
                        ├── Yes → Use a Fake (preferred) or Mock
                        └── No → Use a Stub with controlled return values
```

---

## Measuring Mock Health

| Metric | Healthy | Warning | Danger |
|--------|---------|---------|--------|
| Mocks per test | 0–2 | 3–4 | 5+ |
| Test runtime | < 10ms | 10–100ms | > 100ms |
| Mocked external libraries | 0 | 1 | 2+ |
| Chain depth in mocks | 0–1 | 2 | 3+ |
| Tests broken by refactoring | < 5% | 5–20% | > 20% |

---

## References

- Gerard Meszaros, *xUnit Test Patterns* (definitive reference on Test Doubles)
- Martin Fowler, *Mocks Aren't Stubs* (martinfowler.com)
- Steve Freeman & Nat Pryce, *Growing Object-Oriented Software, Guided by Tests*
- Google Testing Blog, *TOWT: Don't Mock What You Don't Own*
