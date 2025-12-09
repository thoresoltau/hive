"""Tests for shell operation tools."""

import pytest
from pathlib import Path

from tools.shell_ops import RunCommandTool, is_command_allowed
from tools.base import ToolResultStatus


class TestCommandValidation:
    """Tests for command validation logic."""

    def test_allowed_command(self):
        """Should allow whitelisted commands."""
        allowed, reason = is_command_allowed("pytest tests/")
        assert allowed
        assert reason is None

    def test_allowed_npm_command(self):
        """Should allow npm commands."""
        allowed, reason = is_command_allowed("npm test")
        assert allowed

    def test_blocked_rm_rf(self):
        """Should block dangerous rm -rf."""
        allowed, reason = is_command_allowed("rm -rf /")
        assert not allowed
        assert "Blocked pattern" in reason

    def test_blocked_sudo(self):
        """Should block sudo commands."""
        allowed, reason = is_command_allowed("sudo apt install something")
        assert not allowed
        assert "Blocked pattern" in reason

    def test_blocked_unknown_command(self):
        """Should block non-whitelisted commands."""
        allowed, reason = is_command_allowed("dangerous_script.sh")
        assert not allowed
        assert "not in the allowed list" in reason

    def test_allowed_command_with_path(self):
        """Should allow commands even with full path."""
        allowed, reason = is_command_allowed("/usr/bin/pytest tests/")
        assert allowed


class TestRunCommandTool:
    """Tests for RunCommandTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return RunCommandTool(workspace_path=str(temp_dir))

    async def test_run_simple_command(self, tool):
        """Should run a simple allowed command."""
        result = await tool.execute(command="echo hello")
        
        assert result.success
        assert "hello" in result.output
        assert result.metadata["exit_code"] == 0

    async def test_run_command_with_exit_code(self, tool, temp_dir):
        """Should capture non-zero exit codes."""
        # Create a file to grep for non-existent content
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")
        
        result = await tool.execute(command="grep nonexistent test.txt")
        
        assert result.status == ToolResultStatus.PARTIAL
        assert result.metadata["exit_code"] == 1

    async def test_run_blocked_command(self, tool):
        """Should reject blocked commands."""
        result = await tool.execute(command="sudo ls")
        
        assert result.status == ToolResultStatus.ERROR
        assert "nicht erlaubt" in result.error.lower()

    async def test_run_unknown_command(self, tool):
        """Should reject unknown commands."""
        result = await tool.execute(command="unknown_cmd arg1")
        
        assert result.status == ToolResultStatus.ERROR
        assert "nicht erlaubt" in result.error.lower()

    async def test_run_with_cwd(self, tool, temp_dir):
        """Should run command in specified directory."""
        # Create a subdirectory with a file
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.txt"
        test_file.write_text("content")
        
        result = await tool.execute(
            command="ls",
            cwd="subdir",
        )
        
        assert result.success
        assert "test.txt" in result.output

    async def test_run_with_timeout(self, tool):
        """Should handle timeout properly."""
        # This should complete quickly, just testing the parameter works
        result = await tool.execute(
            command="echo fast",
            timeout=5,
        )
        
        assert result.success
        assert "fast" in result.output

    async def test_run_pytest_command(self, tool, temp_dir):
        """Should allow running pytest."""
        # Create a simple test file
        test_file = temp_dir / "test_simple.py"
        test_file.write_text("""
def test_pass():
    assert True
""")
        
        result = await tool.execute(command="pytest test_simple.py -v")
        
        assert result.success or result.status == ToolResultStatus.PARTIAL
        assert "test_pass" in result.output.lower() or "passed" in result.output.lower()
