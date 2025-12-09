"""Tests for git operation tools."""

import pytest
from pathlib import Path

from tools.git_ops import (
    GitStatusTool,
    GitBranchTool,
    GitCommitTool,
    GitDiffTool,
    GitLogTool,
    GitCurrentBranchTool,
)
from tools.base import ToolResultStatus


class TestGitStatusTool:
    """Tests for GitStatusTool."""

    @pytest.fixture
    def tool(self, temp_git_repo):
        return GitStatusTool(workspace_path=str(temp_git_repo))

    async def test_status_clean_repo(self, tool):
        """Should show clean status."""
        result = await tool.execute()
        
        assert result.success
        assert "status" in result.output

    async def test_status_with_changes(self, tool, temp_git_repo):
        """Should show modified files."""
        # Create a new file
        (temp_git_repo / "new_file.txt").write_text("content")
        
        result = await tool.execute()
        
        assert result.success
        assert "new_file.txt" in result.output["status"]

    async def test_status_short_format(self, tool, temp_git_repo):
        """Should support short format."""
        (temp_git_repo / "new_file.txt").write_text("content")
        
        result = await tool.execute(short=True)
        
        assert result.success


class TestGitBranchTool:
    """Tests for GitBranchTool."""

    @pytest.fixture
    def tool(self, temp_git_repo):
        return GitBranchTool(workspace_path=str(temp_git_repo))

    async def test_create_branch(self, tool):
        """Should create new branch."""
        result = await tool.execute(
            branch_name="feature/test",
            action="create",
        )
        
        assert result.success
        assert result.output["action"] == "created"
        assert result.output["branch"] == "feature/test"

    async def test_switch_branch(self, tool):
        """Should switch to existing branch."""
        # First create branch
        await tool.execute(branch_name="feature/test", action="create")
        # Switch back to main/master
        await tool.execute(branch_name="master", action="switch")
        
        # Switch to feature branch
        result = await tool.execute(
            branch_name="feature/test",
            action="switch",
        )
        
        assert result.success
        assert result.output["action"] == "switched"

    async def test_list_branches(self, tool):
        """Should list all branches."""
        result = await tool.execute(action="list")
        
        assert result.success
        assert "branches" in result.output

    async def test_create_existing_branch_fails(self, tool):
        """Should fail when creating existing branch."""
        await tool.execute(branch_name="feature/test", action="create")
        # Switch back first
        await tool.execute(branch_name="master", action="switch")
        
        result = await tool.execute(
            branch_name="feature/test",
            action="create",
        )
        
        assert result.status == ToolResultStatus.ERROR


class TestGitCommitTool:
    """Tests for GitCommitTool."""

    @pytest.fixture
    def tool(self, temp_git_repo):
        return GitCommitTool(workspace_path=str(temp_git_repo))

    async def test_commit_changes(self, tool, temp_git_repo):
        """Should commit staged changes."""
        # Create a new file
        (temp_git_repo / "new_file.txt").write_text("content")
        
        result = await tool.execute(message="Add new file")
        
        assert result.success
        assert result.output["committed"] == True
        assert "hash" in result.output

    async def test_commit_with_ticket_id(self, tool, temp_git_repo):
        """Should include ticket ID in commit message."""
        (temp_git_repo / "feature.txt").write_text("feature")
        
        result = await tool.execute(
            message="Add feature",
            ticket_id="HIVE-001",
        )
        
        assert result.success
        assert "[HIVE-001]" in result.output["message"]

    async def test_commit_nothing_to_commit(self, tool):
        """Should handle nothing to commit."""
        result = await tool.execute(message="Empty commit")
        
        assert result.success
        assert result.output["committed"] == False

    async def test_commit_specific_files(self, tool, temp_git_repo):
        """Should commit only specified files."""
        (temp_git_repo / "file1.txt").write_text("content1")
        (temp_git_repo / "file2.txt").write_text("content2")
        
        result = await tool.execute(
            message="Add file1 only",
            files=["file1.txt"],
        )
        
        assert result.success


class TestGitDiffTool:
    """Tests for GitDiffTool."""

    @pytest.fixture
    def tool(self, temp_git_repo):
        return GitDiffTool(workspace_path=str(temp_git_repo))

    async def test_diff_no_changes(self, tool):
        """Should show no changes for clean repo."""
        result = await tool.execute()
        
        assert result.success
        assert "Keine Änderungen" in result.output["diff"]

    async def test_diff_with_changes(self, tool, temp_git_repo):
        """Should show diff for modified files."""
        # Modify existing file
        readme = temp_git_repo / "README.md"
        readme.write_text("# Modified\nNew content")
        
        result = await tool.execute()
        
        assert result.success
        # Should show diff
        assert len(result.output["diff"]) > 0

    async def test_diff_specific_file(self, tool, temp_git_repo):
        """Should show diff for specific file."""
        readme = temp_git_repo / "README.md"
        readme.write_text("# Modified")
        
        result = await tool.execute(file_path="README.md")
        
        assert result.success


class TestGitLogTool:
    """Tests for GitLogTool."""

    @pytest.fixture
    def tool(self, temp_git_repo):
        return GitLogTool(workspace_path=str(temp_git_repo))

    async def test_log_shows_commits(self, tool):
        """Should show commit history."""
        result = await tool.execute()
        
        assert result.success
        assert "Initial commit" in result.output["log"]

    async def test_log_with_count(self, tool):
        """Should respect count parameter."""
        result = await tool.execute(count=5)
        
        assert result.success

    async def test_log_oneline_format(self, tool):
        """Should support oneline format."""
        result = await tool.execute(oneline=True)
        
        assert result.success


class TestGitCurrentBranchTool:
    """Tests for GitCurrentBranchTool."""

    @pytest.fixture
    def tool(self, temp_git_repo):
        return GitCurrentBranchTool(workspace_path=str(temp_git_repo))

    async def test_current_branch(self, tool):
        """Should return current branch name."""
        result = await tool.execute()
        
        assert result.success
        assert "branch" in result.output
        # Should be master or main
        assert result.output["branch"] in ["master", "main"]
