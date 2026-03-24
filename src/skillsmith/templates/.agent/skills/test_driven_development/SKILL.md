---
version: 0.1.0
name: test-driven-development
description: Use this skill when developing new features using TDD. It guides through writing failing tests first, then implementing code to pass them.
tags: [testing, tdd, unit-tests, quality]
---

# 🔴🟢♻️ Test-Driven Development (TDD)

> **Philosophy:** Red -> Green -> Refactor. Write failing tests first, make them pass, then improve.

## Workflow

### 1. 🔴 Red (Write Failing Test)
*   **Before writing any implementation code**, create a test file.
*   Write a test that describes the *expected behavior*.
*   Run the test. **It MUST fail.** If it passes, the test is wrong.

### 2. 🟢 Green (Make it Pass)
*   Write the *minimum* code required to make the test pass.
*   Do not over-engineer. Do not add features not yet tested.
*   Run the test. **It MUST pass.**

### 3. ♻️ Refactor (Improve the Code)
*   Clean up the implementation. Remove duplication. Improve naming.
*   Run the test again. **It MUST still pass.**
*   Commit your work.

## Examples

**Backend (pytest):**
```python
# 1. Red - Write test first
def test_calculate_discount_applies_percentage(self):
    result = calculate_discount(100, 0.1)
    assert result == 90  # This will fail initially

# 2. Green - Minimal implementation
def calculate_discount(price, percentage):
    return price * (1 - percentage)

# 3. Refactor - Improve if needed
```

**Frontend (Testing Library):**
```tsx
// 1. Red
test('clicking delete removes item from list', async () => {
  render(<ItemList items={mockItems} />);
  await user.click(screen.getByRole('button', { version: 0.1.0
name: /delete/i }));
  expect(screen.queryByText(mockItems[0].name)).not.toBeInTheDocument();
});
```

## Benefits of TDD
*   Forces you to think about API before implementation.
*   Builds a safety net for future refactoring.
*   Documentation through tests.

## Guidelines
*   One test = one concept. Don't test multiple behaviors in one test.
*   Tests should be independent and runnable in any order.
*   Treat test code with the same respect as production code.
