# UPCOMING_FEATURES.md — The $100M Roadmap

**Date:** 2026-03-25
**Horizon:** 90-Day Execution Plan (3 Phases)
**North Star:** Skillsmith becomes the operating system for AI coding agents — the layer every team installs before their first AI-assisted commit.

---

## 0) Strategic Position (Why $100M Is Real)

**Market truth:** Every dev team is running AI agents. Zero of them have a trust layer, evolution engine, or readiness gate. They copy-paste CLAUDE.md files from GitHub (50K-star repos prove demand), then pray nothing breaks.

**Our wedge today:** `pip install skillsmith` → `skillsmith start` → agent-ready project with trust, composition, and CI gates.

**Our wedge tomorrow:** The only platform where skills self-evolve, agents learn from execution, and every improvement is trust-verified, profile-driven, and shared across teams.

**Competitive moat:**
- **OpenSpace** (HKUDS) has self-evolution but zero trust, zero profiles, zero CI — pure research.
- **Everything Claude Code** has 50K stars of content but zero infrastructure — copy-paste distribution, no integrity.
- **Skillsmith** has the infrastructure (trust, profiles, CI gates, 7-tool rendering, eval harness) — now we add the content depth AND the evolution engine.

**Nobody else combines all three: Trust × Evolution × Content.**

---

## 1) The Three Pillars to $100M

### Pillar 1: Content Gravity (Why developers install)
60+ production-grade skills, 15+ subagent personas, language-specific rule packs, real-world project templates. This is what drives 50K stars.

### Pillar 2: Self-Evolution Engine (Why developers stay)
Skills that auto-fix, auto-improve, and auto-learn from execution. Every task makes every skill smarter. This is what no competitor ships with trust guarantees.

### Pillar 3: Team Intelligence Platform (Why companies pay)
Shared skill evolution across teams, governance, CI gates, compliance audit trails, and usage analytics. This is the $100M revenue layer.

---

## 2) Phase 1: Ecosystem Dominance (Weeks 1-3)

**Goal:** Integrate the **Antigravity Awesome Skills (889+)** as the primary knowledge upstream.
**Success metric:** 50,000+ GitHub stars (Combined Ecosystem), 10,000+ PyPI downloads.

### 2.1 The Ghost-Sync Engine (Week 1)

Instead of building individual skills, we'll implement **Native Integration** with the global skill library:
- [x] **Ghost Branch Sync**: Sovereign Python-managed distribution of 889+ skills (👻 ghost-content) - v1.0.3.
- **`skillsmith add --remote awesome`**: Install any skill directly from our sovereign ghost branch.
- **Python-Native Integration**: Unified installer that pre-scaffolds `.agent/skills/` using the awesome library's DNA.
- **Trust-Verified Catalogs**: Pre-sign the top 100 most used skills from the awesome library for instant **Zero-Configuration Trust**.

### 2.2 Sync & Evolve (XSkill v1.5) (Week 1-2)

Leverage our **Autonomous Evolution Engine** on the massive 889+ skill pool:
- **DNA Extraction**: Use `evolve unlabeled` to reverse-engineer the most complex skills in the awesome library.
- **Benchmark Routing**: Automatically determine which models (Claude 3.5, Gemini 2.0, Deepseek v3) handle specific awesome-skills best.
- **Persona Swarms**: Group the 889+ skills into specialized **Swarm Persona Packs** (e.g., "Full-Stack Security Team", "Kubernetes Reliability Squad").

### 2.3 Real-World Project Templates (Week 2)

| Skill | Purpose | Inspired By |
|-------|---------|-------------|
| `planner` | Feature implementation planning with acceptance criteria | ECC planner.md |
| `architect` | System design decisions with tradeoff analysis | ECC architect.md |
| `tdd-guide` | Test-driven development workflow (RED→GREEN→REFACTOR) | ECC tdd-guide.md |
| `code-reviewer` | Quality, security, and maintainability review | ECC code-reviewer.md |
| `security-reviewer` | OWASP Top 10, vulnerability analysis, dependency audit | ECC security-reviewer.md |
| `build-resolver` | Build error diagnosis and fix (multi-language) | ECC build-error-resolver.md |
| `refactor-cleaner` | Dead code removal, DRY enforcement, complexity reduction | ECC refactor-cleaner.md |
| `doc-updater` | Documentation sync after code changes | ECC doc-updater.md |
| `loop-operator` | Autonomous loop execution with safety bounds | ECC loop-operator.md |
| `harness-optimizer` | Agent config tuning for token/cost efficiency | ECC harness-optimizer.md |
| `python-expert` | Python idioms, patterns, testing, packaging | ECC python-reviewer.md |
| `typescript-expert` | TS/JS patterns, React, Node.js, testing | ECC typescript-reviewer.md |
| `go-expert` | Go idioms, concurrency, testing, benchmarks | ECC go-reviewer.md |
| `java-expert` | Java/Spring Boot patterns, JPA, security | ECC java-reviewer.md |
| `database-expert` | SQL optimization, migrations, schema design | ECC database-reviewer.md |

**Implementation:**
- Each skill is a proper `SKILL.md` with YAML frontmatter (name, description, triggers, tools)
- Auto-discoverable by `skillsmith recommend` via project profile inference
- Installable via `skillsmith add <skill-name>` from local catalog

### 2.2 Language-Specific Rule Packs (Week 1-2)

Expand curated starter packs in `providers.py` with language-specific bundles:

| Pack | Contents |
|------|----------|
| `python-pack` | coding-standards, testing (pytest), security, patterns, Django/FastAPI |
| `typescript-pack` | coding-standards, React patterns, Node.js, testing (Vitest/Jest) |
| `go-pack` | idioms, concurrency patterns, testing, benchmarks |
| `java-pack` | Spring Boot patterns, JPA, security, Maven/Gradle |
| `rust-pack` | ownership patterns, error handling, testing |
| `swift-pack` | SwiftUI, concurrency, actor patterns, testing |
| `devops-pack` | Docker, CI/CD, deployment, monitoring |
| `full-stack-pack` | frontend + backend + database + deployment combined |

**Auto-selection logic:** Profile inference detects `languages` + `frameworks` → auto-recommends the right pack during `init --guided`.

### 2.3 Real-World Project Templates (Week 2)

Add 8 example project profiles with complete `.agent/` configurations:

1. **SaaS Starter** — Next.js + Supabase + Stripe + Vercel
2. **Python API** — FastAPI + PostgreSQL + Redis + Docker
3. **Go Microservice** — gRPC + PostgreSQL + Kubernetes
4. **Python Library** — Click/Rich + PyPI + GitHub Actions (dogfood!)
5. **Django App** — DRF + Celery + PostgreSQL + Redis
6. **Mobile App** — Flutter + Firebase + CI/CD
7. **Data Pipeline** — Python + Airflow + PostgreSQL + dbt
8. **Monorepo** — Turborepo + multiple services + shared libs

**Implementation:**
- `skillsmith init --template saas-starter`
- Each template includes: `project_profile.yaml`, starter skill set, example workflows, example CLAUDE.md/AGENTS.md
- Templates stored in `src/skillsmith/templates/examples/`

### 2.4 Slash Command Expansion (Week 2-3)

Expand `.agent/workflows/` command bundles from current set to 25+:

**Development Commands:**
- `/plan` — Implementation planning with acceptance criteria
- `/tdd` — Test-driven development workflow
- `/review` — Code review checklist execution
- `/refactor` — Safe refactoring with verification
- `/debug` — Structured debugging workflow

**Quality Commands:**
- `/security-scan` — Security audit against OWASP patterns
- `/test-coverage` — Coverage analysis and gap identification
- `/perf-audit` — Performance profiling and optimization
- `/lint-fix` — Auto-fix linting issues across project

**Operations Commands:**
- `/deploy-check` — Pre-deployment verification checklist
- `/incident` — Incident response workflow
- `/migrate` — Database migration planning and execution
- `/update-deps` — Dependency update with risk assessment

**Documentation Commands:**
- `/doc-sync` — Sync docs with code changes
- `/changelog` — Generate changelog from commits
- `/api-docs` — Generate API documentation

**Learning Commands:**
- `/learn` — Extract patterns from current session
- `/evolve` — Cluster learned patterns into skills
- `/retrospective` — Session retrospective and improvement plan

---

## 3) Phase 2: Self-Evolution Engine (Weeks 4-6)

**Goal:** Build the skill evolution engine that makes skillsmith the only tool where skills get smarter over time — with trust guarantees.
**Success metric:** Measurable skill quality improvement after 100+ task executions.

### 3.1 Skill Quality Metrics System (Week 4)

Add per-skill execution telemetry to `skills.lock.json`:

```json
{
  "skill_name": "python-expert",
  "version": "1.2.0",
  "metrics": {
    "applied_count": 147,
    "success_rate": 0.91,
    "completion_rate": 0.94,
    "fallback_rate": 0.06,
    "avg_token_cost": 2340,
    "avg_execution_time_ms": 4500,
    "user_override_rate": 0.12,
    "last_applied": "2026-03-24T18:00:00Z",
    "degradation_trend": "stable",
    "quality_score": 87
  }
}
```

**New commands:**
- `skillsmith metrics` — Show quality dashboard for all installed skills
- `skillsmith metrics <skill>` — Deep dive on one skill's performance
- `skillsmith metrics --export` — Export metrics for CI/analytics

### 3.2 Evolution Engine Core (Week 4-5)

`skillsmith evolve` — Three evolution modes inspired by OpenSpace:

**Mode 1: FIX** — Auto-repair degraded skills
```bash
skillsmith evolve --mode fix
# Detects skills with success_rate < 0.7 or degradation_trend == "declining"
# Analyzes failure patterns from execution logs
# Generates targeted diff patches to SKILL.md
# Validates fix against test cases before applying
# Records evolution in version DAG
```

**Mode 2: DERIVE** — Specialize skills for specific contexts
```bash
skillsmith evolve --mode derive --from python-expert --context "FastAPI APIs"
# Creates a new skill derived from parent
# Specializes instructions, examples, and triggers
# Maintains parent reference in lineage
# Coexists with parent (does not replace)
```

**Mode 3: CAPTURE** — Extract new skills from successful executions
```bash
skillsmith evolve --mode capture
# Scans recent compose/execution logs
# Identifies recurring successful patterns not covered by existing skills
# Generates new SKILL.md from extracted patterns
# Assigns confidence score based on pattern frequency
```

**Safety guarantees (what OpenSpace lacks):**
- All evolutions are lockfile-signed before activation
- Confirmation gates prevent false-positive triggers
- Anti-loop guards cap evolution frequency (max 3 per skill per day)
- Validation against existing test cases before replacing predecessors
- Full diff history in `.agent/skills/<name>/versions/` with version DAG

### 3.3 Version DAG & Lineage Tracking (Week 5)

Every skill maintains a version history with full lineage:

```
.agent/skills/python-expert/
├── SKILL.md              # Current active version
├── versions/
│   ├── v1.0.0.md         # Original
│   ├── v1.1.0.md         # FIX: improved error handling patterns
│   ├── v1.2.0.md         # DERIVE: FastAPI specialization
│   └── lineage.json      # Version DAG with diffs and metrics
```

**`lineage.json` structure:**
```json
{
  "current": "v1.2.0",
  "dag": {
    "v1.0.0": { "mode": "captured", "parent": null, "date": "2026-03-01" },
    "v1.1.0": { "mode": "fix", "parent": "v1.0.0", "trigger": "success_rate_drop", "diff_size": 23 },
    "v1.2.0": { "mode": "derived", "parent": "v1.1.0", "context": "FastAPI APIs", "diff_size": 45 }
  }
}
```

### 3.4 Post-Execution Analysis Hook (Week 5-6)

After every `compose` execution, auto-analyze outcomes:

```bash
# Automatic (runs after compose if --learn is enabled)
skillsmith compose "build user authentication" --learn

# Manual
skillsmith analyze-execution --session <session-id>
```

**Analysis pipeline:**
1. Capture execution trace (commands run, files changed, errors hit)
2. Score each skill's contribution (did it help? was it ignored? did it cause errors?)
3. Update skill metrics in lockfile
4. Suggest evolution if degradation detected
5. Offer to capture new patterns if novel successful workflow found

### 3.5 Eval-Driven Evolution (Week 6)

Wire evolution into the existing eval harness:

```bash
# Run eval, identify underperformers, auto-evolve
skillsmith eval --benchmark standard --evolve-on-failure

# CI gate: fail if evolved skills don't improve metrics
skillsmith eval --evolve-gate --min-improvement 5%
```

**Integration points:**
- `eval` → detects skill quality drops → triggers `evolve --mode fix`
- `compose --feedback` → reads evolution history → weights evolved skills higher
- `report` → includes evolution summary (skills improved, degraded, captured)

---

## 4) Phase 3: Team Intelligence Platform (Weeks 7-12)

**Goal:** Build the revenue layer — team skill sharing, governance, and analytics.
**Success metric:** 3 paying teams, $5K MRR within 90 days of launch.

### 4.1 Team Skill Marketplace (Week 7-8)

Extend `registry-service` + `trust-service` into a team skill marketplace:

```bash
# Publish an evolved skill to team registry
skillsmith publish <skill-name> --scope team --registry https://registry.company.com

# Browse team skills
skillsmith marketplace search "authentication patterns"

# Install team skill with trust verification
skillsmith marketplace install auth-expert --verify-publisher
```

**Revenue model:**
- Free: local skills, local evolution, local metrics
- Team ($29/seat/mo): shared registry, team evolution sync, usage analytics
- Enterprise ($99/seat/mo): RBAC, OIDC SSO, audit compliance, SLA

### 4.2 Collective Evolution (Week 8-9)

When one team member's skill evolves, the improvement propagates:

```bash
# Enable collective evolution for your team
skillsmith team sync --enable-collective

# View team evolution feed
skillsmith team feed

# Accept/reject team skill improvements
skillsmith team review --pending
```

**Trust-verified propagation:**
- Evolutions are signed by the author
- Team admin can set approval requirements (auto-accept, require-review, require-2-approvals)
- Revocation feed for compromised skills
- Transparency log for all team skill changes

### 4.3 Usage Analytics & ROI Dashboard (Week 9-10)

```bash
# CLI analytics
skillsmith analytics summary
skillsmith analytics --export json

# Metrics tracked:
# - Time saved per compose session
# - Token cost reduction from skill evolution
# - Error rate reduction from evolved skills
# - Team skill adoption rate
# - Most valuable skills by usage × success rate
```

**For enterprise sales:**
- "Your team saved X hours and $Y in tokens this month"
- "Skill evolution improved code review accuracy by Z%"
- Exportable compliance reports

### 4.4 Hook System & Automation (Week 10-11)

`skillsmith hooks` — Event-driven automation layer:

```bash
# Register hooks
skillsmith hooks add pre-commit "skillsmith ready --quick"
skillsmith hooks add post-compose "skillsmith metrics update"
skillsmith hooks add on-failure "skillsmith evolve --mode fix --auto"
skillsmith hooks add weekly "skillsmith evolve --mode capture --scan-logs"

# List active hooks
skillsmith hooks list

# Hook config stored in .agent/hooks/config.json
```

**Trigger types:**
- `pre-commit` / `post-commit` — Git integration
- `pre-compose` / `post-compose` — Workflow lifecycle
- `on-failure` / `on-success` — Execution outcomes
- `on-degradation` — Skill quality drops below threshold
- `scheduled` — Cron-like periodic triggers (daily metrics, weekly evolution)
- `on-drift` — Context index or profile drift detected

### 4.5 Continuous Learning v2 (Week 11-12)

Instinct-based learning pipeline (inspired by ECC, enhanced with trust):

```bash
# Extract patterns from current session
skillsmith learn
# → Identifies successful patterns
# → Creates instinct entries with confidence scores
# → Stores in .agent/learning/instincts.json

# Review learned instincts
skillsmith instincts list
skillsmith instincts list --confidence-above 0.8

# Cluster instincts into skills
skillsmith instincts evolve
# → Groups related instincts by semantic similarity
# → Generates new SKILL.md candidates
# → Requires confirmation before activation

# Import/export instincts for team sharing
skillsmith instincts export --format json
skillsmith instincts import team-instincts.json --verify-trust
```

**Instinct lifecycle:**
```
Session execution → Pattern extraction → Instinct (pending, confidence: 0.3)
Repeated observation → Confidence increase → Instinct (confirmed, confidence: 0.8)
Clustering → Skill candidate → Review → New SKILL.md (trust-signed)
```

### 4.6 Advanced Context Modes (Week 12)

Dynamic context injection based on current task type:

```bash
skillsmith compose "build auth" --mode development
skillsmith compose "review PR #42" --mode review
skillsmith compose "investigate memory leak" --mode debug
skillsmith compose "explore new API" --mode research
```

**Mode affects:**
- Which skills are prioritized in composition
- What depth of context is retrieved
- How much verification/reflection is injected
- Token budget allocation strategy

---

## 5) Advanced Features Backlog (Post-Phase 3)

### 5.1 AI-Native Features (Q3 2026)
- [ ] **Skill synthesis from natural language** — "Create a skill for handling GraphQL mutations" → generates full SKILL.md
- [ ] **Cross-project skill transfer** — Skills evolved in Project A automatically suggested in similar Project B
- [ ] **Execution replay** — Replay and debug past compose sessions step-by-step
- [ ] **Skill A/B testing** — Run two skill versions in parallel, auto-promote the winner
- [ ] **Predictive composition** — Suggest workflows before user asks, based on git activity patterns

### 5.2 Enterprise Features (Q3-Q4 2026)
- [ ] **SSO/OIDC integration** — Beyond current MVP, full enterprise IdP support
- [ ] **Compliance templates** — SOC 2, HIPAA, GDPR skill packs with audit trails
- [ ] **Managed KMS** — HSM-backed key custody for publisher verification
- [ ] **Role-based skill access** — Junior devs get guardrailed skills, seniors get full access
- [ ] **Org-wide evolution policies** — Central control over which skills can auto-evolve

### 5.3 Platform Features (Q4 2026)
- [ ] **Skillsmith Cloud** — Hosted registry, analytics, team management (SaaS revenue)
- [ ] **VS Code extension** — Native IDE integration beyond MCP
- [ ] **GitHub App** — Auto-run readiness checks on PRs, publish skill evolution in PR comments
- [ ] **Skill certification** — Verified skills with quality badges and publisher reputation scores
- [ ] **Agent observability** — Real-time monitoring of agent behavior across teams

### 5.4 Research & Ecosystem (2027)
- [ ] **Federated learning** — Privacy-preserving skill evolution across organizations
- [ ] **Multi-agent orchestration** — Native support for coordinating 3+ agents on one task
- [ ] **Skill compiler** — Compile high-level skill intent into optimized per-model instructions
- [ ] **Agent benchmark suite** — Standardized benchmark for comparing agent performance with/without skillsmith
- [ ] **Open skill protocol** — Contribute to/define the open standard for portable agent skills

---

## 6) Architecture Principles for Scale

### Non-Negotiable Foundations
1. **Library-first** — `pip install skillsmith` works offline, no hosted service required for core
2. **Trust-by-default** — Every skill change is signed, every evolution is auditable
3. **Profile-driven** — All composition, recommendation, and evolution is personalized to the project
4. **Deterministic outputs** — Every command supports `--json` for automation
5. **Backward-compatible** — Deprecated features get migration paths, never silent removal

### Scale Architecture
```
┌──────────────────────────────────────────────────┐
│                Skillsmith Cloud (SaaS)            │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Registry │  │Analytics │  │ Team Mgmt    │   │
│  │ Service  │  │ Service  │  │ Service      │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       └──────────────┼───────────────┘            │
│                      │ API Gateway                │
└──────────────────────┼───────────────────────────┘
                       │ HTTPS + JWT
┌──────────────────────┼───────────────────────────┐
│              Local CLI (pip install)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Evolution│  │ Compose  │  │ Trust        │   │
│  │ Engine   │  │ Engine   │  │ Engine       │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       └──────────────┼───────────────┘            │
│              Profile & Context Layer              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Skills   │  │ Metrics  │  │ Lockfile     │   │
│  │ Store    │  │ Store    │  │ Store        │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│              .agent/ (Local Filesystem)           │
└──────────────────────────────────────────────────┘
```

---

## 7) Revenue Trajectory

| Milestone | Timeline | Revenue | Signal |
|-----------|----------|---------|--------|
| Open source traction | Month 1-3 | $0 | 2K+ stars, 5K+ PyPI weekly |
| Team tier launch | Month 4 | $5K MRR | 3 paying teams |
| Enterprise pilot | Month 6 | $25K MRR | 1 enterprise contract |
| Series A ready | Month 9 | $80K MRR | 20+ teams, 3+ enterprises |
| Growth inflection | Month 12 | $200K MRR | Self-serve + enterprise pipeline |
| $100M ARR path | Month 24-36 | $8M+ ARR | Platform network effects |

**Key insight:** Every team that installs skillsmith trains skills that make the platform better for every other team. This is a **network-effect business**, not a tools business.

---

## 8) Execution Priority Matrix

### Do Now (This Sprint)
- [x] Complete Phase 1 content library (15 subagent skills)
- [x] Language-specific starter packs (8 packs)
- [x] Real-world project templates (8 templates)
- [ ] Slash command expansion (25+ commands)

### Do Next (Next Sprint)
- [ ] Skill quality metrics system
- [ ] Evolution engine core (FIX/DERIVE/CAPTURE)
- [ ] Version DAG & lineage tracking
- [ ] Post-execution analysis hook

### Do After PMF Signal
- [ ] Team skill marketplace
- [ ] Collective evolution
- [ ] Usage analytics dashboard
- [ ] Hook system
- [ ] Continuous learning v2

### Hard No (Until $1M ARR)
- ❌ Building a web dashboard UI
- ❌ Mobile apps
- ❌ Custom LLM training
- ❌ Horizontal platform plays outside developer tools
- ❌ Any feature that requires mandatory cloud dependency for core functionality

---

## 9) Release Gates

### Phase 1 Gate (Week 3)
- [x] 15+ subagent skills in catalog, installable via `skillsmith add` (36 total now)
- [x] 8 language packs auto-recommended by profile (Expert packs for PY, TS, GO, JAVA, RUST, CPP, RUBY, SWIFT)
- [x] 8 project templates working with `skillsmith init --template` (FastAPI, Next, React, CLI, Go, Java, Rust, Ruby)
- [x] 25+ total slash command bundles (33+ implemented: refactor, debug, test, doc, audit, lint, etc.)
- [ ] Full test suite green: `uv run python -m unittest discover tests -v`
- [x] Fresh install → init → align → doctor validated in clean Desktop environment (Pass 100/100)

### Phase 2 Gate (Week 6)
- [ ] `skillsmith evolve` ships with all 3 modes (fix/derive/capture)
- [ ] Skill metrics tracked and visible via `skillsmith metrics`
- [ ] Version DAG persisted and queryable
- [ ] Post-execution analysis runs automatically with `--learn`
- [ ] Eval-driven evolution wired and tested

### Phase 3 Gate (Week 12)
- [ ] Team registry + marketplace functional with trust verification
- [ ] Collective evolution with approval workflows
- [ ] Hook system with 6+ trigger types
- [ ] Continuous learning v2 with instinct lifecycle
- [ ] 3 paying teams on team tier

---

*Last updated: 2026-03-25 by competitive audit against OpenSpace (HKUDS) and Everything Claude Code (affaan-m).*
