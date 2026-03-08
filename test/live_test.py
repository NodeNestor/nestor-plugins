"""
Live integration test — runs real Claude Code with all plugins installed.

Same pattern as rolling-context test container, but with actual Claude Code
executing prompts that exercise each plugin.
"""

import json
import os
import subprocess
import sys
import time


WORKSPACE = "/workspace/test-project"
RESULTS = []


def log(msg):
    print(f"  {msg}", flush=True)


def run_claude(prompt, cwd=WORKSPACE, timeout=120, permission_mode="bypassPermissions"):
    """Run claude -p with a prompt and return output."""
    env = os.environ.copy()
    # Use the rolling-context proxy if configured, otherwise direct API
    if os.environ.get("ANTHROPIC_BASE_URL"):
        env["ANTHROPIC_BASE_URL"] = os.environ["ANTHROPIC_BASE_URL"]

    cmd = ["claude", "-p", prompt, "--output-format", "text"]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
        output = result.stdout.strip()
        stderr = result.stderr.strip()
        return {
            "success": result.returncode == 0,
            "output": output,
            "stderr": stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "stderr": "TIMEOUT", "returncode": -1}
    except Exception as e:
        return {"success": False, "output": "", "stderr": str(e), "returncode": -1}


def run_test(name, fn):
    """Run a single test."""
    print(f"\n{'='*60}", flush=True)
    print(f"LIVE TEST: {name}", flush=True)
    print(f"{'='*60}", flush=True)
    try:
        fn()
        log("PASS")
        RESULTS.append((name, True, None))
    except AssertionError as e:
        log(f"FAIL: {e}")
        RESULTS.append((name, False, str(e)))
    except Exception as e:
        log(f"ERROR: {e}")
        RESULTS.append((name, False, str(e)))


# ============================================================
# Setup
# ============================================================

def setup():
    """Set up the test project."""
    print("Setting up test project...", flush=True)
    result = subprocess.run(
        ["bash", "/app/setup_project.sh"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"Setup failed: {result.stderr}", flush=True)
        sys.exit(1)
    print("Test project ready.", flush=True)

    # Verify Claude Code is installed
    result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
    print(f"Claude Code version: {result.stdout.strip()}", flush=True)

    # List plugin dirs
    plugins_dir = os.path.expanduser("~/.claude/plugins")
    if os.path.exists(plugins_dir):
        plugins = os.listdir(plugins_dir)
        print(f"Mounted plugins: {plugins}", flush=True)
    else:
        print("No plugins directory found", flush=True)


# ============================================================
# Tests
# ============================================================

def test_claude_basic():
    """Claude Code responds to a simple prompt."""
    result = run_claude("What is 2+2? Reply with just the number.", timeout=30)
    log(f"Output: {result['output'][:200]}")
    assert result["success"], f"Claude failed: {result['stderr']}"
    assert "4" in result["output"], f"Expected '4' in output"


def test_autoresearch_detect():
    """Autoresearch can detect the project type via MCP tool."""
    result = run_claude(
        "Use the detect_project tool to detect what type of project this is. "
        "Report the project type detected.",
        timeout=60,
    )
    log(f"Output: {result['output'][:300]}")
    assert result["success"], f"Claude failed: {result['stderr']}"
    # Should detect nodejs from package.json
    out_lower = result["output"].lower()
    assert "node" in out_lower or "javascript" in out_lower or "package" in out_lower, \
        f"Didn't detect Node.js project"


def test_worktrees_experiment():
    """Worktrees plugin can start and clean up an experiment."""
    result = run_claude(
        "Use the start_experiment tool with project_path='/workspace/test-project', "
        "description='Test experiment', num_variants=2, eval_cmd='npm test'. "
        "Then immediately use cleanup_experiment to clean it up. "
        "Report the experiment ID and cleanup status.",
        timeout=90,
    )
    log(f"Output: {result['output'][:400]}")
    assert result["success"], f"Claude failed: {result['stderr']}"


def test_workflows_list():
    """Workflows plugin finds the test workflow."""
    result = run_claude(
        "Use the list_workflows tool with project_path='/workspace/test-project'. "
        "Report what workflows you found.",
        timeout=60,
    )
    log(f"Output: {result['output'][:300]}")
    assert result["success"], f"Claude failed: {result['stderr']}"


def test_autofix_edit():
    """Autofix fires after Claude edits a file."""
    result = run_claude(
        "Edit the file src/utils/buggyCalc.ts — fix the sumRange function's off-by-one error "
        "(change i < end to i <= end). Report what happened after the edit.",
        timeout=90,
    )
    log(f"Output: {result['output'][:400]}")
    assert result["success"], f"Claude failed: {result['stderr']}"


def test_guardian_observe():
    """Guardian starts in observe mode and collects data."""
    result = run_claude(
        "Read 3 component files from src/components/ and tell me what naming "
        "convention they use.",
        timeout=60,
    )
    log(f"Output: {result['output'][:300]}")
    assert result["success"], f"Claude failed: {result['stderr']}"
    out_lower = result["output"].lower()
    assert "pascal" in out_lower or "component" in out_lower or "named" in out_lower, \
        f"Didn't recognize naming convention"


def test_multi_plugin():
    """Multiple plugins work together in a single session."""
    result = run_claude(
        "Do all of these:\n"
        "1. Use detect_project to identify this project type\n"
        "2. Use list_workflows to see available workflows\n"
        "3. Read src/components/UserCard.tsx\n"
        "4. Report what you found for each step.",
        timeout=90,
    )
    log(f"Output: {result['output'][:500]}")
    assert result["success"], f"Claude failed: {result['stderr']}"


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60, flush=True)
    print("NodeNestor Plugin Suite — LIVE Integration Tests", flush=True)
    print("=" * 60, flush=True)
    print(f"API Key: {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'NOT SET'}", flush=True)
    print(f"Base URL: {os.environ.get('ANTHROPIC_BASE_URL', 'default (api.anthropic.com)')}", flush=True)
    print(flush=True)

    # Check we have an API key
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_BASE_URL"):
        print("ERROR: Set ANTHROPIC_API_KEY or ANTHROPIC_BASE_URL to run live tests.", flush=True)
        print("Example: docker compose -f docker-compose.live.yml up", flush=True)
        sys.exit(1)

    setup()

    tests = [
        ("1. Basic Claude Code response", test_claude_basic),
        ("2. Autoresearch — detect project type", test_autoresearch_detect),
        ("3. Worktrees — start + cleanup experiment", test_worktrees_experiment),
        ("4. Workflows — list workflows", test_workflows_list),
        ("5. Autofix — edit triggers checks", test_autofix_edit),
        ("6. Guardian — observe naming conventions", test_guardian_observe),
        ("7. Multi-plugin — all plugins in one session", test_multi_plugin),
    ]

    for name, fn in tests:
        run_test(name, fn)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print("LIVE TEST RESULTS", flush=True)
    print(f"{'='*60}", flush=True)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    for name, ok, err in RESULTS:
        status = "PASS" if ok else "FAIL"
        suffix = f" — {err[:80]}" if err else ""
        print(f"  [{status}] {name}{suffix}", flush=True)
    print(f"\n  {passed} passed, {failed} failed, {len(RESULTS)} total", flush=True)
    print(f"{'='*60}", flush=True)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
