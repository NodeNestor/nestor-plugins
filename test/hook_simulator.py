"""
Simulate Claude Code hook events by calling plugin hook scripts directly.

Each hook script reads JSON from stdin and writes JSON to stdout.
This module simulates the exact same interface Claude Code uses.
"""

import json
import os
import subprocess
import sys
import time


class HookSimulator:
    """Simulate Claude Code hook events against plugin scripts."""

    def __init__(self, plugins_dir="/plugins"):
        self.plugins_dir = plugins_dir
        self.session_id = f"test-{int(time.time())}"

    def _base_event(self, cwd="/workspace/test-project", hook_event=None):
        """Base event fields that all hooks receive."""
        return {
            "session_id": self.session_id,
            "transcript_path": f"/tmp/transcript-{self.session_id}.jsonl",
            "cwd": cwd,
            "permission_mode": "default",
            "hook_event_name": hook_event or "Unknown",
        }

    def fire_hook(self, plugin_name, script_name, event_data, timeout=15):
        """
        Fire a hook by running the plugin's Python script with event JSON on stdin.
        Returns parsed JSON output or None.
        """
        plugin_dir = os.path.join(self.plugins_dir, plugin_name)
        script_path = os.path.join(plugin_dir, "hooks", script_name)

        if not os.path.exists(script_path):
            return {"error": f"Script not found: {script_path}"}

        # Add CLAUDE_PLUGIN_ROOT to env
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = plugin_dir

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                input=json.dumps(event_data),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=event_data.get("cwd", "/workspace"),
                env=env,
            )

            stdout = result.stdout.strip()
            if stdout:
                try:
                    return json.loads(stdout)
                except json.JSONDecodeError:
                    return {"raw_output": stdout, "stderr": result.stderr}
            return {"empty": True, "stderr": result.stderr, "returncode": result.returncode}

        except subprocess.TimeoutExpired:
            return {"error": "timeout", "script": script_name}
        except Exception as e:
            return {"error": str(e)}

    # --- High-level event simulators ---

    def session_start(self, plugin_name, cwd="/workspace/test-project"):
        """Simulate SessionStart event."""
        event = {**self._base_event(cwd, "SessionStart"), "source": "startup"}
        return self.fire_hook(plugin_name, "session_start.py", event)

    def post_tool_use_edit(self, plugin_name, file_path, old_string, new_string,
                           cwd="/workspace/test-project"):
        """Simulate PostToolUse for an Edit tool."""
        event = {
            **self._base_event(cwd, "PostToolUse"),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
            "tool_response": {"success": True},
        }
        return self.fire_hook(plugin_name, self._post_edit_script(plugin_name), event)

    def post_tool_use_write(self, plugin_name, file_path, content,
                            cwd="/workspace/test-project"):
        """Simulate PostToolUse for a Write tool."""
        event = {
            **self._base_event(cwd, "PostToolUse"),
            "tool_name": "Write",
            "tool_input": {
                "file_path": file_path,
                "content": content,
            },
            "tool_response": {"success": True},
        }
        return self.fire_hook(plugin_name, self._post_edit_script(plugin_name), event)

    def post_tool_use_bash(self, plugin_name, command, output="",
                           cwd="/workspace/test-project"):
        """Simulate PostToolUse for a Bash tool."""
        event = {
            **self._base_event(cwd, "PostToolUse"),
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": {"output": output},
        }
        script = "collect_bash.py" if plugin_name == "guardian" else "trigger.py"
        return self.fire_hook(plugin_name, script, event)

    def pre_tool_use_edit(self, plugin_name, file_path, old_string, new_string,
                          cwd="/workspace/test-project"):
        """Simulate PreToolUse for an Edit tool."""
        event = {
            **self._base_event(cwd, "PreToolUse"),
            "tool_name": "Edit",
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
        }
        return self.fire_hook(plugin_name, "enforce.py", event)

    def stop(self, plugin_name, cwd="/workspace/test-project"):
        """Simulate Stop event."""
        event = {
            **self._base_event(cwd, "Stop"),
            "stop_hook_active": True,
            "last_assistant_message": "Done with the task.",
        }
        script = "analyze.py" if plugin_name == "guardian" else "on_stop.py"
        if plugin_name == "workflows":
            script = "trigger.py"
        return self.fire_hook(plugin_name, script, event)

    def _post_edit_script(self, plugin_name):
        """Get the right PostToolUse script name per plugin."""
        scripts = {
            "autofix": "post_edit.py",
            "guardian": "collect_edit.py",
            "workflows": "trigger.py",
        }
        return scripts.get(plugin_name, "post_edit.py")
