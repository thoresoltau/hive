"""Tests for guardrails module."""

import tempfile
from pathlib import Path

import pytest

from tools.guardrails import (
    PathValidator,
    AuditLogger,
    PROTECTED_PATHS,
    PROTECTED_PATTERNS,
)


class TestPathValidator:
    """Tests for PathValidator."""
    
    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        validator = PathValidator("/workspace")
        
        # Direct traversal
        safe, reason = validator.is_path_safe("../etc/passwd")
        assert not safe
        assert "traversal" in reason.lower()
        
        # Nested traversal
        safe, reason = validator.is_path_safe("foo/../../bar")
        assert not safe
        assert "traversal" in reason.lower()
        
        # Hidden traversal
        safe, reason = validator.is_path_safe("foo/../../../etc/passwd")
        assert not safe
    
    def test_normal_paths_allowed(self):
        """Test that normal paths are allowed."""
        validator = PathValidator("/workspace")
        
        safe, reason = validator.is_path_safe("src/main.py")
        assert safe
        assert reason is None
        
        safe, reason = validator.is_path_safe("tests/test_foo.py")
        assert safe
        
        safe, reason = validator.is_path_safe("README.md")
        assert safe
    
    def test_protected_git_directory(self):
        """Test that .git directory is protected."""
        validator = PathValidator("/workspace")
        
        protected, reason = validator.is_protected(".git")
        assert protected
        
        protected, reason = validator.is_protected(".git/HEAD")
        assert protected
        
        protected, reason = validator.is_protected(".git/config")
        assert protected
    
    def test_protected_env_files(self):
        """Test that .env files are protected."""
        validator = PathValidator("/workspace")
        
        protected, reason = validator.is_protected(".env")
        assert protected
        
        protected, reason = validator.is_protected(".env.local")
        assert protected
        
        protected, reason = validator.is_protected(".env.production")
        assert protected
    
    def test_protected_lock_files(self):
        """Test that lock files are protected."""
        validator = PathValidator("/workspace")
        
        # Exact matches
        protected, reason = validator.is_protected("package-lock.json")
        assert protected
        
        protected, reason = validator.is_protected("yarn.lock")
        assert protected
        
        protected, reason = validator.is_protected("poetry.lock")
        assert protected
        
        # Pattern matches
        protected, reason = validator.is_protected("some-package.lock")
        assert protected
    
    def test_protected_node_modules(self):
        """Test that node_modules is protected."""
        validator = PathValidator("/workspace")
        
        protected, reason = validator.is_protected("node_modules")
        assert protected
        
        protected, reason = validator.is_protected("node_modules/express/index.js")
        assert protected
    
    def test_normal_files_not_protected(self):
        """Test that normal files are not protected."""
        validator = PathValidator("/workspace")
        
        protected, reason = validator.is_protected("src/main.py")
        assert not protected
        
        protected, reason = validator.is_protected("README.md")
        assert not protected
        
        protected, reason = validator.is_protected("tests/test_foo.py")
        assert not protected
    
    def test_validate_for_delete(self):
        """Test delete validation."""
        validator = PathValidator("/workspace")
        
        # Normal file OK
        valid, reason = validator.validate_for_delete("src/temp.py")
        assert valid
        
        # Protected file blocked
        valid, reason = validator.validate_for_delete(".env")
        assert not valid
        assert "protected" in reason.lower()
        
        # Path traversal blocked
        valid, reason = validator.validate_for_delete("../etc/passwd")
        assert not valid
        assert "traversal" in reason.lower()
    
    def test_validate_for_move(self):
        """Test move validation."""
        validator = PathValidator("/workspace")
        
        # Normal move OK
        valid, reason = validator.validate_for_move("old.py", "new.py")
        assert valid
        
        # Moving protected source blocked
        valid, reason = validator.validate_for_move(".env", "backup.env")
        assert not valid
        
        # Path traversal in source blocked
        valid, reason = validator.validate_for_move("../etc/passwd", "stolen.txt")
        assert not valid
        
        # Path traversal in destination blocked
        valid, reason = validator.validate_for_move("file.txt", "../etc/crontab")
        assert not valid


class TestAuditLogger:
    """Tests for AuditLogger."""
    
    def test_log_creates_file(self):
        """Test that logging creates the audit file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(
                workspace_path=tmpdir,
                log_file=f"{tmpdir}/audit.log"
            )
            
            logger.log(
                agent="test_agent",
                tool="delete_file",
                action="delete",
                path="test.txt",
                result="success",
            )
            
            assert Path(f"{tmpdir}/audit.log").exists()
    
    def test_log_format(self):
        """Test log entry format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(
                workspace_path=tmpdir,
                log_file=f"{tmpdir}/audit.log"
            )
            
            logger.log(
                agent="backend_dev",
                tool="delete_file",
                action="delete",
                path="temp.py",
                result="blocked",
                details="Protected path",
            )
            
            with open(f"{tmpdir}/audit.log") as f:
                content = f.read()
            
            assert "[backend_dev]" in content
            assert "[delete_file]" in content
            assert "[delete]" in content
            assert "[blocked]" in content
            assert "temp.py" in content
            assert "Protected path" in content
    
    def test_get_recent(self):
        """Test retrieving recent log entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(
                workspace_path=tmpdir,
                log_file=f"{tmpdir}/audit.log"
            )
            
            # Log multiple entries
            for i in range(5):
                logger.log(
                    agent="agent",
                    tool="tool",
                    action="action",
                    path=f"file{i}.txt",
                    result="success",
                )
            
            recent = logger.get_recent(3)
            assert len(recent) == 3
            assert "file4.txt" in recent[-1]
            assert "file2.txt" in recent[0]
    
    def test_get_recent_empty_log(self):
        """Test get_recent with no log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(
                workspace_path=tmpdir,
                log_file=f"{tmpdir}/nonexistent.log"
            )
            
            recent = logger.get_recent()
            assert recent == []


class TestProtectedPaths:
    """Tests for protected paths configuration."""
    
    def test_git_in_protected(self):
        """Test .git is in protected paths."""
        assert ".git" in PROTECTED_PATHS
        assert ".gitignore" in PROTECTED_PATHS
    
    def test_env_in_protected(self):
        """Test .env is in protected paths."""
        assert ".env" in PROTECTED_PATHS
    
    def test_hive_in_protected(self):
        """Test .hive is in protected paths."""
        assert ".hive" in PROTECTED_PATHS
    
    def test_node_modules_in_protected(self):
        """Test node_modules is in protected paths."""
        assert "node_modules" in PROTECTED_PATHS
    
    def test_lock_pattern_exists(self):
        """Test lock file pattern exists."""
        assert any("lock" in p for p in PROTECTED_PATTERNS)


class TestFileOpsIntegration:
    """Integration tests for guardrails with file operations."""
    
    @pytest.mark.asyncio
    async def test_delete_protected_file_blocked(self):
        """Test that deleting .env is blocked."""
        from tools.file_ops import DeleteFileTool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .env file
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("SECRET=test")
            
            tool = DeleteFileTool(workspace_path=tmpdir)
            result = await tool.execute(".env")
            
            assert not result.success
            assert "blockiert" in result.error.lower() or "protected" in result.error.lower()
            # File should still exist
            assert env_file.exists()
    
    @pytest.mark.asyncio
    async def test_delete_git_blocked(self):
        """Test that deleting .git files is blocked."""
        from tools.file_ops import DeleteFileTool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .git directory structure
            git_dir = Path(tmpdir) / ".git"
            git_dir.mkdir()
            head_file = git_dir / "HEAD"
            head_file.write_text("ref: refs/heads/main")
            
            tool = DeleteFileTool(workspace_path=tmpdir)
            result = await tool.execute(".git/HEAD")
            
            assert not result.success
            assert "blockiert" in result.error.lower() or "protected" in result.error.lower()
            # File should still exist
            assert head_file.exists()
    
    @pytest.mark.asyncio
    async def test_path_traversal_blocked(self):
        """Test that path traversal is blocked."""
        from tools.file_ops import DeleteFileTool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = DeleteFileTool(workspace_path=tmpdir)
            result = await tool.execute("../../../etc/passwd")
            
            assert not result.success
            assert "blockiert" in result.error.lower() or "traversal" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_normal_delete_works(self):
        """Test that normal file deletion still works."""
        from tools.file_ops import DeleteFileTool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a normal file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")
            
            tool = DeleteFileTool(workspace_path=tmpdir)
            result = await tool.execute("test.txt")
            
            assert result.success
            assert not test_file.exists()
