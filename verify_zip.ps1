$ErrorActionPreference = "Stop"

function Test-Command {
    param(
        [string]$Name,
        [scriptblock]$ScriptBlock,
        [scriptblock]$CheckBlock
    )
    Write-Host "Running Test: $Name..." -NoNewline
    try {
        & $ScriptBlock
        if ($CheckBlock) { & $CheckBlock }
        Write-Host " [PASS]" -ForegroundColor Green
    } catch {
        Write-Host " [FAIL]" -ForegroundColor Red
        Write-Host "Error: $_"
        exit 1
    }
}

if (Test-Path "test_zip_env") { Remove-Item "test_zip_env" -Recurse -Force }
New-Item -ItemType Directory -Path "test_zip_env" | Out-Null
Set-Location "test_zip_env"

# Test 1: List Categories (Should read JSON, ignoring zip)
Test-Command "List Categories" `
    { uv run skillsmith list --list-categories } `
    { }

# Test 2: Init (Should extract at least one skill from zip)
Test-Command "Init + Skill Extraction" `
    { uv run skillsmith init } `
    {
        $skills = Get-ChildItem ".agent/skills" -Recurse -Filter "SKILL.md" -ErrorAction SilentlyContinue
        if (-not $skills -or $skills.Count -lt 1) { throw "Extraction failed: no skills extracted to .agent/skills" }
    }

Set-Location ..
Remove-Item "test_zip_env" -Recurse -Force
Write-Host "`nZip Verification Completed."
