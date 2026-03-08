"""
Minimal MCP client for testing MCP servers.

Talks JSON-RPC 2.0 over subprocess stdin/stdout — same as Claude Code does.
"""

import json
import os
import subprocess
import sys
import threading


class MCPClient:
    """Test client for MCP servers running as subprocesses."""

    def __init__(self, server_script, cwd=None, env=None):
        self.server_script = server_script
        self.cwd = cwd
        self.env = env or os.environ.copy()
        self.process = None
        self._request_id = 0
        self._lock = threading.Lock()

    def start(self):
        """Start the MCP server subprocess."""
        self.process = subprocess.Popen(
            [sys.executable, self.server_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=self.cwd,
            env=self.env,
        )

    def stop(self):
        """Stop the server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _send(self, method, params=None):
        """Send a JSON-RPC request and read response."""
        with self._lock:
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
            }
            if params:
                request["params"] = params

            line = json.dumps(request) + "\n"
            self.process.stdin.write(line)
            self.process.stdin.flush()

            # Read response line
            resp_line = self.process.stdout.readline()
            if not resp_line:
                return {"error": "No response from server"}

            try:
                return json.loads(resp_line)
            except json.JSONDecodeError:
                return {"error": f"Invalid JSON: {resp_line}"}

    def initialize(self):
        """Send MCP initialize handshake."""
        resp = self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        })
        # Send initialized notification (no response expected)
        notif = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }) + "\n"
        self.process.stdin.write(notif)
        self.process.stdin.flush()
        return resp

    def list_tools(self):
        """Get available tools."""
        resp = self._send("tools/list")
        if "result" in resp:
            return resp["result"].get("tools", [])
        return []

    def call_tool(self, name, arguments=None):
        """Call a tool and return the result."""
        resp = self._send("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        if "result" in resp:
            content = resp["result"].get("content", [])
            is_error = resp["result"].get("isError", False)
            text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
            return {"text": text, "is_error": is_error, "raw": content}
        return {"error": resp.get("error", "Unknown error")}

    def __enter__(self):
        self.start()
        self.initialize()
        return self

    def __exit__(self, *args):
        self.stop()
