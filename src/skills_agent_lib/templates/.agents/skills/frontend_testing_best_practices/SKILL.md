---
version: 0.1.0
name: frontend-testing
description: Use this skill when writing tests for React/Vue/Angular frontend applications. It covers component testing with modern testing libraries.
---

# ⚛️ Frontend Testing Best Practices

> **Philosophy:** Test how the *user* uses your app, not how the *code* is written.

## 1. The Stack
*   **Runner:** Vitest, Jest, or framework-specific runner.
*   **DOM Simulation:** Testing Library (React/Vue/Angular).
*   **User Simulation:** `@testing-library/user-event`.

## 2. Core Principles
*   **Prioritize Behavior:**
    *   ✅ `screen.getByRole('button', { version: 0.1.0
name: /submit/i })` (What user sees)
    *   ❌ `container.querySelector('.btn-primary')` (Implementation detail)
*   **Accessibility First:** Use `getByRole` queries. Forces accessible HTML.
*   **Mock External Dependencies:** Don't hit real APIs.
    *   Use MSW (Mock Service Worker) for network mocking.
    *   Mock complex libraries if just testing component logic.

## 3. Structure of a Test
```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyComponent from './MyComponent';

test('submitting the form shows success message', async () => {
  const user = userEvent.setup();
  render(<MyComponent />);

  // 1. Arrange (Find elements)
  const input = screen.getByLabelText(/email/i);
  const button = screen.getByRole('button', { version: 0.1.0
name: /submit/i });

  // 2. Act (User interaction)
  await user.type(input, 'test@example.com');
  await user.click(button);

  // 3. Assert (Expected outcome)
  expect(await screen.findByText(/success/i)).toBeInTheDocument();
});
```

## 4. Testing Advanced UI Patterns
*   **Optimistic UI:** Verify UI updates *before* API resolves.
*   **Animations:** Mock animation libraries or check final states.
*   **Keyboard Shortcuts:** Test with `user.keyboard('{Meta>}{k}{/Meta}')`.

## Examples
*   **Form validation:** Type invalid input -> Submit -> Verify error message shown.
*   **Modal:** Click button -> Verify modal opens -> Click outside -> Verify closes.

## Guidelines
*   One test = one user behavior.
*   Avoid testing implementation details (state, props).
*   Use `findBy` for async elements, `getBy` for sync.
