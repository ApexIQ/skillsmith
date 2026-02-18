import pytest
import zipfile
from pathlib import Path
from click.testing import CliRunner

@pytest.fixture
def runner():
    """Fixture for running CLI commands."""
    return CliRunner()

@pytest.fixture
def temp_project_dir(tmp_path):
    """Fixture for a temporary project directory."""
    d = tmp_path / "test_project"
    d.mkdir()
    return d

@pytest.fixture
def mock_templates(tmp_path):
    """Fixture to create a mock templates structure."""
    templates = tmp_path / "templates"
    agents = templates / ".agent"
    agents.mkdir(parents=True)
    
    # Create a mock skill directory and zip payload (used by init)
    skill_dir = agents / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_body = "---\nversion: 0.1.0\nname: test-skill\ndescription: A test skill\n---\n# Test Skill"
    (skill_dir / "SKILL.md").write_text(skill_body)
    with zipfile.ZipFile(agents / "skills.zip", "w") as zf:
        zf.writestr("skills/test-skill/SKILL.md", skill_body)
    
    # Create agents.md template
    (templates / "AGENTS.md").write_text("# AGENTS.md Template")
    
    # Create files inside .agent template
    (agents / "prd.md").write_text("# PRD Template")
    (agents / "status.md").write_text("# Status Template")
    
    return templates
