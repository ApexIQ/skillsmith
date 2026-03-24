---
version: 1.0.0
name: build-resolver
description: Use this skill when diagnosing and fixing build errors across any language or framework. Covers dependency resolution, compilation errors, configuration issues, CI failures, and environment mismatches.
---

# 🔧 Build Resolver — Fix Build Errors Fast

> **Philosophy:** Build errors are information, not punishment. Every error message contains the fix — you just need to read it correctly.

## 1. When to Use This Skill

- Build/compile errors blocking development
- CI pipeline failures
- Dependency resolution conflicts
- Environment mismatch issues (local works, CI fails)
- Package manager errors (npm, pip, cargo, go mod, maven, gradle)
- Docker build failures

## 2. The Build Error Resolution Framework

### Step 1: Read the ACTUAL Error

Most developers panic-Google the first red text they see. Instead:

1. **Find the FIRST error** — subsequent errors are often cascading
2. **Read the full message** — including the file path and line number
3. **Identify the error category** (see table below)

### Step 2: Categorize the Error

| Category | Signal | Common Causes |
|----------|--------|---------------|
| **Dependency** | "not found", "unresolved", "version conflict" | Missing install, version mismatch, lockfile drift |
| **Syntax** | "unexpected token", "parse error" | Typo, wrong language version, encoding issue |
| **Type** | "type mismatch", "cannot assign" | Wrong argument type, missing cast, API change |
| **Import** | "module not found", "no such file" | Wrong path, missing export, circular dependency |
| **Config** | "configuration error", "invalid option" | Wrong config file, deprecated option, env variable |
| **Environment** | "command not found", "permission denied" | Missing tool, wrong PATH, insufficient permissions |
| **Memory/Resource** | "out of memory", "heap size" | Large build, need to increase limits |

### Step 3: Apply the Fix Pattern

#### Dependency Errors
```bash
# Python
pip install -r requirements.txt    # or: uv sync
pip install --upgrade <package>     # version mismatch

# Node.js
rm -rf node_modules package-lock.json
npm install                         # fresh install

# Go
go mod tidy                        # clean up go.sum
go mod download                    # fetch dependencies

# Rust
cargo update                       # update Cargo.lock
cargo clean && cargo build         # full rebuild

# Java (Maven)
mvn dependency:resolve             # resolve deps
mvn clean install -U               # force update

# Java (Gradle)
./gradlew --refresh-dependencies   # force refresh
./gradlew clean build              # clean build
```

#### Import/Module Errors
```bash
# Check if the module actually exists
find . -name "module_name*"        # file search
grep -r "export.*functionName" .   # find the export

# Common fixes:
# 1. Check relative vs absolute imports
# 2. Check __init__.py exists (Python)
# 3. Check package.json "exports" field (Node.js)
# 4. Check go.mod module path (Go)
# 5. Check tsconfig.json "paths" (TypeScript)
```

#### Environment Errors
```bash
# Check tool versions
python --version
node --version
go version
java -version
rustc --version

# Check PATH
echo $PATH                         # Unix
$env:PATH                          # PowerShell

# Common fixes:
# 1. Install missing tool
# 2. Use version manager (pyenv, nvm, sdkman)
# 3. Check CI image has required tools
# 4. Set environment variables in CI config
```

### Step 4: Verify the Fix

```bash
# Always do a clean build after fixing
# Don't just re-run — clear caches first

# Python
rm -rf __pycache__ .pytest_cache
python -m pytest

# Node.js
rm -rf node_modules/.cache
npm run build

# Go
go clean -cache
go build ./...

# Rust
cargo clean
cargo build

# Docker
docker build --no-cache .
```

## 3. CI-Specific Failures

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Works locally, fails in CI" | Different OS, tool version, or env vars | Pin versions, use same base image |
| "Flaky — passes sometimes" | Race condition, time-dependent test, network call | Add retries, mock external calls |
| "Timeout" | Slow tests, no parallelism, large download | Increase timeout, cache deps, parallelize |
| "Permission denied" | File permissions, Docker user, secrets access | Check user context, fix permissions |
| "Out of disk space" | Build artifacts, Docker layers, cache bloat | Clean workspace, prune Docker, limit cache |

## 4. Language-Specific Quick Fixes

### Python
```bash
# "ModuleNotFoundError"
pip install <module>               # install missing
pip install -e .                   # install in dev mode

# "SyntaxError: invalid syntax"
python --version                   # check Python version
# Often: using 3.10+ syntax (match/case) on 3.9

# "ImportError: cannot import name"
# Circular import — restructure or use lazy import
```

### TypeScript/JavaScript
```bash
# "Cannot find module"
npm install                        # install deps
npx tsc --noEmit                   # type check only

# "Type error"
# Check tsconfig.json strict settings
# Check @types/* packages are installed

# "ERR_REQUIRE_ESM"
# Package is ESM-only, use dynamic import or update config
```

### Go
```bash
# "cannot find package"
go mod tidy
go get <package>@latest

# "imported and not used"
# Remove unused import or use blank identifier _

# "undefined: <name>"
# Check export (must be uppercase first letter)
```

### Java
```bash
# "package does not exist"
mvn dependency:tree                # inspect dep tree
# Check artifactId, groupId, version in pom.xml

# "cannot find symbol"
# Check import statement, class visibility (public/private)

# "incompatible types"
# Check generics, autoboxing, method signatures
```

## 5. Docker Build Failures

| Error | Fix |
|-------|-----|
| "COPY failed: file not found" | Check `.dockerignore`, verify file path relative to context |
| "returned a non-zero code" | Run failing command manually in container to see real error |
| "no space left on device" | `docker system prune -a` |
| "network unreachable" | Check DNS, proxy settings, `--network host` |
| Multi-stage build fails | Check `FROM ... AS builder` names match `COPY --from=builder` |

## Guidelines

- **Read the first error first.** Fix it, rebuild, then tackle the next.
- **Clean before retry.** Never just re-run a failed build without clearing caches.
- **Pin your versions.** In CI, use exact versions for everything (tools, deps, images).
- **Reproduce locally.** If CI fails, reproduce the exact environment before guessing.
- **Keep build logs.** Save the full output — you'll need it when the same error returns.
- See `debugging` skill for general diagnostic techniques.
- See `ci-cd-best-practices` skill for pipeline design patterns.
