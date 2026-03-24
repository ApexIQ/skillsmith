---
version: 1.0.0
name: go-expert
description: Use this skill when writing or reviewing Go code. Covers Go idioms, concurrency patterns, error handling, project structure, testing, benchmarks, and production-grade Go standards.
---

# 🔷 Go Expert — Production-Grade Go

> **Philosophy:** Go is about simplicity and clarity. If your Go code is clever, it's wrong. Write boring, obvious code that any engineer can debug at 2 AM.

## 1. When to Use This Skill

- Writing new Go services or CLI tools
- Reviewing Go code for idioms and best practices
- Designing concurrent systems with goroutines
- Structuring Go projects for maintainability
- Writing effective Go tests and benchmarks
- Debugging Go-specific issues (goroutine leaks, race conditions)

## 2. Go Idioms

### Error Handling — The Go Way

```go
// GOOD: Check errors immediately, add context
user, err := db.GetUser(ctx, userID)
if err != nil {
    return fmt.Errorf("get user %s: %w", userID, err)
}

// GOOD: Custom error types for programmatic handling
type NotFoundError struct {
    Resource string
    ID       string
}

func (e *NotFoundError) Error() string {
    return fmt.Sprintf("%s not found: %s", e.Resource, e.ID)
}

// Check error type
var nfe *NotFoundError
if errors.As(err, &nfe) {
    http.Error(w, nfe.Error(), http.StatusNotFound)
    return
}

// BAD: Ignoring errors
user, _ := db.GetUser(ctx, userID) // Bug waiting to happen

// BAD: Generic error without context
if err != nil {
    return err // Which step failed? Nobody knows.
}
```

### Interfaces — Accept Interfaces, Return Structs

```go
// GOOD: Small, focused interface
type UserStore interface {
    GetUser(ctx context.Context, id string) (*User, error)
    CreateUser(ctx context.Context, u *User) error
}

// GOOD: Concrete struct that implements the interface
type PostgresUserStore struct {
    db *sql.DB
}

func (s *PostgresUserStore) GetUser(ctx context.Context, id string) (*User, error) {
    // Implementation
}

// GOOD: Function accepts interface
func NewUserService(store UserStore) *UserService {
    return &UserService{store: store}
}

// BAD: Interface with 20 methods — too broad
type Repository interface {
    GetUser(...) ...
    CreateUser(...) ...
    DeleteUser(...) ...
    GetTeam(...) ...
    // ... 16 more methods
}
```

**Rule:** Interfaces should have 1-3 methods. If your interface has 5+ methods, split it.

### Context — Thread It Everywhere

```go
// GOOD: Context flows through the entire call chain
func (s *UserService) CreateUser(ctx context.Context, req CreateUserRequest) (*User, error) {
    // Check for cancellation
    select {
    case <-ctx.Done():
        return nil, ctx.Err()
    default:
    }

    user, err := s.store.CreateUser(ctx, &User{Name: req.Name, Email: req.Email})
    if err != nil {
        return nil, fmt.Errorf("create user: %w", err)
    }

    // Pass context to downstream calls
    if err := s.notifier.SendWelcome(ctx, user); err != nil {
        // Log but don't fail — notification is best-effort
        slog.ErrorContext(ctx, "send welcome", "error", err, "user_id", user.ID)
    }

    return user, nil
}
```

## 3. Concurrency Patterns

### Worker Pool

```go
func processItems(ctx context.Context, items []Item, workers int) []Result {
    jobs := make(chan Item, len(items))
    results := make(chan Result, len(items))

    // Start workers
    var wg sync.WaitGroup
    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for item := range jobs {
                select {
                case <-ctx.Done():
                    return
                case results <- process(item):
                }
            }
        }()
    }

    // Send jobs
    for _, item := range items {
        jobs <- item
    }
    close(jobs)

    // Wait and collect
    go func() {
        wg.Wait()
        close(results)
    }()

    var out []Result
    for r := range results {
        out = append(out, r)
    }
    return out
}
```

### `errgroup` for Parallel with Error Handling

```go
import "golang.org/x/sync/errgroup"

func fetchAll(ctx context.Context) (*Dashboard, error) {
    g, ctx := errgroup.WithContext(ctx)
    var user *User
    var team *Team
    var perms []Permission

    g.Go(func() error {
        var err error
        user, err = fetchUser(ctx)
        return err
    })
    g.Go(func() error {
        var err error
        team, err = fetchTeam(ctx)
        return err
    })
    g.Go(func() error {
        var err error
        perms, err = fetchPermissions(ctx)
        return err
    })

    if err := g.Wait(); err != nil {
        return nil, fmt.Errorf("fetch dashboard: %w", err)
    }
    return &Dashboard{User: user, Team: team, Permissions: perms}, nil
}
```

## 4. Project Structure

```
my-service/
├── cmd/
│   └── server/
│       └── main.go            # Entry point — thin, just wiring
├── internal/                  # Private to this module
│   ├── user/
│   │   ├── handler.go         # HTTP handlers
│   │   ├── service.go         # Business logic
│   │   ├── store.go           # Database interface + impl
│   │   └── store_test.go
│   ├── team/
│   │   └── ...
│   └── middleware/
│       ├── auth.go
│       └── logging.go
├── pkg/                       # Importable by other projects (use sparingly)
│   └── httperr/
│       └── errors.go
├── go.mod
├── go.sum
├── Dockerfile
└── Makefile
```

**Rules:**
- `internal/` prevents external imports — use it for business logic
- `cmd/` contains entry points — should be thin (< 50 lines)
- Group by domain (`user/`, `team/`), not by layer (`handlers/`, `services/`)

## 5. Testing

```go
// Table-driven tests — the Go standard
func TestCreateUser(t *testing.T) {
    tests := []struct {
        name    string
        input   CreateUserRequest
        wantErr bool
        errMsg  string
    }{
        {
            name:  "valid user",
            input: CreateUserRequest{Name: "Jane", Email: "jane@test.com"},
        },
        {
            name:    "empty name",
            input:   CreateUserRequest{Name: "", Email: "jane@test.com"},
            wantErr: true,
            errMsg:  "name is required",
        },
        {
            name:    "invalid email",
            input:   CreateUserRequest{Name: "Jane", Email: "not-an-email"},
            wantErr: true,
            errMsg:  "invalid email",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            svc := NewUserService(newMockStore())
            _, err := svc.CreateUser(context.Background(), tt.input)

            if tt.wantErr {
                if err == nil {
                    t.Fatal("expected error, got nil")
                }
                if !strings.Contains(err.Error(), tt.errMsg) {
                    t.Errorf("error = %q, want containing %q", err, tt.errMsg)
                }
                return
            }
            if err != nil {
                t.Fatalf("unexpected error: %v", err)
            }
        })
    }
}

// Benchmark
func BenchmarkProcessItems(b *testing.B) {
    items := generateTestItems(1000)
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        processItems(context.Background(), items, 10)
    }
}
```

## 6. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| Goroutine without cancellation | Always pass `context.Context` |
| Unbuffered channel + no consumer | Size channels or use `select` with `default` |
| `sync.Mutex` protecting a `map` | `sync.Map` for simple cases, or protect with struct method |
| Returning `interface{}` / `any` | Return concrete types, accept interfaces |
| Package named `util`, `common`, `helpers` | Name by domain: `httperr`, `auth`, `cache` |
| `init()` functions for setup | Explicit initialization in `main()` |
| `panic()` in library code | Return errors — let the caller decide |

## Guidelines

- **`go vet` and `golangci-lint` in CI.** Non-negotiable.
- **Race detector in tests.** `go test -race ./...` on every PR.
- **Benchmark before optimizing.** `go test -bench . -benchmem`
- **Keep goroutine lifetimes explicit.** Every `go func()` needs a cancellation path.
- **Use `slog` for structured logging.** Not `fmt.Println` or `log.Printf`.
- See `build-resolver` skill for Go build and dependency issues.
