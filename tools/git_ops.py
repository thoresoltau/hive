"""Git operation tools for agents."""

import asyncio
import os
from typing import Optional

from .base import Tool, ToolResult, ToolParameter, ToolResultStatus


async def run_git_command(
    args: list[str],
    cwd: str,
    timeout: float = 30.0,
    auto_init: bool = True,
) -> tuple[bool, str, str]:
    """
    Run a git command asynchronously.

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        success = process.returncode == 0
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()

        # Auto-initialize git if needed and retry once
        if not success and auto_init and "not a git repository" in stderr_str.lower():
            init_process = await asyncio.create_subprocess_exec(
                "git", "init",
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await init_process.communicate()
            return await run_git_command(args, cwd, timeout, auto_init=False)

        return success, stdout_str, stderr_str

    except asyncio.TimeoutError:
        return False, "", "Git command timed out"
    except FileNotFoundError:
        return False, "", "Git not found. Is git installed?"
    except Exception as e:
        return False, "", str(e)


class GitStatusTool(Tool):
    """Tool to check git repository status."""

    name = "git_status"
    description = "Shows the current git status of the repository (changed, new, deleted files)"

    parameters = [
        ToolParameter(
            name="short",
            type="boolean",
            description="Short output (only filenames with status codes)",
            required=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(self, short: bool = False) -> ToolResult:
        args = ["status"]
        if short:
            args.append("--short")

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr or "Git status failed",
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"status": stdout.strip()},
        )


class GitBranchTool(Tool):
    """Tool to manage git branches."""

    name = "git_branch"
    description = "Manages git branches: create, switch, list or delete"

    parameters = [
        ToolParameter(
            name="branch_name",
            type="string",
            description="Name of the branch",
            required=False,
        ),
        ToolParameter(
            name="action",
            type="string",
            description="Action: 'create', 'switch', 'list', 'delete'",
            required=False,
        ),
        ToolParameter(
            name="base_branch",
            type="string",
            description="Base branch for new branch (default: current branch)",
            required=False,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force delete even with unmerged changes",
            required=False,
            default=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        branch_name: str = "",
        action: str = "create",
        base_branch: Optional[str] = None,
        force: bool = False,
    ) -> ToolResult:
        if action == "list":
            success, stdout, stderr = await run_git_command(
                ["branch", "-a"],
                self.workspace_path,
            )

            if not success:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=stderr,
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output={"branches": stdout.strip()},
            )

        if not branch_name:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error="branch_name is required",
            )

        if action == "create":
            # Create and switch to new branch
            args = ["checkout", "-b", branch_name]
            if base_branch:
                args.append(base_branch)

            success, stdout, stderr = await run_git_command(args, self.workspace_path)

            if not success:
                # Branch might already exist, try just switching
                if "already exists" in stderr:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        output=None,
                        error=f"Branch '{branch_name}' already exists. Use action='switch' to switch.",
                    )
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=stderr,
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output={
                    "action": "created",
                    "branch": branch_name,
                    "message": f"Branch '{branch_name}' created and activated",
                },
            )

        elif action == "switch":
            success, stdout, stderr = await run_git_command(
                ["checkout", branch_name],
                self.workspace_path,
            )

            if not success:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=stderr,
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output={
                    "action": "switched",
                    "branch": branch_name,
                    "message": f"Switched to branch '{branch_name}'",
                },
            )

        elif action == "delete":
            # Safety: Don't delete protected branches
            protected_branches = {"main", "master", "develop", "production"}
            if branch_name.lower() in protected_branches:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Branch '{branch_name}' is protected and cannot be deleted.",
                )

            # Check if we're on the branch to delete
            success, current, _ = await run_git_command(
                ["branch", "--show-current"],
                self.workspace_path,
            )
            if success and current.strip() == branch_name:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Cannot delete current branch '{branch_name}'. Switch to another branch first.",
                )

            # Delete branch
            delete_flag = "-D" if force else "-d"
            success, stdout, stderr = await run_git_command(
                ["branch", delete_flag, branch_name],
                self.workspace_path,
            )

            if not success:
                if "not fully merged" in stderr:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        output=None,
                        error=f"Branch '{branch_name}' has unmerged changes. Use force=true to delete.",
                    )
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=stderr,
                )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output={
                    "action": "deleted",
                    "branch": branch_name,
                    "message": f"Branch '{branch_name}' deleted",
                },
            )

        return ToolResult(
            status=ToolResultStatus.ERROR,
            output=None,
            error=f"Unknown action: {action}. Use 'create', 'switch', 'delete', or 'list'.",
        )


class GitCommitTool(Tool):
    """Tool to commit changes."""

    name = "git_commit"
    description = "Commit staged changes. Optionally, files can be staged beforehand."

    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="Commit message (short and descriptive)",
            required=True,
        ),
        ToolParameter(
            name="files",
            type="array",
            description="List of files to be staged (optional, default: all changed)",
            required=False,
        ),
        ToolParameter(
            name="ticket_id",
            type="string",
            description="Ticket ID for the commit message (e.g. 'HIVE-001')",
            required=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        message: str,
        files: Optional[list[str]] = None,
        ticket_id: Optional[str] = None,
    ) -> ToolResult:
        if not message:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error="Commit-Message is required",
            )

        # Stage files
        if files:
            for file in files:
                success, _, stderr = await run_git_command(
                    ["add", file],
                    self.workspace_path,
                )
                if not success:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        output=None,
                        error=f"Error staging '{file}': {stderr}",
                    )
        else:
            # Stage all changes
            success, _, stderr = await run_git_command(
                ["add", "-A"],
                self.workspace_path,
            )
            if not success:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Error staging: {stderr}",
                )

        # Format commit message with ticket ID
        if ticket_id:
            full_message = f"[{ticket_id}] {message}"
        else:
            full_message = message

        # Commit
        success, stdout, stderr = await run_git_command(
            ["commit", "-m", full_message],
            self.workspace_path,
        )

        if not success:
            if "nothing to commit" in stderr or "nothing to commit" in stdout:
                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    output={
                        "committed": False,
                        "message": "No changes to commit",
                    },
                )
            error_msg = stderr.strip() if stderr.strip() else stdout.strip() if stdout.strip() else "Git commit failed (unknown error)"
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=error_msg,
            )

        # Get commit hash
        success, commit_hash, _ = await run_git_command(
            ["rev-parse", "--short", "HEAD"],
            self.workspace_path,
        )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={
                "committed": True,
                "hash": commit_hash.strip() if success else "unknown",
                "message": full_message,
            },
        )


class GitDiffTool(Tool):
    """Tool to show git diff."""

    name = "git_diff"
    description = "Shows changes (diff) for files or the entire repository"

    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Optional path to a specific file",
            required=False,
        ),
        ToolParameter(
            name="staged",
            type="boolean",
            description="Show only staged changes",
            required=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        file_path: Optional[str] = None,
        staged: bool = False,
    ) -> ToolResult:
        if not staged:
            if file_path:
                full_path = os.path.join(self.workspace_path, file_path)
                if os.path.exists(full_path):
                    await run_git_command(["add", "-N", file_path], self.workspace_path)
            else:
                await run_git_command(["add", "-N", "."], self.workspace_path)

        args = ["diff"]

        if staged:
            args.append("--staged")

        if file_path:
            full_path = os.path.join(self.workspace_path, file_path)
            if not os.path.exists(full_path):
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"File not found: {file_path}",
                )
            args.append(file_path)

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr,
            )

        if not stdout.strip():
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output={"diff": "No changes"},
            )

        # Truncate if too long
        max_length = 5000
        diff_output = stdout
        if len(diff_output) > max_length:
            diff_output = diff_output[:max_length] + "\n... (truncated)"

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"diff": diff_output},
        )


class GitLogTool(Tool):
    """Tool to show git log."""

    name = "git_log"
    description = "Shows the commit history"

    parameters = [
        ToolParameter(
            name="count",
            type="integer",
            description="Number of commits to display (default: 10)",
            required=False,
        ),
        ToolParameter(
            name="oneline",
            type="boolean",
            description="Compact display (one line per commit)",
            required=False,
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="Show only commits for this file",
            required=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        count: int = 10,
        oneline: bool = True,
        file_path: Optional[str] = None,
    ) -> ToolResult:
        args = ["log", f"-{count}"]

        if oneline:
            args.append("--oneline")
        else:
            args.extend(["--pretty=format:%h - %s (%ci) <%an>"])

        if file_path:
            args.extend(["--", file_path])

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr,
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"log": stdout.strip() or "No commits found"},
        )


class GitCurrentBranchTool(Tool):
    """Tool to get current branch name."""

    name = "git_current_branch"
    description = "Shows the name of the current branch"

    parameters = []

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(self) -> ToolResult:
        success, stdout, stderr = await run_git_command(
            ["branch", "--show-current"],
            self.workspace_path,
        )

        if not success:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr,
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={"branch": stdout.strip()},
        )


class GitPushTool(Tool):
    """Tool to push commits to remote."""

    name = "git_push"
    description = "Pushes local commits to the remote repository"

    parameters = [
        ToolParameter(
            name="remote",
            type="string",
            description="Remote name (default: origin)",
            required=False,
            default="origin",
        ),
        ToolParameter(
            name="branch",
            type="string",
            description="Branch name (default: current branch)",
            required=False,
        ),
        ToolParameter(
            name="set_upstream",
            type="boolean",
            description="Sets upstream for new branch (-u flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force push (CAUTION: overwrites remote history)",
            required=False,
            default=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        set_upstream: bool = False,
        force: bool = False,
    ) -> ToolResult:
        args = ["push"]

        if set_upstream:
            args.append("-u")

        if force:
            args.append("--force")

        args.append(remote)

        if branch:
            args.append(branch)

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr or "Push failed",
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={
                "message": f"Successfully pushed to {remote}",
                "details": stdout.strip() or stderr.strip(),
            },
        )


class GitPullTool(Tool):
    """Tool to pull changes from remote."""

    name = "git_pull"
    description = "Fetches changes from the remote repository"

    parameters = [
        ToolParameter(
            name="remote",
            type="string",
            description="Remote name (default: origin)",
            required=False,
            default="origin",
        ),
        ToolParameter(
            name="branch",
            type="string",
            description="Branch name (optional)",
            required=False,
        ),
        ToolParameter(
            name="rebase",
            type="boolean",
            description="Rebase instead of merge",
            required=False,
            default=False,
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        rebase: bool = False,
    ) -> ToolResult:
        args = ["pull"]

        if rebase:
            args.append("--rebase")

        args.append(remote)

        if branch:
            args.append(branch)

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            if "conflict" in stderr.lower() or "conflict" in stdout.lower():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Merge conflicts during pull: {stderr or stdout}",
                )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr or "Pull failed",
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={
                "message": f"Successfully pulled from {remote}",
                "details": stdout.strip(),
            },
        )


class GitResetTool(Tool):
    """Tool to reset changes."""

    name = "git_reset"
    description = "Resets changes (soft/mixed/hard)"

    parameters = [
        ToolParameter(
            name="mode",
            type="string",
            description="Reset mode: 'soft' (keeps changes staged), 'mixed' (default, keeps changes unstaged), 'hard' (CAUTION: discards all changes)",
            required=False,
            default="mixed",
        ),
        ToolParameter(
            name="target",
            type="string",
            description="Target commit (default: HEAD)",
            required=False,
            default="HEAD",
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        mode: str = "mixed",
        target: str = "HEAD",
    ) -> ToolResult:
        valid_modes = {"soft", "mixed", "hard"}
        if mode not in valid_modes:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Invalid mode: {mode}. Allowed: {', '.join(valid_modes)}",
            )

        args = ["reset", f"--{mode}", target]

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr,
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={
                "mode": mode,
                "target": target,
                "message": f"Reset ({mode}) auf {target} performed",
            },
        )


class GitCheckoutFileTool(Tool):
    """Tool to checkout specific files."""

    name = "git_checkout_file"
    description = "Resets individual files to the state of a commit"

    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Path to file (relative to repository)",
            required=True,
        ),
        ToolParameter(
            name="ref",
            type="string",
            description="Commit/branch/tag reference (default: HEAD)",
            required=False,
            default="HEAD",
        ),
    ]

    def __init__(self, workspace_path: str):
        self.workspace_path = workspace_path

    async def execute(
        self,
        file_path: str,
        ref: str = "HEAD",
    ) -> ToolResult:
        args = ["checkout", ref, "--", file_path]

        success, stdout, stderr = await run_git_command(args, self.workspace_path)

        if not success:
            if "did not match any" in stderr:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Datei '{file_path}' does not exist in {ref}",
                )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr,
            )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={
                "file": file_path,
                "ref": ref,
                "message": f"Datei '{file_path}' auf Stand von {ref} zurückgesetzt",
            },
        )
