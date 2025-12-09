"""Shell operation tools for agents."""

import asyncio
import shlex
from typing import Optional

from .base import Tool, ToolResult, ToolParameter, ToolResultStatus


# Whitelist of allowed command prefixes
ALLOWED_COMMANDS = {
    # Python
    "pytest", "python", "pip", "ruff", "black", "mypy", "pylint", "flake8",
    # Node.js
    "npm", "npx", "node", "yarn", "pnpm", "eslint", "prettier", "tsc", "jest", "vitest",
    # Build tools
    "make", "cargo", "go", "gradle", "mvn",
    # Version control (for rollback operations)
    "git",
    # General utilities
    "cat", "head", "tail", "grep", "find", "ls", "echo", "pwd", "wc",
    "sort", "uniq", "diff", "tree", "which", "env",
}

# Blacklist of dangerous commands/patterns
BLOCKED_PATTERNS = {
    "rm -rf /", "rm -rf ~", "rm -rf *",
    "sudo", "su ",
    "> /dev/", "| /dev/",
    "mkfs", "dd if=",
    "chmod 777", "chmod -R 777",
    ":(){", "fork",  # Fork bombs
    "curl | sh", "wget | sh", "curl | bash", "wget | bash",
    "eval", "exec",
    ">/etc/", ">> /etc/",
    "shutdown", "reboot", "halt", "poweroff",
}


def is_command_allowed(command: str) -> tuple[bool, Optional[str]]:
    """
    Check if a command is allowed to run.
    
    Returns:
        Tuple of (allowed, reason_if_blocked)
    """
    command_lower = command.lower().strip()
    
    # Check against blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if pattern in command_lower:
            return False, f"Blocked pattern detected: '{pattern}'"
    
    # Extract base command (first word)
    try:
        parts = shlex.split(command)
        if not parts:
            return False, "Empty command"
        base_cmd = parts[0].split("/")[-1]  # Handle full paths
    except ValueError:
        return False, "Invalid command syntax"
    
    # Check whitelist
    if base_cmd not in ALLOWED_COMMANDS:
        return False, f"Command '{base_cmd}' is not in the allowed list. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"
    
    return True, None


class RunCommandTool(Tool):
    """Run shell commands safely."""
    
    name = "run_command"
    description = """Führt Shell-Befehle aus (z.B. Tests, Linter, Build).
    
Erlaubte Befehle: pytest, npm, pip, ruff, eslint, make, etc.
Nicht erlaubt: rm -rf, sudo, etc."""
    
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="Der auszuführende Befehl (z.B. 'pytest tests/', 'npm test')",
        ),
        ToolParameter(
            name="cwd",
            type="string",
            description="Arbeitsverzeichnis für den Befehl (relativ zum Workspace)",
            required=False,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Timeout in Sekunden (default: 60, max: 300)",
            required=False,
            default=60,
        ),
    ]

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> ToolResult:
        """Execute a shell command safely."""
        # Validate command
        allowed, reason = is_command_allowed(command)
        if not allowed:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Befehl nicht erlaubt: {reason}",
            )
        
        # Enforce timeout limits
        timeout = min(max(timeout, 1), 300)  # 1-300 seconds
        
        # Determine working directory
        if self.workspace_path:
            if cwd:
                work_dir = f"{self.workspace_path}/{cwd}"
            else:
                work_dir = self.workspace_path
        else:
            work_dir = cwd or "."
        
        try:
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Befehl abgebrochen nach {timeout}s Timeout",
                    metadata={"command": command, "timeout": True},
                )
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            exit_code = process.returncode
            
            # Truncate output if too long
            max_output = 10000
            if len(stdout_str) > max_output:
                stdout_str = stdout_str[:max_output] + "\n... (truncated)"
            if len(stderr_str) > max_output:
                stderr_str = stderr_str[:max_output] + "\n... (truncated)"
            
            # Format output
            output_parts = []
            if stdout_str.strip():
                output_parts.append(f"STDOUT:\n{stdout_str.strip()}")
            if stderr_str.strip():
                output_parts.append(f"STDERR:\n{stderr_str.strip()}")
            output_parts.append(f"\nExit Code: {exit_code}")
            
            output = "\n\n".join(output_parts)
            
            # Determine status based on exit code
            if exit_code == 0:
                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    output=output,
                    metadata={
                        "command": command,
                        "exit_code": exit_code,
                        "cwd": work_dir,
                    },
                )
            else:
                # Command ran but returned non-zero exit code
                return ToolResult(
                    status=ToolResultStatus.PARTIAL,
                    output=output,
                    error=f"Befehl beendet mit Exit-Code {exit_code}" + (f": {stderr_str[:200]}" if stderr_str.strip() else ""),
                    metadata={
                        "command": command,
                        "exit_code": exit_code,
                        "cwd": work_dir,
                    },
                )
            
        except FileNotFoundError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Arbeitsverzeichnis nicht gefunden: {work_dir}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Fehler bei Befehlsausführung: {str(e)}",
            )
