"""Constants and configuration values for Skillsmith."""

from pathlib import Path

# Version
SKILLSMITH_VERSION = "1.0.9"

# Default values
DEFAULT_TEMPLATE = "python-pro"
MIN_TRUST_SCORE = 65
MAX_CONTEXT_TOKENS = 128000

# Trusted domains for remote skills
TRUSTED_DOMAINS = ["github.com", "skills.sh"]

# Signature algorithms
ALLOWED_SIGNATURE_ALGORITHMS = ["hmac-sha256", "rsa-sha256"]

# Directory paths
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
PLATFORM_DIR = TEMPLATE_DIR / "platforms"

# Platform-specific rule files that each AI tool auto-reads
PLATFORM_FILES = {
    "gemini": {"src": "GEMINI.md", "dest": "GEMINI.md"},
    "claude": {"src": "CLAUDE.md", "dest": "CLAUDE.md"},
    "claude_orchestrator": {"src": ".claude/agents/orchestrator.md", "dest": ".claude/agents/orchestrator.md"},
    "claude_researcher": {"src": ".claude/agents/researcher.md", "dest": ".claude/agents/researcher.md"},
    "claude_implementer": {"src": ".claude/agents/implementer.md", "dest": ".claude/agents/implementer.md"},
    "claude_reviewer": {"src": ".claude/agents/reviewer.md", "dest": ".claude/agents/reviewer.md"},
    "claude_plan_feature": {"src": ".claude/commands/plan-feature.md", "dest": ".claude/commands/plan-feature.md"},
    "claude_implement_feature": {"src": ".claude/commands/implement-feature.md", "dest": ".claude/commands/implement-feature.md"},
    "claude_review_changes": {"src": ".claude/commands/review-changes.md", "dest": ".claude/commands/review-changes.md"},
    "claude_refactor": {"src": ".claude/commands/refactor.md", "dest": ".claude/commands/refactor.md"},
    "claude_debug": {"src": ".claude/commands/debug.md", "dest": ".claude/commands/debug.md"},
    "claude_test": {"src": ".claude/commands/test.md", "dest": ".claude/commands/test.md"},
    "claude_doc": {"src": ".claude/commands/doc.md", "dest": ".claude/commands/doc.md"},
    "claude_audit": {"src": ".claude/commands/audit.md", "dest": ".claude/commands/audit.md"},
    "claude_lint": {"src": ".claude/commands/lint.md", "dest": ".claude/commands/lint.md"},
    "claude_compose": {"src": ".claude/commands/compose.md", "dest": ".claude/commands/compose.md"},
    "claude_evolve": {"src": ".claude/commands/evolve.md", "dest": ".claude/commands/evolve.md"},
    "claude_align": {"src": ".claude/commands/align.md", "dest": ".claude/commands/align.md"},
    "claude_profile": {"src": ".claude/commands/profile.md", "dest": ".claude/commands/profile.md"},
    "claude_report": {"src": ".claude/commands/report.md", "dest": ".claude/commands/report.md"},
    "claude_sync": {"src": ".claude/commands/sync.md", "dest": ".claude/commands/sync.md"},
    "claude_autonomous": {"src": ".claude/commands/autonomous.md", "dest": ".claude/commands/autonomous.md"},
    "claude_metrics": {"src": ".claude/commands/metrics.md", "dest": ".claude/commands/metrics.md"},
    "claude_context": {"src": ".claude/commands/context.md", "dest": ".claude/commands/context.md"},
    "claude_verify": {"src": ".claude/commands/verify.md", "dest": ".claude/commands/verify.md"},
    "claude_review": {"src": ".claude/commands/review.md", "dest": ".claude/commands/review.md"},
    "claude_bootstrap": {"src": ".claude/commands/bootstrap.md", "dest": ".claude/commands/bootstrap.md"},
    "claude_migrate": {"src": ".claude/commands/migrate.md", "dest": ".claude/commands/migrate.md"},
    "claude_security": {"src": ".claude/commands/security.md", "dest": ".claude/commands/security.md"},
    "claude_performance": {"src": ".claude/commands/performance.md", "dest": ".claude/commands/performance.md"},
    "claude_benchmark": {"src": ".claude/commands/benchmark.md", "dest": ".claude/commands/benchmark.md"},
    "claude_search": {"src": ".claude/commands/search.md", "dest": ".claude/commands/search.md"},
    "claude_explain": {"src": ".claude/commands/explain.md", "dest": ".claude/commands/explain.md"},
    "claude_brainstorm": {"src": ".claude/commands/brainstorm.md", "dest": ".claude/commands/brainstorm.md"},
    "claude_cleanup": {"src": ".claude/commands/cleanup.md", "dest": ".claude/commands/cleanup.md"},
    "claude_debug_issue": {"src": ".claude/commands/debug-issue.md", "dest": ".claude/commands/debug-issue.md"},
    "claude_deploy_checklist": {"src": ".claude/commands/deploy-checklist.md", "dest": ".claude/commands/deploy-checklist.md"},
    "claude_test_changes": {"src": ".claude/commands/test-changes.md", "dest": ".claude/commands/test-changes.md"},
    "claude_swarm": {"src": ".claude/commands/swarm.md", "dest": ".claude/commands/swarm.md"},
    "claude_team_exec": {"src": ".claude/commands/team-exec.md", "dest": ".claude/commands/team-exec.md"},
    "claude_ready": {"src": ".claude/commands/ready.md", "dest": ".claude/commands/ready.md"},

    # Cursor-specific files
    "cursor": {"src": ".cursorrules", "dest": ".cursorrules"},
    "cursor_fast": {"src": ".cursor/README.md", "dest": ".cursor/README.md"},

    # Windsurf-specific files
    "windsurf": {"src": ".windsurfrules", "dest": ".windsurfrules"},

    # General agent instructions
    "agents": {"src": "AGENTS.md", "dest": "AGENTS.md"},
}

# Agent roles
AGENT_ROLES = ["Orchestrator", "Researcher", "Implementer", "Reviewer"]

# Workflow stages
WORKFLOW_STAGES = [
    "Discover",
    "Plan",
    "Build",
    "Review",
    "Test",
    "Ship",
    "Reflect"
]

# Priorities
PROJECT_PRIORITIES = [
    "testability",
    "maintainability",
    "verification",
    "automation"
]