import os
from pathlib import Path
from skills_agent_lib.cli import main

def test_init_scaffolding(runner, temp_project_dir, mock_templates, monkeypatch):
    """Test that init scaffolds the correct structure."""
    # Mock TEMPLATE_DIR in cli.py
    monkeypatch.setattr("skills_agent_lib.cli.TEMPLATE_DIR", mock_templates)
    
    with runner.isolated_filesystem(temp_dir=temp_project_dir):
        result = runner.invoke(main, ["init"])
        
        assert result.exit_code == 0
        assert "Successfully initialized .agents structure!" in result.output
        
        assert os.path.exists("AGENTS.md")
        assert os.path.exists(".agents/prd.md")
        assert os.path.exists(".agents/status.md")
        assert os.path.exists(".agents/skills/test-skill/SKILL.md")

def test_list_skills(runner, mock_templates, monkeypatch):
    """Test the list command."""
    monkeypatch.setattr("skills_agent_lib.cli.TEMPLATE_DIR", mock_templates)
    
    result = runner.invoke(main, ["list"])
    
    assert result.exit_code == 0
    assert "test-skill" in result.output
    assert "A test skill" in result.output

def test_lint_local(runner, mock_templates, monkeypatch):
    """Test the lint command on local templates."""
    monkeypatch.setattr("skills_agent_lib.cli.TEMPLATE_DIR", mock_templates)
    
    result = runner.invoke(main, ["lint", "--local"])
    
    assert result.exit_code == 0
    assert "test-skill" in result.output
    assert "PASS" in result.output

def test_lint_failure(runner, temp_project_dir, mock_templates, monkeypatch):
    """Test the lint command with a failing skill."""
    monkeypatch.setattr("skills_agent_lib.cli.TEMPLATE_DIR", mock_templates)
    
    # Create an invalid skill in the current directory's .agents/skills
    with runner.isolated_filesystem(temp_dir=temp_project_dir):
        skills_dir = Path(".agents/skills/bad-skill")
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("No frontmatter here")
        
        result = runner.invoke(main, ["lint"])
        
        assert result.exit_code != 0
        assert "bad-skill" in result.output
        assert "FAIL" in result.output
        assert "Missing YAML frontmatter start" in result.output

def test_update_skill(runner, temp_project_dir, mock_templates, monkeypatch):
    """Test updating a skill to a newer version."""
    monkeypatch.setattr("skills_agent_lib.cli.TEMPLATE_DIR", mock_templates)
    
    with runner.isolated_filesystem(temp_dir=temp_project_dir):
        # 1. Initialize with v0.1.0
        runner.invoke(main, ["init"])
        
        # 2. Update template to v0.2.0
        tpl_skill_md = mock_templates / ".agents" / "skills" / "test-skill" / "SKILL.md"
        tpl_skill_md.write_text("---\nversion: 0.2.0\nname: test-skill\ndescription: Updated skill\n---\n# New Content")
        
        # 3. Run update (using --force because version change makes content different)
        result = runner.invoke(main, ["update", "--force"])
        
        assert result.exit_code == 0
        # Verify content changed
        local_md = Path(".agents/skills/test-skill/SKILL.md")
        assert "0.2.0" in local_md.read_text()

def test_update_skip_modified(runner, temp_project_dir, mock_templates, monkeypatch):
    """Test that modified skills are skipped during update."""
    monkeypatch.setattr("skills_agent_lib.cli.TEMPLATE_DIR", mock_templates)
    
    with runner.isolated_filesystem(temp_dir=temp_project_dir):
        runner.invoke(main, ["init"])
        
        # Modify local skill
        local_md = Path(".agents/skills/test-skill/SKILL.md")
        local_md.write_text("User modified content")
        
        # Update template to v0.2.0
        tpl_skill_md = mock_templates / ".agents" / "skills" / "test-skill" / "SKILL.md"
        tpl_skill_md.write_text("---\nversion: 0.2.0\nname: test-skill\n---\nLibrary content")
        
        # Run update
        result = runner.invoke(main, ["update"])
        
        assert "PENDING" in result.output
        assert "no frontmatter" in result.output or "Modified" in result.output
        
        # Verify it wasn't overwritten
        assert "User modified content" in local_md.read_text()
        
        # Run with force
        result_force = runner.invoke(main, ["update", "--force"])
        assert "UPGRADED" in result_force.output
        assert "Library content" in local_md.read_text()
