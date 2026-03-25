# 📕 The Skillsmith Mission Cookbook
> A collection of recipes for building, scaling, and evolving your software with agentic subagents.

---

## 🏗️ Category 1: Feature Engineering (Creating the "What")
These recipes move you from an idea to a production-grade implementation.

### ⚡ Recipe 1: Standard API Endpoint
*   **The Goal**: Add a POST /payments endpoint to a FastAPI backend.
*   **The Tools**: `/context`, `/plan-feature`, `/implement-feature`, `/test`.
*   **🍳 The Recipe**:
    1.  `/context app/api` (Gather context).
    2.  `/plan-feature "Add POST /payments endpoint using Stripe"` (Get the blueprint).
    3.  `/implement-feature` (Let the subagent write the code).
    4.  `/test` (Verify logic).

### ⚡ Recipe 2: Database Model & Migration
*   **The Goal**: Add a `UserPreferences` table with Alembic migrations.
*   **The Tools**: `/search alembic`, `skillsmith add alembic`, `/plan-feature`, `/implement-feature`.
*   **🍳 The Recipe**:
    1.  `/search sqlmodel alembic` (Find best practice).
    2.  `skillsmith add sqlmodel alembic --remote` (Acquire skill).
    3.  `/plan-feature "add UserPreferences model and alembic script"`.
    4.  `/implement-feature`.

---

## 🪲 Category 2: Troubleshooting & Debugging (Fixing the "Ouch")
These recipes root-cause and repair issues that break your build or runtime.

### ⚡ Recipe 11: Race Condition Repair
*   **The Goal**: Root-cause a flaking test caused by a thread race.
*   **The Tools**: `/debug`, `/fix`, `/test --retries 5`.
*   **🍳 The Recipe**:
    1.  `/debug "test_async_flow flaking in CI logs"`.
    2.  Analyze the provided thread-trace analysis.
    3.  `/fix "add synchronization primitive to shared state"`.
    4.  `/test --retries 5` (Verify the fix is stable).

---

## 🏗️ Category 3: Refactoring (Improving the "How")
These recipes pay down technical debt and modernize architectural patterns.

### ⚡ Recipe 21: Monolith Decoupling
*   **The Goal**: Split a 2,000-line `ServiceHandler` class into three smaller modules.
*   **The Tools**: `skillsmith understand sync`, `/explain`, `/refactor`.
*   **🍳 The Recipe**:
    1.  `skillsmith understand sync --deep` (Identify hotspots).
    2.  `/explain "ServiceHandler dependencies"`.
    3.  `/refactor "split ServiceHandler into Order, Billing, and Shipping services"`.
    4.  `skillsmith align` (Check project stability).

---

## 🛡️ Category 4: Quality & Security (Guarding the "Why")
These recipes ensure your code is secure, accessible, and compliant.

### ⚡ Recipe 31: SOC2 Readiness Audit
*   **The Goal**: Run a full security audit across the codebase for SOC2 compliance.
*   **The Tools**: `/search security`, `skillsmith add security-audit`, `/security --audit`.
*   **🍳 The Recipe**:
    1.  `skillsmith add security-audit --remote awesome`.
    2.  `/security --audit "compliance-check"`.
    3.  `/report "security vulnerabilities"`.
    4.  `/fix` (Targeted repairs).

---

## 🚢 Category 5: DevOps & Scaling (Reaching the "Where")
These recipes get your code to the cloud and keep it running at scale.

### ⚡ Recipe 41: Dockerize legacy app
*   **The Goal**: Add a Dockerfile and docker-compose to an existing repo.
*   **The Tools**: `/search docker`, `/plan-feature`.
*   **🍳 The Recipe**:
    1.  `/search python-docker-best-practices`.
    2.  `/plan-feature "add Dockerfile and docker-compose.yml"`.
    3.  `/implement-feature`.
    4.  `/verify "docker build works"`.

---

## 🧠 Category 6: Architectural Mastery (Expanding the "Brain")
These recipes govern the AI infrastructure itself.

### ⚡ Recipe 51: Skill Self-Healing
*   **The Goal**: Repair a skill that is frequently failing to generate correct tests.
*   **The Tools**: `skillsmith metrics`, `skillsmith evolve --mode fix`.
*   **🍳 The Recipe**:
    1.  `skillsmith metrics "test-generator"` (Confirm failure rates).
    2.  `skillsmith evolve --mode fix "test-generator"`.
    3.  `/ready` (Verify evolution success).

---

### 💡 Pro-Tips for Chefs (Developers):
*   **Season with Context**: Always run `/context` before heavy implement missions.
*   **Taste the Code**: Run `/test` immediately after every `/implement-feature`.
*   **Follow the Gate**: If `skillsmith ready` is not 100/100, do not merge.
