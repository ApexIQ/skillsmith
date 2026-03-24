---
version: 1.0.0
name: java-expert
description: Use this skill when writing or reviewing Java code. Covers modern Java (17+), Spring Boot patterns, JPA/Hibernate, Maven/Gradle, testing with JUnit 5, security patterns, and production-grade enterprise Java standards.
---

# ☕ Java Expert — Production-Grade Java

> **Philosophy:** Modern Java is not your grandfather's Java. Records, sealed classes, pattern matching, and virtual threads have transformed the language. Write modern Java, not enterprise Java from 2010.

## 1. When to Use This Skill

- Writing new Java services or libraries
- Reviewing Java code for modern patterns
- Building Spring Boot applications
- Working with JPA/Hibernate
- Configuring Maven or Gradle builds
- Writing tests with JUnit 5

## 2. Modern Java (17+)

### Records Over Boilerplate Classes

```java
// GOOD: Record — immutable, equals/hashCode/toString auto-generated
public record UserResponse(String id, String name, String email, Instant createdAt) {}

// GOOD: Record with validation
public record CreateUserRequest(String name, String email) {
    public CreateUserRequest {
        if (name == null || name.isBlank()) throw new IllegalArgumentException("name is required");
        if (email == null || !email.contains("@")) throw new IllegalArgumentException("invalid email");
    }
}

// BAD: 80-line POJO with getters, setters, equals, hashCode, toString, builder
public class UserResponse {
    private String id;
    private String name;
    // ... 70 more lines of boilerplate
}
```

### Sealed Classes for Domain Modeling

```java
// GOOD: Sealed hierarchy — compiler knows all cases
public sealed interface PaymentResult permits Success, Failed, Pending {
    record Success(String transactionId, BigDecimal amount) implements PaymentResult {}
    record Failed(String reason, String errorCode) implements PaymentResult {}
    record Pending(String pollUrl, Instant expiresAt) implements PaymentResult {}
}

// Pattern matching with exhaustive switch
String message = switch (result) {
    case Success s -> "Paid $%s (tx: %s)".formatted(s.amount(), s.transactionId());
    case Failed f -> "Failed: %s (%s)".formatted(f.reason(), f.errorCode());
    case Pending p -> "Pending — check %s".formatted(p.pollUrl());
};
```

### Virtual Threads (Java 21+)

```java
// GOOD: Virtual threads — millions of concurrent I/O operations
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<User>> futures = userIds.stream()
        .map(id -> executor.submit(() -> fetchUser(id)))
        .toList();

    List<User> users = futures.stream()
        .map(f -> {
            try { return f.get(); }
            catch (Exception e) { throw new RuntimeException(e); }
        })
        .toList();
}

// Spring Boot: Enable virtual threads
# application.properties
spring.threads.virtual.enabled=true
```

## 3. Spring Boot Patterns

### Layered Architecture

```
src/main/java/com/example/
├── Application.java           # @SpringBootApplication
├── user/
│   ├── UserController.java    # @RestController — HTTP layer
│   ├── UserService.java       # @Service — Business logic
│   ├── UserRepository.java    # @Repository — Data access
│   ├── User.java              # @Entity — JPA entity
│   ├── UserDto.java           # Records for API request/response
│   └── UserMapper.java        # Entity ↔ DTO mapping
├── team/
│   └── ...
└── common/
    ├── exception/
    │   ├── GlobalExceptionHandler.java
    │   └── ResourceNotFoundException.java
    └── config/
        ├── SecurityConfig.java
        └── WebConfig.java
```

### Controller Best Practices

```java
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public UserResponse createUser(@Valid @RequestBody CreateUserRequest request) {
        return userService.createUser(request);
    }

    @GetMapping("/{id}")
    public UserResponse getUser(@PathVariable String id) {
        return userService.getUser(id)
            .orElseThrow(() -> new ResourceNotFoundException("User", id));
    }

    @GetMapping
    public Page<UserResponse> listUsers(
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size
    ) {
        return userService.listUsers(PageRequest.of(page, size));
    }
}
```

### Global Exception Handling

```java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ErrorResponse handleNotFound(ResourceNotFoundException ex) {
        return new ErrorResponse("NOT_FOUND", ex.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ErrorResponse handleValidation(MethodArgumentNotValidException ex) {
        var errors = ex.getBindingResult().getFieldErrors().stream()
            .collect(Collectors.toMap(
                FieldError::getField,
                e -> Objects.requireNonNullElse(e.getDefaultMessage(), "invalid")
            ));
        return new ErrorResponse("VALIDATION_ERROR", "Validation failed", errors);
    }

    record ErrorResponse(String code, String message, Map<String, String> fields) {
        ErrorResponse(String code, String message) { this(code, message, Map.of()); }
    }
}
```

## 4. JPA/Hibernate

```java
@Entity
@Table(name = "users")
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(nullable = false, unique = true)
    private String email;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private Role role = Role.MEMBER;

    @CreationTimestamp
    private Instant createdAt;

    @UpdateTimestamp
    private Instant updatedAt;

    // N+1 prevention: use JOIN FETCH in repository
}

// GOOD: Prevent N+1 with explicit fetch
public interface UserRepository extends JpaRepository<User, String> {
    @Query("SELECT u FROM User u JOIN FETCH u.team WHERE u.id = :id")
    Optional<User> findByIdWithTeam(@Param("id") String id);

    // Projections for read-only queries (skip hydration overhead)
    @Query("SELECT new com.example.UserSummary(u.id, u.name, u.email) FROM User u")
    List<UserSummary> findAllSummaries();
}
```

## 5. Testing with JUnit 5

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock UserRepository userRepository;
    @InjectMocks UserService userService;

    @Test
    void createUser_validInput_returnsUser() {
        var request = new CreateUserRequest("Jane", "jane@test.com");
        when(userRepository.save(any())).thenAnswer(inv -> {
            User u = inv.getArgument(0);
            return u; // return the saved entity
        });

        var result = userService.createUser(request);

        assertThat(result.name()).isEqualTo("Jane");
        assertThat(result.email()).isEqualTo("jane@test.com");
        verify(userRepository).save(any(User.class));
    }

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = {" ", "  "})
    void createUser_invalidName_throws(String name) {
        var request = new CreateUserRequest(name, "jane@test.com");

        assertThatThrownBy(() -> userService.createUser(request))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("name");
    }
}

// Integration test with Testcontainers
@SpringBootTest
@Testcontainers
class UserIntegrationTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }
}
```

## 6. Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|----------------|-------------------|
| `null` returns | `Optional<T>` for query results |
| Checked exceptions everywhere | Unchecked exceptions for business errors |
| `@Autowired` field injection | Constructor injection (`@RequiredArgsConstructor`) |
| `@Transactional` on controller | `@Transactional` on service methods only |
| Lazy loading outside transaction | Eager fetch or DTO projections |
| `HashMap` for API responses | Record DTOs with proper types |
| `System.out.println` for logging | SLF4J: `log.info("message", args)` |
| XML configuration | Java config or application.yml |

## Guidelines

- **Java 17+ minimum.** Records, sealed, pattern matching are non-negotiable.
- **Constructor injection always.** Immutable, testable, explicit.
- **Test with real databases.** Testcontainers over H2 — test against what you deploy.
- **DTO ≠ Entity.** Never expose JPA entities directly in API responses.
- **Pagination by default.** Never return unbounded lists from APIs.
- See `build-resolver` skill for Maven/Gradle build issues.
- See `database-migrations` skill for schema change patterns.
