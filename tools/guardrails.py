"""
Guardrails for safe file operations.

Provides path validation, protected path detection, and audit logging.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# Protected paths that should never be modified/deleted
PROTECTED_PATHS = {
    # Version control
    ".git",
    ".gitignore",
    ".gitmodules",
    ".gitattributes",
    
    # Environment & Secrets
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    
    # Hive internal
    ".hive",
    
    # Package managers (lock files)
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "Gemfile.lock",
    "composer.lock",
    
    # Dependencies (directories)
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
    ".nox",
}

# Patterns for protected files (regex)
PROTECTED_PATTERNS = [
    r".*\.lock$",           # All lock files
    r".*-lock\.json$",      # npm style locks
    r".*-lock\.yaml$",      # pnpm style locks
    r"\.env\..*",           # All .env variants
]


class PathValidator:
    """Validates paths for safety."""
    
    def __init__(self, workspace_path: Optional[str] = None):
        """
        Initialize path validator.
        
        Args:
            workspace_path: Root workspace path (operations limited to this)
        """
        self.workspace_path = Path(workspace_path).resolve() if workspace_path else None
    
    def is_path_safe(self, path: str) -> tuple[bool, Optional[str]]:
        """
        Check if a path is safe (no traversal attacks).
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_safe, reason_if_unsafe)
        """
        # Check for path traversal attempts
        if ".." in path:
            return False, "Path traversal detected: '..' is not allowed"
        
        # Check for absolute paths when workspace is set
        if self.workspace_path and os.path.isabs(path):
            resolved = Path(path).resolve()
            if not self._is_within_workspace(resolved):
                return False, f"Absolute path outside workspace: {path}"
        
        # Resolve the full path
        if self.workspace_path:
            full_path = (self.workspace_path / path).resolve()
        else:
            full_path = Path(path).resolve()
        
        # Verify path stays within workspace
        if self.workspace_path and not self._is_within_workspace(full_path):
            return False, f"Path escapes workspace: {path}"
        
        # Check for symlink attacks
        if full_path.is_symlink():
            target = full_path.resolve()
            if self.workspace_path and not self._is_within_workspace(target):
                return False, f"Symlink target outside workspace: {path}"
        
        return True, None
    
    def _is_within_workspace(self, path: Path) -> bool:
        """Check if path is within workspace."""
        if not self.workspace_path:
            return True
        try:
            path.relative_to(self.workspace_path)
            return True
        except ValueError:
            return False
    
    def is_protected(self, path: str) -> tuple[bool, Optional[str]]:
        """
        Check if a path is protected from modification.
        
        Args:
            path: Path to check
            
        Returns:
            Tuple of (is_protected, reason)
        """
        path_obj = Path(path)
        path_str = str(path)
        
        # Check exact matches
        for protected in PROTECTED_PATHS:
            # Check if path IS the protected item
            if path_obj.name == protected:
                return True, f"Protected path: {protected}"
            
            # Check if path is INSIDE a protected directory
            parts = path_obj.parts
            if protected in parts:
                return True, f"Path inside protected directory: {protected}"
        
        # Check patterns
        for pattern in PROTECTED_PATTERNS:
            if re.match(pattern, path_obj.name):
                return True, f"Matches protected pattern: {pattern}"
        
        return False, None
    
    def validate_for_write(self, path: str) -> tuple[bool, Optional[str]]:
        """
        Validate path for write operation.
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # First check path safety
        safe, reason = self.is_path_safe(path)
        if not safe:
            return False, reason
        
        # Check if target exists and is protected
        if self.workspace_path:
            full_path = self.workspace_path / path
        else:
            full_path = Path(path)
        
        if full_path.exists():
            protected, reason = self.is_protected(path)
            if protected:
                return False, f"Cannot overwrite protected file: {reason}"
        
        return True, None
    
    def validate_for_delete(self, path: str) -> tuple[bool, Optional[str]]:
        """
        Validate path for delete operation.
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # First check path safety
        safe, reason = self.is_path_safe(path)
        if not safe:
            return False, reason
        
        # Check if protected
        protected, reason = self.is_protected(path)
        if protected:
            return False, f"Cannot delete protected path: {reason}"
        
        return True, None
    
    def validate_for_move(
        self, source: str, destination: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate paths for move operation.
        
        Args:
            source: Source path
            destination: Destination path
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Validate source
        safe, reason = self.is_path_safe(source)
        if not safe:
            return False, f"Source: {reason}"
        
        protected, reason = self.is_protected(source)
        if protected:
            return False, f"Cannot move protected source: {reason}"
        
        # Validate destination
        safe, reason = self.is_path_safe(destination)
        if not safe:
            return False, f"Destination: {reason}"
        
        # Check if destination would overwrite protected
        if self.workspace_path:
            dest_path = self.workspace_path / destination
        else:
            dest_path = Path(destination)
        
        if dest_path.exists():
            protected, reason = self.is_protected(destination)
            if protected:
                return False, f"Cannot overwrite protected destination: {reason}"
        
        return True, None


class AuditLogger:
    """Logs all file operations for audit trail."""
    
    def __init__(
        self,
        workspace_path: Optional[str] = None,
        log_file: Optional[str] = None,
        max_size_mb: int = 10,
    ):
        """
        Initialize audit logger.
        
        Args:
            workspace_path: Root workspace path
            log_file: Path to audit log file
            max_size_mb: Max log size before rotation
        """
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        
        if log_file:
            self.log_file = Path(log_file)
        else:
            self.log_file = self.workspace_path / ".hive" / "audit.log"
        
        self.max_size = max_size_mb * 1024 * 1024
        self._ensure_log_dir()
    
    def _ensure_log_dir(self) -> None:
        """Ensure log directory exists."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        if not self.log_file.exists():
            return
        
        if self.log_file.stat().st_size > self.max_size:
            # Rotate existing backups
            for i in range(4, 0, -1):
                old = self.log_file.with_suffix(f".log.{i}")
                new = self.log_file.with_suffix(f".log.{i + 1}")
                if old.exists():
                    if i == 4:
                        old.unlink()  # Delete oldest
                    else:
                        old.rename(new)
            
            # Rotate current to .1
            self.log_file.rename(self.log_file.with_suffix(".log.1"))
    
    def log(
        self,
        agent: str,
        tool: str,
        action: str,
        path: str,
        result: str,
        details: Optional[str] = None,
    ) -> None:
        """
        Log an operation.
        
        Args:
            agent: Name of agent performing operation
            tool: Tool being used
            action: Action type (delete, write, edit, move)
            path: Target path
            result: Result (success, blocked, error)
            details: Optional additional details
        """
        self._rotate_if_needed()
        
        timestamp = datetime.now().isoformat()
        
        # Format: [timestamp] [agent] [tool] [action] [result] path | details
        log_line = f"[{timestamp}] [{agent}] [{tool}] [{action}] [{result}] {path}"
        if details:
            log_line += f" | {details}"
        log_line += "\n"
        
        with open(self.log_file, "a") as f:
            f.write(log_line)
    
    def get_recent(self, n: int = 20) -> list[str]:
        """
        Get recent log entries.
        
        Args:
            n: Number of entries to return
            
        Returns:
            List of log lines (most recent last)
        """
        if not self.log_file.exists():
            return []
        
        with open(self.log_file, "r") as f:
            lines = f.readlines()
        
        return lines[-n:]


# Singleton instances for easy access
_validator: Optional[PathValidator] = None
_audit_logger: Optional[AuditLogger] = None


def get_validator(workspace_path: Optional[str] = None) -> PathValidator:
    """Get or create path validator singleton."""
    global _validator
    if _validator is None or (workspace_path and str(_validator.workspace_path) != workspace_path):
        _validator = PathValidator(workspace_path)
    return _validator


def get_audit_logger(workspace_path: Optional[str] = None) -> AuditLogger:
    """Get or create audit logger singleton."""
    global _audit_logger
    if _audit_logger is None or workspace_path:
        _audit_logger = AuditLogger(workspace_path)
    return _audit_logger
