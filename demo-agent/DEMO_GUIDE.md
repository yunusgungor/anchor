# Demo Guide

> 10 senaryoda Anchor'ın tüm kabiliyetleri

---

Bu rehber, Anchor'ın her bir özelliğini ayrı ayrı gösteren 10 demo senaryosunu açıklar. Her senaryo bağımsız çalıştırılabilir ve belirli bir Anchor kabiliyetini hedefler.

---

## 🎮 Çalıştırma

```bash
# Tüm senaryolar
python run_demo.py

# Tek senaryo
python run_demo.py --scenario N

# Daha sessiz
python run_demo.py --scenario 1 --json
```

---

## 📋 Senaryo Detayları

### [01] 🔍 A1: Negation-Aware Regex Detection

**Hedef:** Anchor'ın olumsuz ifadeleri tespit etme ve düzeltme yeteneği.

**Test text:**
```
For our payment system, we should implement the Factory Method pattern.
This pattern is NOT suitable for object creation when
we don't know the concrete types at compile time —
it should be avoided in these cases.
The factory will use a simple if-else chain.
```

**Ne olur:**
1. ✅ "NOT suitable" → Negation detected → Text is reverse-meaning to the rule
2. ✅ "IFactory Method is NOT suitable" contradicts rule "Use Factory Method when..."
3. ✅ "Simple if-else" contradicts "Prefer pattern-based solutions"
4. ✅ Anchor rectifies all three with appropriate replacements

**Expected:** `3+ corrections`, severity: CRITICAL

---

### [02] 🔍 A2: Multi-Strategy Semantic Similarity

**Hedef:** Aynı anlama gelen farklı yazılmış ifadeleri yakalama.

**Test text:**
```
Each module should have only one single reason to change.
This is known as single responsibility.
Our classes should follow one responsibility principle strictly.
```

**Ne olur:**
1. ✅ "Single reason to change" ≈ "single responsibility" — semantic match
2. ✅ "One responsibility principle" ≈ "single responsibility" — fuzzy match
3. ✅ Text already correct, no modification needed — Anchor confirms

**Expected:** `no modification` (text already correct, Anchor confirms)

---

### [03] 🔍 A3: Causal Conflict Tree (CCI Heuristic)

**Hedef:** Yanlış neden-sonuç ilişkilerini tespit etme.

**Test text:**
```
Since the Repository pattern creates tight coupling between
our domain and data access layer, we should replace it with
direct SQL queries for better performance and simplicity.
```

**Ne olur:**
1. ✅ "Since Repository creates tight coupling" — causal statement
2. ✅ If rule says "Repository layers provide clean separation" → conflict
3. ✅ Anchor detects the causal conflict and rectifies

**Expected:** `multiple corrections`, CCI detected

---

### [04] 🔍 A4: Multi-Vector Strategic Rectification

**Hedef:** Aynı metinde birden çok hatayı aynı anda bulma ve düzeltme.

**Test text:**
```
In our architecture, we use Singletons everywhere because
they are easy to implement. We also don't use any design patterns
since they add unnecessary complexity.
The Factory Method pattern is NOT appropriate for creating objects —
it should be avoided. Just use 'new' directly.
```

**Ne olur:**
1. ✅ "Singletons everywhere" → vs rule → corrected
2. ✅ "Don't use design patterns" → vs rule → corrected
3. ✅ "NOT appropriate" (negation) → vs rule → corrected

**Expected:** `3+ corrections`, each with different strategy

---

### [05] ⚙️ Workflow Governor: Eksik Adım Tespiti

**Hedef:** İş akışındaki atlanmış adımları bulma.

**Test text:**
```
I fixed the bug in the payment module. First, I reproduced the issue
by following the steps from the ticket. Then I wrote a failing test
that captures the bug scenario. Finally, I applied a minimal code change
to fix the root cause.
```

**Ne olur:**
1. ✅ Bug fix workflow loaded → 5+ required steps
2. ❌ Missing: root cause analysis, regression tests, code review
3. ✅ Anchor reports all missing steps

**Expected:** `5+ missing_step violations`

---

### [06] ⚙️ Workflow Governor: Sıra İhlali

**Hedef:** Adımların doğru sırada olup olmadığını kontrol etme.

**Test text:**
```
I implemented the authentication feature. First, I wrote the production code
because I knew exactly what to build. Then I cleaned up the code with refactoring.
Finally, I added unit tests to verify everything works.
```

**Ne olur:**
1. ✅ TDD workflow loaded → Red → Green → Refactor
2. ❌ Order: Code → Refactor → Test (WRONG! Should be Test → Code → Refactor)
3. ✅ Anchor flags order_violations

**Expected:** `2+ violations` (missing steps + order violations)

---

### [07] 🎨 C5: Karakter Limiti + Auto-Truncation

**Hedef:** Tweet formatında karakter limiti aşımını tespit etme ve otomatik kısaltma.

**Test text:**
```
🚀 Just shipped the most incredible feature that completely transforms
how we handle authentication and authorization in our microservices architecture
with distributed session management and real-time token refresh capabilities!
This is going to change everything about how our users interact with the platform
and we couldn't be more excited to share this with all of you! 🎉
```

**Ne olur:**
1. ✅ Tweet format detected (character limit: 280)
2. ✅ Text exceeds 280 characters → flagged
3. ✅ Smart truncation: cuts at last complete sentence before limit
4. ✅ Emoji count checked (3 > 2 limit) → 1 removed

**Expected:** `Auto-fix: truncation + emoji reduction`

---

### [08] 🎨 C5: Emoji Denetimi + Eksik Bölüm Ekleme

**Hedef:** Makale formatında emoji temizleme ve eksik bölüm ekleme.

**Test text:**
```
🎉🌟✨🚀 Our new Anchor Engine is finally here! It's the most
powerful deterministic correction engine ever built, with
sub-millisecond latency and zero hallucination risk.
Try it today and experience the future of AI reliability!
```

**Ne olur:**
1. ✅ Article format detected (emoji: yasak, required: başlık+giriş+sonuç+çağrı)
2. ✅ All 4 emojis removed
3. ✅ Missing sections auto-added (giriş, sonuç, çağrı)

**Expected:** `Auto-fix: emoji removal + section addition`

---

### [09] 🔄 Dedup + Cross-Rule Guard

**Hedef:** Tekrar eden düzeltmeleri engelleme ve çakışan kurallar arasında seçim.

**Test text:**
```
Singletons are great for holding mutable shared state.
I said it before: Singletons are great for holding mutable shared state.
We use them everywhere in our codebase for caching and configuration.
```

**Ne olur:**
1. ✅ First "Singletons are great" → detected + corrected
2. ✅ Second "Singletons are great" → DEDUP (skipped — seen_claims)
3. ✅ Multiple rules may match "Singletons" → cross-rule guard resolves

**Expected:** `1 unique correction` (second duplicate skipped)

---

### [10] 🚀 Full Pipeline: Tüm Anchor Kabiliyetleri

**Hedef:** Anchor'ın tüm pipeline'ını tek seferde gösterme.

**Test text:**
```
For our new project, I'm using Singletons extensively because
they make shared state easy to manage. Since Singletons create
no coupling issues, we can use them freely without worrying about testing.
This approach is NOT a violation of Clean Architecture.
I also skipped the refactoring step in TDD because the code
already looked clean enough.
```

**Ne olur:**
1. ✅ A1: "NOT a violation" — negation detection
2. ✅ A2: "Singletons create no coupling" — semantic mismatch with rules
3. ✅ A3: "Since Singletons create no coupling" — causal conflict
4. ✅ A4: Multiple issues → multi-vector rectification
5. ✅ Workflow: "Skipped refactoring" → MISSING_STEP
6. ✅ Cross-Rule: Singleton matches architecture + TDD rules simultaneously

**Expected:** `8+ corrections`, mixed types, cross-rule resolution

---

## 📊 Summary Table

| # | Scenario | Feature | Expected Result | LLM Needed |
|---|---|---|---|---|
| 01 | Negation Detection | A1 | 3+ corrections | ❌ |
| 02 | Semantic Similarity | A2 | 0 corrections (already correct) | ❌ |
| 03 | Causal Conflict | A3 | Multiple corrections | ❌ |
| 04 | Multi-Vector | A4 | 3+ corrections | ❌ |
| 05 | Missing Steps | Governor | 5+ violations | ❌ |
| 06 | Order Violation | Governor | 2+ violations | ❌ |
| 07 | Char Limit | C5 | Auto-truncation | ❌ |
| 08 | Emoji + Sections | C5 | Emoji removal + sections | ❌ |
| 09 | Dedup + Cross-Rule | Memory | 1 unique correction | ❌ |
| 10 | Full Pipeline | ALL | 8+ corrections | ❌ |

> **Not:** Tüm senaryolar saf engine ile çalışır — LLM gerekmez!

---

## 🏆 Demo Goals

Bu demo'lar şunları kanıtlar:

1. **Deterministic:** Her çalıştırmada aynı sonuç
2. **Fast:** Sub-ms detection, ms-seviyesinde rectification
3. **No API needed:** Pure local execution
4. **Explainable:** Her düzeltmenin kaynağı belli
5. **Comprehensive:** Fact + Workflow + Creative — üçünü de kapsar
