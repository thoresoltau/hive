
import pytest
import asyncio
from tools.shell_ops import RunCommandTool, ToolResultStatus

@pytest.mark.asyncio
async def test_input_fails_immediately():
    """Test that a command asking for input fails immediately (EOFError) due to /dev/null stdin."""
    tool = RunCommandTool()
    
    # Python's input() raises EOFError when stdin is closed/empty
    cmd = "python3 -c \"import sys; \ntry:\n    input('Prompt: ')\nexcept EOFError:\n    print('EOF caught')\n    sys.exit(0)\""
    
    # Should be near instant, definitely under 2 seconds if working
    result = await tool.execute(command=cmd, timeout=5)
    
    msg = f"Output: {result.output}\nError: {result.error}"
    assert result.status == ToolResultStatus.SUCCESS, msg
    assert "EOF caught" in str(result.output)

@pytest.mark.asyncio
async def test_interactive_input_errors():
    """Test that a raw input() call errors out instead of hanging."""
    tool = RunCommandTool()
    
    # Without catch blocks, input() -> EOFError -> Exit 1
    cmd = "python3 -c \"input()\""
    
    result = await tool.execute(command=cmd, timeout=5)
    
    # Should fail (exit code 1)
    assert result.status == ToolResultStatus.PARTIAL
    assert result.metadata["exit_code"] != 0
    assert "EOFError" in str(result.output) or "EOFError" in str(result.error)

@pytest.mark.asyncio
async def test_env_vars_set():
    """Test that CI environment variables are injected."""
    tool = RunCommandTool()
    
    cmd = "env"
    result = await tool.execute(command=cmd)
    
    assert result.status == ToolResultStatus.SUCCESS
    output = str(result.output)
    assert "CI=true" in output
    assert "NPM_CONFIG_YES=true" in output
    assert "DEBIAN_FRONTEND=noninteractive" in output

@pytest.mark.asyncio
async def test_timeout_still_works():
    """Test that timeout mechanism still functions correctly."""
    tool = RunCommandTool()
    
    # Sleep 3s, timeout 1s
    cmd = "sleep 3"
    result = await tool.execute(command=cmd, timeout=1)
    
    assert result.status == ToolResultStatus.ERROR
    assert "Timeout" in str(result.error)
