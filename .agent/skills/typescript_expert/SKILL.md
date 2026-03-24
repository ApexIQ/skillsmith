---
version: 1.0.0
name: typescript-expert
description: Use this skill when writing or reviewing TypeScript/JavaScript code.
  Covers modern TS patterns, React best practices, Node.js patterns, type system mastery,
  bundler config, testing, and production-...
tags:
- promoted
- autonomous-repair
globs:
- '**/*.py'
---

# 📘 TypeScript Expert — Production-Grade TypeScript

> **Philosophy:** TypeScript's type system is your first line of defense. If it compiles, it should be mostly correct. If you're using `any`, you're using JavaScript with extra steps.

## 1. When to Use This Skill

- Writing new TypeScript/JavaScript modules
- Reviewing TS/JS code for patterns and type safety
- Building React components or Node.js services
- Configuring TypeScript projects (tsconfig, bundlers)
- Migrating JavaScript to TypeScript
- Debugging type errors

## 2. Type System Mastery

### Use Discriminated Unions Over Enums

```typescript
// GOOD: Discriminated union — exhaustive checking
type Result<T> =
  | { status: "success"; data: T }
  | { status: "error"; error: string }
  | { status: "loading" };

function handleResult(result: Result<User>) {
  switch (result.status) {
    case "success":
      console.log(result.data.name); // TS knows data exists
      break;
    case "error":
      console.error(result.error); // TS knows error exists
      break;
    case "loading":
      showSpinner();
      break;
    // If you miss a case, TS will warn you
  }
}

// BAD: Enum + separate error field — runtime bugs
enum Status { Success, Error, Loading }
interface Result { status: Status; data?: User; error?: string; }
```

### Utility Types

```typescript
// Don't reinvent — use built-in utility types
type UserCreate = Omit<User, "id" | "createdAt">;
type UserUpdate = Partial<Pick<User, "name" | "email">>;
type ReadonlyUser = Readonly<User>;
type UserRecord = Record<string, User>;

// Branded types for type-safe IDs
type UserId = string & { __brand: "UserId" };
type TeamId = string & { __brand: "TeamId" };

function getUser(id: UserId): User { ... }
// getUser("abc" as TeamId) → Type error!
```

### Zod for Runtime Validation

```typescript
import { z } from "zod";

const UserSchema = z.object({
  name: z.string().min(2).max(100),
  email: z.string().email(),
  role: z.enum(["member", "admin", "viewer"]).default("member"),
});

type User = z.infer<typeof UserSchema>; // Type derived from schema

// Validate at API boundary
const result = UserSchema.safeParse(requestBody);
if (!result.success) {
  return res.status(400).json({ errors: result.error.issues });
}
const user: User = result.data; // Fully typed and validated
```

## 3. React Patterns (2025+)

### Server Components First

```tsx
// GOOD: Server component (default in Next.js App Router)
// Runs on server, zero JS shipped to client
async function UserList() {
  const users = await db.getUsers(); // Direct DB access
  return (
    <ul>
      {users.map((user) => (
        <li key={user.id}>{user.name}</li>
      ))}
    </ul>
  );
}

// Client component — only when you need interactivity
"use client";
function SearchBar({ onSearch }: { onSearch: (q: string) => void }) {
  const [query, setQuery] = useState("");
  return <input value={query} onChange={(e) => setQuery(e.target.value)} />;
}
```

### Custom Hooks for Logic

```tsx
// GOOD: Logic extracted into testable hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

// Usage
function SearchPage() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);

  const { data } = useSWR(`/api/search?q=${debouncedQuery}`);
  return <SearchResults results={data} />;
}
```

### Component Composition Over Props Drilling

```tsx
// GOOD: Composition pattern
function Layout({ sidebar, content }: {
  sidebar: React.ReactNode;
  content: React.ReactNode;
}) {
  return (
    <div className="layout">
      <aside>{sidebar}</aside>
      <main>{content}</main>
    </div>
  );
}

// Usage — flexible, no prop drilling
<Layout
  sidebar={<Navigation items={navItems} />}
  content={<UserDashboard userId={userId} />}
/>
```

## 4. Node.js Patterns

### Error Handling with Custom Errors

```typescript
// Domain errors with HTTP status mapping
class AppError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number = 500,
    public readonly code: string = "INTERNAL_ERROR",
  ) {
    super(message);
    this.name = this.constructor.name;
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string) {
    super(`${resource} not found: ${id}`, 404, "NOT_FOUND");
  }
}

class ValidationError extends AppError {
  constructor(
    message: string,
    public readonly fields: Record<string, string>,
  ) {
    super(message, 400, "VALIDATION_ERROR");
  }
}
```

### Async Patterns

```typescript
// GOOD: Promise.allSettled for parallel with partial failures
const results = await Promise.allSettled([
  fetchUser(userId),
  fetchTeam(teamId),
  fetchPermissions(userId),
]);

const [userResult, teamResult, permResult] = results;
const user = userResult.status === "fulfilled" ? userResult.value : null;

// GOOD: AsyncIterator for streaming
async function* streamLogs(path: string) {
  const stream = createReadStream(path);
  for await (const chunk of stream) {
    yield chunk.toString();
  }
}
```

## 5. Project Configuration

### Strict tsconfig.json

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "moduleResolution": "bundler",
    "target": "ES2022",
    "module": "ESNext",
    "outDir": "dist",
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src"],
  "exclude": ["node_modules", "dist"]
}
```

**Rule:** Start with `"strict": true` on day one. Relaxing later is easy; tightening later is painful.

## 6. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| `any` as a type | `unknown` + type narrowing |
| `as` type assertions | Type guards: `if ('name' in obj)` |
| `enum` for simple values | `as const` objects or union types |
| Prop drilling 5+ levels | Context, composition, or state management |
| `useEffect` for derived data | `useMemo` or compute inline |
| `index.ts` barrel files everywhere | Direct imports to avoid circular deps |
| `console.log` debugging | Structured logging with `pino` or `winston` |
| Callback hell | `async/await` with proper error handling |

## Guidelines

- **Strict mode always.** `"strict": true` in every tsconfig.
- **Validate at boundaries.** Use Zod/Valibot at API boundaries, trust types internally.
- **Server components first.** Only add `"use client"` when you need interactivity.
- **Test with Vitest.** Fast, TypeScript-native, compatible with Jest API.
- **Use `biome` or `eslint` + `prettier`.** Autoformat, don't debate style.
- See `frontend-best-practices` skill for broader frontend architecture.
- See `frontend-testing-best-practices` skill for component testing patterns.
