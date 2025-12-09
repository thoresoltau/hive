"""Git operation tools for agents."""

import asyncio
import os
from pathlib import Path
from typing import Optional

from .base import Tool, ToolResult, ToolParameter, ToolResultStatus


async def run_git_command(
    args: list[str],
    cwd: str,
    timeout: float = 30.0,
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
        return success, stdout.decode(), stderr.decode()
        
    except asyncio.TimeoutError:
        return False, "", "Git command timed out"
    except FileNotFoundError:
        return False, "", "Git not found. Is git installed?"
    except Exception as e:
        return False, "", str(e)


class GitStatusTool(Tool):
    """Tool to check git repository status."""
    
    name = "git_status"
    description = "Zeigt den aktuellen Git-Status des Repositories (geänderte, neue, gelöschte Dateien)"
    
    parameters = [
        ToolParameter(
            name="short",
            type="boolean",
            description="Kurze Ausgabe (nur Dateinamen mit Status-Codes)",
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
    description = "Verwaltet Git-Branches: erstellen, wechseln, auflisten oder löschen"
    
    parameters = [
        ToolParameter(
            name="branch_name",
            type="string",
            description="Name des Branches",
            required=False,
        ),
        ToolParameter(
            name="action",
            type="string",
            description="Aktion: 'create', 'switch', 'list', 'delete'",
            required=False,
        ),
        ToolParameter(
            name="base_branch",
            type="string",
            description="Basis-Branch für neuen Branch (default: aktueller Branch)",
            required=False,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force-Delete auch bei ungemergten Änderungen",
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
                error="branch_name ist erforderlich",
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
                        error=f"Branch '{branch_name}' existiert bereits. Nutze action='switch' zum Wechseln.",
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
                    "message": f"Branch '{branch_name}' erstellt und aktiviert",
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
                    "message": f"Gewechselt zu Branch '{branch_name}'",
                },
            )
        
        elif action == "delete":
            # Safety: Don't delete protected branches
            protected_branches = {"main", "master", "develop", "production"}
            if branch_name.lower() in protected_branches:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Branch '{branch_name}' ist geschützt und kann nicht gelöscht werden.",
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
                    error=f"Kann aktuellen Branch '{branch_name}' nicht löschen. Wechsle zuerst zu einem anderen Branch.",
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
                        error=f"Branch '{branch_name}' hat ungemergte Änderungen. Nutze force=true zum Löschen.",
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
                    "message": f"Branch '{branch_name}' gelöscht",
                },
            )
        
        return ToolResult(
            status=ToolResultStatus.ERROR,
            output=None,
            error=f"Unbekannte Aktion: {action}. Nutze 'create', 'switch', 'delete', oder 'list'.",
        )


class GitCommitTool(Tool):
    """Tool to commit changes."""
    
    name = "git_commit"
    description = "Staged Änderungen committen. Optional können Dateien vorher gestaged werden."
    
    parameters = [
        ToolParameter(
            name="message",
            type="string",
            description="Commit-Message (kurz und aussagekräftig)",
            required=True,
        ),
        ToolParameter(
            name="files",
            type="array",
            description="Liste von Dateien die gestaged werden sollen (optional, default: alle geänderten)",
            required=False,
        ),
        ToolParameter(
            name="ticket_id",
            type="string",
            description="Ticket-ID für die Commit-Message (z.B. 'HIVE-001')",
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
                error="Commit-Message ist erforderlich",
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
                        error=f"Fehler beim Stagen von '{file}': {stderr}",
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
                    error=f"Fehler beim Stagen: {stderr}",
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
                        "message": "Keine Änderungen zum Committen",
                    },
                )
            error_msg = stderr.strip() if stderr.strip() else stdout.strip() if stdout.strip() else "Git commit fehlgeschlagen (unbekannter Fehler)"
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
    description = "Zeigt Änderungen (Diff) für Dateien oder das gesamte Repository"
    
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Optionaler Pfad zu einer spezifischen Datei",
            required=False,
        ),
        ToolParameter(
            name="staged",
            type="boolean",
            description="Zeige nur gestagete Änderungen",
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
        args = ["diff"]
        
        if staged:
            args.append("--staged")
        
        if file_path:
            full_path = os.path.join(self.workspace_path, file_path)
            if not os.path.exists(full_path):
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Datei nicht gefunden: {file_path}",
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
                output={"diff": "Keine Änderungen"},
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
    description = "Zeigt die Commit-Historie"
    
    parameters = [
        ToolParameter(
            name="count",
            type="integer",
            description="Anzahl der anzuzeigenden Commits (default: 10)",
            required=False,
        ),
        ToolParameter(
            name="oneline",
            type="boolean",
            description="Kompakte Darstellung (eine Zeile pro Commit)",
            required=False,
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="Zeige nur Commits für diese Datei",
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
            output={"log": stdout.strip() or "Keine Commits gefunden"},
        )


class GitCurrentBranchTool(Tool):
    """Tool to get current branch name."""
    
    name = "git_current_branch"
    description = "Zeigt den Namen des aktuellen Branches"
    
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
    description = "Pusht lokale Commits zum Remote-Repository"
    
    parameters = [
        ToolParameter(
            name="remote",
            type="string",
            description="Remote Name (default: origin)",
            required=False,
            default="origin",
        ),
        ToolParameter(
            name="branch",
            type="string",
            description="Branch Name (default: aktueller Branch)",
            required=False,
        ),
        ToolParameter(
            name="set_upstream",
            type="boolean",
            description="Setzt Upstream für neuen Branch (-u flag)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="force",
            type="boolean",
            description="Force Push (VORSICHT: überschreibt Remote-History)",
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
                "message": f"Erfolgreich nach {remote} gepusht",
                "details": stdout.strip() or stderr.strip(),
            },
        )


class GitPullTool(Tool):
    """Tool to pull changes from remote."""
    
    name = "git_pull"
    description = "Holt Änderungen vom Remote-Repository"
    
    parameters = [
        ToolParameter(
            name="remote",
            type="string",
            description="Remote Name (default: origin)",
            required=False,
            default="origin",
        ),
        ToolParameter(
            name="branch",
            type="string",
            description="Branch Name (optional)",
            required=False,
        ),
        ToolParameter(
            name="rebase",
            type="boolean",
            description="Rebase statt Merge",
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
                    error=f"Merge-Konflikte beim Pull: {stderr or stdout}",
                )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=stderr or "Pull failed",
            )
        
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output={
                "message": f"Erfolgreich von {remote} gepullt",
                "details": stdout.strip(),
            },
        )


class GitResetTool(Tool):
    """Tool to reset changes."""
    
    name = "git_reset"
    description = "Setzt Änderungen zurück (soft/mixed/hard)"
    
    parameters = [
        ToolParameter(
            name="mode",
            type="string",
            description="Reset-Modus: 'soft' (behält Änderungen staged), 'mixed' (default, behält Änderungen unstaged), 'hard' (VORSICHT: verwirft alle Änderungen)",
            required=False,
            default="mixed",
        ),
        ToolParameter(
            name="target",
            type="string",
            description="Ziel-Commit (default: HEAD)",
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
                error=f"Ungültiger Modus: {mode}. Erlaubt: {', '.join(valid_modes)}",
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
                "message": f"Reset ({mode}) auf {target} durchgeführt",
            },
        )


class GitCheckoutFileTool(Tool):
    """Tool to checkout specific files."""
    
    name = "git_checkout_file"
    description = "Setzt einzelne Dateien auf den Stand eines Commits zurück"
    
    parameters = [
        ToolParameter(
            name="file_path",
            type="string",
            description="Pfad zur Datei (relativ zum Repository)",
            required=True,
        ),
        ToolParameter(
            name="ref",
            type="string",
            description="Commit/Branch/Tag Referenz (default: HEAD)",
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
                    error=f"Datei '{file_path}' existiert nicht in {ref}",
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
