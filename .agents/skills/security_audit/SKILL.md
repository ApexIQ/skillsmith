---
version: 0.1.0
name: security-audit
description: Use this skill when reviewing code for security vulnerabilities. It covers OWASP Top 10 and common web security patterns.
---

# 🔒 Security Audit

> **Rule:** Assume every input is malicious. Verify everything.

## OWASP Top 10 Checklist

### 1. Injection (SQL, NoSQL, Command)
- [ ] Using parameterized queries? (SQLModel does this automatically)
- [ ] Never concatenating user input into queries?

### 2. Broken Authentication
- [ ] Passwords hashed with bcrypt/argon2?
- [ ] Session tokens are random and long (>128 bits)?
- [ ] Rate limiting on login endpoints?

### 3. Sensitive Data Exposure
- [ ] API keys/secrets in environment variables, NOT code?
- [ ] HTTPS enforced?
- [ ] Logging does NOT include passwords or tokens?

### 4. Broken Access Control (CRITICAL for this app)
- [ ] **Ownership check on EVERY resource access?**
    ```python
    if resource.user_id != current_user.id:
        raise HTTPException(404)  # Return 404, not 403
    ```
- [ ] Admin endpoints require admin role?

### 5. Security Misconfiguration
- [ ] Debug mode OFF in production?
- [ ] Default credentials changed?
- [ ] CORS restricted to allowed origins?

### 6. XSS (Cross-Site Scripting)
- [ ] User-generated content sanitized before rendering? (React auto-escapes)
- [ ] `dangerouslySetInnerHTML` avoided or sanitized?

### 7. Insecure Deserialization
- [ ] Using Pydantic for all input validation?
- [ ] Not using `pickle` on untrusted data?

## Examples
*   **Vulnerable:** `cursor.execute(f"SELECT * FROM users WHERE id = {user_input}")`
*   **Secure:** `cursor.execute("SELECT * FROM users WHERE id = ?", (user_input,))`

## Guidelines
*   Run `bandit` (Python) and `npm audit` (JS) in CI.
*   When in doubt, return 404 instead of 403 (don't leak existence).
*   Log security-relevant events (login attempts, access denials).
