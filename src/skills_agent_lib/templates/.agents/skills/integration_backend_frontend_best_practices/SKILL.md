---
version: 0.1.0
name: integration-testing
description: Use this skill when testing the full-stack integration between frontend and backend. Covers contract testing and E2E patterns.
---

# 🔗 Integration Testing Best Practices

> **Goal:** Ensure the "Handshake" between frontend and backend never breaks.

## 1. The Integration Pyramid
1.  **Contract Tests:**
    *   Verify API response shape matches frontend expectations.
    *   Use schema validation (Zod, Yup) on frontend to catch mismatches early.
2.  **Flow Tests (E2E):**
    *   Simulate full user journeys: Login -> Dashboard -> Action -> Logout.
    *   Tools: Playwright, Cypress, Puppeteer.

## 2. API Contract Strategy
*   **Single Source of Truth:**
    *   Backend defines schemas (Pydantic, Zod).
    *   Generate frontend types from OpenAPI/JSON Schema.
    *   Never manually duplicate type definitions.

## 3. Testing Failure Scenarios
*   **Network Errors:** What happens when API returns 500 or times out?
    *   Frontend should show error state, not crash.
    *   Optimistic updates should be reverted.
*   **Latency:** Test with network throttling to verify loading states.

## 4. E2E Test Example (Playwright)
```typescript
import { test, expect } from '@playwright/test';

test('user can complete checkout', async ({ page }) => {
  // 1. Navigate
  await page.goto('/products');
  
  // 2. Interact
  await page.getByRole('button', { version: 0.1.0
name: 'Add to Cart' }).click();
  await page.getByRole('link', { version: 0.1.0
name: 'Checkout' }).click();
  
  // 3. Fill form
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByRole('button', { version: 0.1.0
name: 'Place Order' }).click();

  // 4. Verify
  await expect(page.getByText('Order Confirmed')).toBeVisible();
});
```

## Examples
*   **Contract test:** Fetch user endpoint -> Validate response matches schema.
*   **E2E test:** Full signup flow across multiple pages.

## Guidelines
*   E2E tests are slow; use sparingly for critical paths only.
*   Mock external services (payment, email) in E2E tests.
*   Run E2E tests in CI before deployment.
