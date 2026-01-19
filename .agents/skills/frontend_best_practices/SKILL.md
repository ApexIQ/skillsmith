---
version: 0.1.0
name: frontend-best-practices
description: Use this skill when creating or modifying React frontend components. It defines UI/UX, styling, and architecture standards.
---

# ⚛️ Frontend Best Practices

## 1. Premium UX Principles
| Principle | Implementation | Example |
|---|---|---|
| **Optimistic UI** | Mutate state *instantly*, sync with server later. Revert on error. | Delete item -> Remove from list immediately -> Call API. |
| **Physics-Based Motion** | Use animation libraries with spring physics. No linear eases. | `framer-motion` with `type: "spring"`. |
| **Keyboard First** | Every action has a hotkey. Command palette for power users. | Global `Cmd+K` for navigation/actions. |

## 2. React Architecture
*   **Hooks:** Logic lives in custom hooks (`useAuth`, `useApi`), not in components.
*   **Context:** Use for global state (User, Theme). Avoid props drilling.
*   **Components:** Small, single-responsibility. Shared UI in `components/ui/`.

## 3. Styling (Tailwind or CSS-in-JS)
*   **Utility First:** Prefer utility classes over custom CSS.
*   **Conditional Styles:** Use a utility like `clsx` or `cn()` for conditionals.
    ```tsx
    <div className={cn("p-4", isActive && "bg-primary")} />
    ```
*   **Design Tokens:** Use semantic colors (`bg-background`, `text-foreground`) for dark mode.

## 4. Data Fetching
*   **SWR / TanStack Query:** Never use raw `useEffect` for API calls.
*   **Stale-While-Revalidate:** Show cached data while fetching fresh data.

## 5. Project Structure
```
src/
  features/       # Domain logic (Auth, Dashboard)
  components/     # Shared UI (Button, Modal)
  hooks/          # Custom hooks (useAuth, useKeyboard)
  lib/            # Utilities (API client, formatters)
  pages/          # Route components
```

## Examples
*   **New component:** Create in `components/ui/` -> Use utility classes -> Export from index.

## Guidelines
*   Test with testing-library (see `frontend_testing` skill).
*   Accessibility first: use semantic HTML and ARIA attributes.
