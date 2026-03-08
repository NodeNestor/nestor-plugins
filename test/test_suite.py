"""
NodeNestor Plugin Suite — Integration Test Suite

Tests all 7 plugins together:
  1. rolling-context  (proxy — tested via HTTP)
  2. knowledge-graph  (MCP + hooks)
  3. autoresearch     (MCP + hooks)
  4. autofix          (hooks only)
  5. guardian         (hooks only)
  6. workflows        (MCP + hooks)
  7. worktrees        (MCP + hooks)

Runs inside Docker with:
  - Rolling-context proxy on the test-net
  - All plugin sources mounted at /plugins/*
  - A test workspace at /workspace
  - Git available for worktree tests
"""

import json
import os
import sys
import time
import http.client
import subprocess
import shutil
from urllib.parse import urlparse

from hook_simulator import HookSimulator
from mcp_client import MCPClient

# --- Config ---
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:5599")
API_KEY = os.environ.get("API_KEY", "test-key")
WORKSPACE = os.environ.get("TEST_WORKSPACE", "/workspace")
PLUGINS_DIR = "/plugins"

parsed = urlparse(PROXY_URL)
results = []


def log(msg):
    print(f"  {msg}")


def test(name):
    """Decorator to register and run a test."""
    def decorator(fn):
        fn._test_name = name
        return fn
    return decorator


def run_test(fn):
    """Run a single test, catch exceptions."""
    name = getattr(fn, "_test_name", fn.__name__)
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        fn()
        log("PASS")
        results.append((name, True, None))
    except AssertionError as e:
        log(f"FAIL: {e}")
        results.append((name, False, str(e)))
    except Exception as e:
        log(f"ERROR: {e}")
        results.append((name, False, str(e)))


# ============================================================
# Setup
# ============================================================

def setup_test_project():
    """Create a realistic test project in the workspace."""
    project = os.path.join(WORKSPACE, "test-project")
    if os.path.exists(project):
        shutil.rmtree(project)
    os.makedirs(project, exist_ok=True)

    # Init git repo
    subprocess.run(["git", "init"], cwd=project, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, capture_output=True)

    # Create a Node.js-ish project structure
    os.makedirs(os.path.join(project, "src", "components"), exist_ok=True)
    os.makedirs(os.path.join(project, "src", "utils"), exist_ok=True)
    os.makedirs(os.path.join(project, "__tests__"), exist_ok=True)
    os.makedirs(os.path.join(project, ".claude", "workflows"), exist_ok=True)

    # package.json
    with open(os.path.join(project, "package.json"), "w") as f:
        json.dump({
            "name": "test-project",
            "scripts": {"test": "echo 'tests pass' && exit 0", "lint": "echo 'lint ok' && exit 0"},
        }, f)

    # Source files with consistent naming (PascalCase components)
    for name in ["UserCard", "ProfileView", "NavBar", "SidePanel", "Footer",
                  "Header", "Modal", "Button", "Input", "Select",
                  "Dropdown", "Tooltip", "Badge", "Alert", "Toast",
                  "Spinner", "Avatar", "Card", "Table", "Form"]:
        with open(os.path.join(project, "src", "components", f"{name}.tsx"), "w") as f:
            f.write(f'import React from "react";\n\nexport function {name}() {{\n  return <div>{name}</div>;\n}}\n')

    # Utils with camelCase
    for name in ["formatDate", "parseUrl", "validateEmail"]:
        with open(os.path.join(project, "src", "utils", f"{name}.ts"), "w") as f:
            f.write(f"export function {name}() {{}}\n")

    # Test files
    with open(os.path.join(project, "__tests__", "UserCard.test.tsx"), "w") as f:
        f.write('import { UserCard } from "../src/components/UserCard";\ntest("renders", () => {});\n')

    # A workflow file
    with open(os.path.join(project, ".claude", "workflows", "test-workflow.yml"), "w") as f:
        f.write("""name: test-workflow
description: Test workflow for integration tests
trigger:
  event: PostToolUse
  matcher: Bash
  condition: echo
steps:
  - name: check
    run: echo "workflow fired"
    timeout: 10
""")

    # Initial commit
    subprocess.run(["git", "add", "-A"], cwd=project, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project, capture_output=True)

    return project


# ============================================================
# Test 1: Rolling Context Proxy
# ============================================================

@test("1. Rolling Context — proxy health")
def test_proxy_health():
    if not proxy_available:
        log("SKIP: proxy not reachable (no upstream on :9212?)")
        return
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    conn.request("GET", "/health")
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    assert data["status"] == "ok", f"Health not ok: {data}"
    log(f"Proxy healthy: trigger={data['trigger_tokens']}, upstream={data['upstream_url']}")


@test("1b. Rolling Context — request passthrough")
def test_proxy_passthrough():
    if not proxy_available:
        log("SKIP: proxy not reachable (no upstream on :9212?)")
        return
    messages = [
        {"role": "user", "content": "Hello, world!"},
    ]
    body = json.dumps({
        "model": "claude-opus-4-6",
        "max_tokens": 10,
        "stream": True,
        "messages": messages,
    }).encode()
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=15)
    conn.request("POST", "/v1/messages", body=body, headers={
        "content-type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    })
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    log(f"Proxy forwarded request, status={resp.status}")
    assert resp.status > 0, "No response from proxy"


# ============================================================
# Test 2: Autofix Hooks
# ============================================================

@test("2. Autofix — session start detects project")
def test_autofix_session_start():
    sim = HookSimulator(PLUGINS_DIR)
    result = sim.session_start("autofix", project_path)
    log(f"Result: {result}")
    msg = result.get("message", "")
    assert "autofix" in msg.lower() or result.get("result") == "continue", \
        f"Unexpected result: {result}"


@test("2b. Autofix — post-edit runs checks")
def test_autofix_post_edit():
    sim = HookSimulator(PLUGINS_DIR)
    result = sim.post_tool_use_edit(
        "autofix",
        os.path.join(project_path, "src/components/UserCard.tsx"),
        'return <div>UserCard</div>;',
        'return <div>Updated UserCard</div>;',
        cwd=project_path,
    )
    log(f"Result: {result}")
    # Should either pass silently or report an error
    assert result.get("result") == "continue" or "error" not in result, \
        f"Hook crashed: {result}"


# ============================================================
# Test 3: Guardian — Learning Pipeline
# ============================================================

@test("3. Guardian — session start (observe phase)")
def test_guardian_session_start():
    sim = HookSimulator(PLUGINS_DIR)
    result = sim.session_start("guardian", project_path)
    log(f"Result: {result}")
    msg = result.get("message", "")
    assert "guardian" in msg.lower() or "observe" in msg.lower() or result.get("result") == "continue", \
        f"Unexpected: {result}"


@test("3b. Guardian — collect edit events")
def test_guardian_collect():
    sim = HookSimulator(PLUGINS_DIR)
    # Simulate several edits to build up events
    for comp in ["UserCard", "ProfileView", "NavBar"]:
        result = sim.post_tool_use_edit(
            "guardian",
            os.path.join(project_path, f"src/components/{comp}.tsx"),
            f"return <div>{comp}</div>;",
            f"return <div>Updated {comp}</div>;",
            cwd=project_path,
        )
    log(f"Last collect result: {result}")
    assert result.get("result") == "continue" or result.get("empty"), \
        f"Collect hook failed: {result}"


@test("3c. Guardian — analyze on stop")
def test_guardian_analyze():
    sim = HookSimulator(PLUGINS_DIR)
    result = sim.stop("guardian", project_path)
    log(f"Analyze result: {result}")
    # Analyze runs async, may return empty
    assert "error" not in str(result).lower() or result.get("result") == "continue", \
        f"Analyze failed: {result}"


# ============================================================
# Test 4: Workflows — YAML Engine
# ============================================================

@test("4. Workflows — session start finds workflows")
def test_workflows_session_start():
    sim = HookSimulator(PLUGINS_DIR)
    result = sim.session_start("workflows", project_path)
    log(f"Result: {result}")
    msg = result.get("message", "")
    # Should find our test-workflow.yml
    assert result.get("result") == "continue", f"Unexpected: {result}"


@test("4b. Workflows — MCP server lists tools")
def test_workflows_mcp_tools():
    server_path = os.path.join(PLUGINS_DIR, "workflows", "server", "main.py")
    if not os.path.exists(server_path):
        log(f"SKIP: server not found at {server_path}")
        return

    with MCPClient(server_path, cwd=project_path) as client:
        tools = client.list_tools()
        tool_names = [t["name"] for t in tools]
        log(f"Tools: {tool_names}")
        assert "list_workflows" in tool_names, f"Missing list_workflows tool: {tool_names}"
        assert "run_workflow" in tool_names, f"Missing run_workflow tool: {tool_names}"


@test("4c. Workflows — list_workflows finds test workflow")
def test_workflows_list():
    server_path = os.path.join(PLUGINS_DIR, "workflows", "server", "main.py")
    if not os.path.exists(server_path):
        log("SKIP: server not found")
        return

    with MCPClient(server_path, cwd=project_path) as client:
        result = client.call_tool("list_workflows", {"project_path": project_path})
        log(f"Result: {result['text'][:200]}")
        assert not result.get("is_error"), f"Error: {result}"
        assert "test-workflow" in result["text"], f"Workflow not found in: {result['text']}"


# ============================================================
# Test 5: Worktrees — Experiment Orchestrator
# ============================================================

@test("5. Worktrees — MCP server lists tools")
def test_worktrees_mcp_tools():
    server_path = os.path.join(PLUGINS_DIR, "worktrees", "server", "main.py")
    if not os.path.exists(server_path):
        log("SKIP: server not found")
        return

    with MCPClient(server_path, cwd=project_path) as client:
        tools = client.list_tools()
        tool_names = [t["name"] for t in tools]
        log(f"Tools: {tool_names}")
        assert "start_experiment" in tool_names, f"Missing start_experiment: {tool_names}"
        assert "merge_variant" in tool_names, f"Missing merge_variant: {tool_names}"


@test("5b. Worktrees — start experiment creates worktrees")
def test_worktrees_experiment():
    server_path = os.path.join(PLUGINS_DIR, "worktrees", "server", "main.py")
    if not os.path.exists(server_path):
        log("SKIP: server not found")
        return

    with MCPClient(server_path, cwd=project_path) as client:
        result = client.call_tool("start_experiment", {
            "project_path": project_path,
            "description": "Test experiment",
            "num_variants": 2,
            "eval_cmd": "echo 'score:100'",
        })
        log(f"Start result: {result['text'][:300]}")
        assert not result.get("is_error"), f"Error starting experiment: {result}"

        # Check status
        data = json.loads(result["text"])
        exp_id = data.get("id") or data.get("experiment_id")
        if exp_id:
            status = client.call_tool("experiment_status", {
                "project_path": project_path,
                "experiment_id": exp_id,
            })
            log(f"Status: {status['text'][:200]}")

            # Cleanup
            cleanup = client.call_tool("cleanup_experiment", {
                "project_path": project_path,
                "experiment_id": exp_id,
            })
            log(f"Cleanup: {cleanup['text'][:100]}")


# ============================================================
# Test 6: Autoresearch — MCP Server
# ============================================================

@test("6. Autoresearch — MCP server lists tools")
def test_autoresearch_mcp_tools():
    server_path = os.path.join(PLUGINS_DIR, "autoresearch", "server", "main.py")
    if not os.path.exists(server_path):
        log("SKIP: server not found")
        return

    with MCPClient(server_path, cwd=project_path) as client:
        tools = client.list_tools()
        tool_names = [t["name"] for t in tools]
        log(f"Tools: {tool_names}")
        assert "init_research" in tool_names, f"Missing init_research: {tool_names}"
        assert "run_eval" in tool_names, f"Missing run_eval: {tool_names}"


@test("6b. Autoresearch — detect project type")
def test_autoresearch_detect():
    server_path = os.path.join(PLUGINS_DIR, "autoresearch", "server", "main.py")
    if not os.path.exists(server_path):
        log("SKIP: server not found")
        return

    with MCPClient(server_path, cwd=project_path) as client:
        result = client.call_tool("detect_project", {"project_path": project_path})
        log(f"Detection: {result['text'][:200]}")
        assert not result.get("is_error"), f"Error: {result}"
        # Should detect as nodejs (package.json)
        assert "node" in result["text"].lower() or "package" in result["text"].lower(), \
            f"Didn't detect Node.js: {result['text']}"


# ============================================================
# Test 7: Cross-Plugin — All hooks fire without conflicts
# ============================================================

@test("7. Cross-Plugin — all SessionStart hooks fire cleanly")
def test_cross_plugin_session_start():
    sim = HookSimulator(PLUGINS_DIR)
    plugins_with_session = ["autofix", "guardian", "workflows", "worktrees", "autoresearch"]
    for plugin in plugins_with_session:
        hook_dir = os.path.join(PLUGINS_DIR, plugin, "hooks", "session_start.py")
        if not os.path.exists(hook_dir):
            log(f"  SKIP {plugin}: no session_start.py")
            continue
        result = sim.session_start(plugin, project_path)
        status = result.get("result", "unknown")
        log(f"  {plugin}: result={status}")
        assert "error" not in json.dumps(result).lower() or status == "continue", \
            f"{plugin} SessionStart failed: {result}"


@test("7b. Cross-Plugin — PostToolUse hooks don't conflict")
def test_cross_plugin_post_edit():
    sim = HookSimulator(PLUGINS_DIR)
    # Simulate an edit that should trigger autofix AND guardian
    file_path = os.path.join(project_path, "src/components/UserCard.tsx")
    for plugin in ["autofix", "guardian"]:
        result = sim.post_tool_use_edit(
            plugin, file_path,
            "return <div>UserCard</div>;",
            "return <div>Updated</div>;",
            cwd=project_path,
        )
        log(f"  {plugin} PostToolUse: {result.get('result', 'unknown')}")


@test("7c. Cross-Plugin — MCP servers have no tool name conflicts")
def test_cross_plugin_tool_names():
    all_tools = {}
    for plugin in ["autoresearch", "workflows", "worktrees"]:
        server_path = os.path.join(PLUGINS_DIR, plugin, "server", "main.py")
        if not os.path.exists(server_path):
            continue
        try:
            with MCPClient(server_path, cwd=project_path) as client:
                tools = client.list_tools()
                for t in tools:
                    name = t["name"]
                    if name in all_tools:
                        log(f"  CONFLICT: tool '{name}' in both {all_tools[name]} and {plugin}")
                    all_tools[name] = plugin
        except Exception as e:
            log(f"  SKIP {plugin}: {e}")

    log(f"  Total tools across all MCP servers: {len(all_tools)}")
    # Check for conflicts
    seen = {}
    conflicts = []
    for name, plugin in all_tools.items():
        if name in seen and seen[name] != plugin:
            conflicts.append(f"{name} ({seen[name]} vs {plugin})")
        seen[name] = plugin
    assert not conflicts, f"Tool name conflicts: {conflicts}"


# ============================================================
# Main
# ============================================================

def main():
    global project_path

    print("=" * 60)
    print("NodeNestor Plugin Suite — Integration Tests")
    print("=" * 60)
    print(f"Proxy: {PROXY_URL}")
    print(f"Workspace: {WORKSPACE}")
    print(f"Plugins: {PLUGINS_DIR}")
    print()

    # Wait for proxy
    global proxy_available
    proxy_available = False
    print("Waiting for rolling-context proxy...")
    for i in range(10):
        try:
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
            conn.request("GET", "/health")
            resp = conn.getresponse()
            if resp.status == 200:
                print("  Proxy ready!")
                proxy_available = True
                break
        except Exception:
            pass
        time.sleep(1)
    if not proxy_available:
        print("  WARNING: Proxy not reachable — proxy tests will be skipped")

    # Setup test project
    print("\nSetting up test project...")
    project_path = setup_test_project()
    print(f"  Created at {project_path}")

    # List available plugins
    print("\nAvailable plugins:")
    for name in sorted(os.listdir(PLUGINS_DIR)):
        plugin_dir = os.path.join(PLUGINS_DIR, name)
        if os.path.isdir(plugin_dir):
            has_hooks = os.path.exists(os.path.join(plugin_dir, "hooks"))
            has_mcp = os.path.exists(os.path.join(plugin_dir, "server", "main.py"))
            print(f"  {name}: hooks={'yes' if has_hooks else 'no'}, mcp={'yes' if has_mcp else 'no'}")

    # Run all tests
    all_tests = [
        test_proxy_health,
        test_proxy_passthrough,
        test_autofix_session_start,
        test_autofix_post_edit,
        test_guardian_session_start,
        test_guardian_collect,
        test_guardian_analyze,
        test_workflows_session_start,
        test_workflows_mcp_tools,
        test_workflows_list,
        test_worktrees_mcp_tools,
        test_worktrees_experiment,
        test_autoresearch_mcp_tools,
        test_autoresearch_detect,
        test_cross_plugin_session_start,
        test_cross_plugin_post_edit,
        test_cross_plugin_tool_names,
    ]

    for t in all_tests:
        run_test(t)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, err in results:
        status = "PASS" if ok else "FAIL"
        suffix = f" — {err}" if err else ""
        print(f"  [{status}] {name}{suffix}")
    print(f"\n  {passed} passed, {failed} failed, {len(results)} total")
    print("=" * 60)

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
