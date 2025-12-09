"""Tests for file operation tools."""

import pytest
from pathlib import Path

from tools.file_ops import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirectoryTool,
    FindFilesTool,
    DeleteFileTool,
    MoveFileTool,
    AppendFileTool,
    CreateDirectoryTool,
)
from tools.base import ToolResultStatus


class TestReadFileTool:
    """Tests for ReadFileTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return ReadFileTool(workspace_path=str(temp_dir))

    async def test_read_existing_file(self, tool, temp_file):
        """Should read existing file with line numbers."""
        result = await tool.execute(path=temp_file.name)
        
        assert result.success
        assert "Line 1" in result.output
        assert result.metadata["total_lines"] == 3

    async def test_read_nonexistent_file(self, tool):
        """Should return error for non-existent file."""
        result = await tool.execute(path="nonexistent.txt")
        
        assert result.status == ToolResultStatus.ERROR
        assert "nicht gefunden" in result.error.lower()

    async def test_read_with_line_range(self, tool, temp_file):
        """Should read specific line range."""
        result = await tool.execute(
            path=temp_file.name,
            start_line=1,
            end_line=2,
        )
        
        assert result.success
        assert "Line 1" in result.output
        assert "Line 2" in result.output


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return WriteFileTool(workspace_path=str(temp_dir))

    async def test_write_new_file(self, tool, temp_dir):
        """Should create new file."""
        result = await tool.execute(
            path="new_file.txt",
            content="Hello, World!",
        )
        
        assert result.success
        assert (temp_dir / "new_file.txt").exists()
        assert (temp_dir / "new_file.txt").read_text() == "Hello, World!"

    async def test_write_creates_directories(self, tool, temp_dir):
        """Should create parent directories."""
        result = await tool.execute(
            path="subdir/nested/file.txt",
            content="Nested content",
        )
        
        assert result.success
        assert (temp_dir / "subdir/nested/file.txt").exists()

    async def test_write_no_overwrite_by_default(self, tool, temp_file):
        """Should not overwrite existing file by default."""
        result = await tool.execute(
            path=temp_file.name,
            content="New content",
        )
        
        assert result.status == ToolResultStatus.ERROR
        assert "existiert" in result.error.lower()

    async def test_write_with_overwrite(self, tool, temp_file):
        """Should overwrite when explicitly requested."""
        result = await tool.execute(
            path=temp_file.name,
            content="Overwritten content",
            overwrite=True,
        )
        
        assert result.success
        assert temp_file.read_text() == "Overwritten content"


class TestEditFileTool:
    """Tests for EditFileTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return EditFileTool(workspace_path=str(temp_dir))

    async def test_edit_replace_string(self, tool, temp_file):
        """Should replace string in file."""
        result = await tool.execute(
            path=temp_file.name,
            old_string="Line 2",
            new_string="Modified Line 2",
        )
        
        assert result.success
        content = temp_file.read_text()
        assert "Modified Line 2" in content

    async def test_edit_string_not_found(self, tool, temp_file):
        """Should return error if string not found."""
        result = await tool.execute(
            path=temp_file.name,
            old_string="Nonexistent",
            new_string="New",
        )
        
        assert result.status == ToolResultStatus.ERROR
        assert "nicht gefunden" in result.error.lower()

    async def test_edit_nonexistent_file(self, tool):
        """Should return error for non-existent file."""
        result = await tool.execute(
            path="nonexistent.txt",
            old_string="old",
            new_string="new",
        )
        
        assert result.status == ToolResultStatus.ERROR


class TestListDirectoryTool:
    """Tests for ListDirectoryTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return ListDirectoryTool(workspace_path=str(temp_dir))

    async def test_list_directory(self, tool, temp_file):
        """Should list directory contents."""
        result = await tool.execute(path=".")
        
        assert result.success
        # Output is a formatted string, not a dict
        assert "test_file.txt" in result.output

    async def test_list_with_subdirs(self, tool, temp_dir):
        """Should handle subdirectories."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "subfile.txt").write_text("content")
        
        result = await tool.execute(path=".", recursive=True)
        
        assert result.success

    async def test_list_nonexistent_directory(self, tool):
        """Should return error for non-existent directory."""
        result = await tool.execute(path="nonexistent")
        
        assert result.status == ToolResultStatus.ERROR


class TestFindFilesTool:
    """Tests for FindFilesTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return FindFilesTool(workspace_path=str(temp_dir))

    async def test_find_by_name(self, tool, temp_file):
        """Should find files by name pattern."""
        result = await tool.execute(pattern="*.txt")
        
        assert result.success
        assert "test_file.txt" in result.output

    async def test_find_by_content(self, tool, temp_file):
        """Should find files by content."""
        result = await tool.execute(content="Line 2")
        
        assert result.success
        assert result.metadata["matches"] >= 1

    async def test_find_no_matches(self, tool, temp_dir):
        """Should return empty/no files message when no matches."""
        result = await tool.execute(pattern="*.nonexistent")
        
        assert result.success
        assert result.metadata["matches"] == 0


class TestDeleteFileTool:
    """Tests for DeleteFileTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return DeleteFileTool(workspace_path=str(temp_dir))

    async def test_delete_existing_file(self, tool, temp_dir):
        """Should delete existing file."""
        # Create a file to delete
        file_path = temp_dir / "to_delete.txt"
        file_path.write_text("Delete me")
        
        result = await tool.execute(path="to_delete.txt")
        
        assert result.success
        assert "gelöscht" in result.output
        assert not file_path.exists()

    async def test_delete_nonexistent_file(self, tool):
        """Should return error for non-existent file."""
        result = await tool.execute(path="nonexistent.txt")
        
        assert result.status == ToolResultStatus.ERROR
        assert "nicht gefunden" in result.error.lower()

    async def test_delete_directory_fails(self, tool, temp_dir):
        """Should return error when trying to delete a directory."""
        # Create a subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        
        result = await tool.execute(path="subdir")
        
        assert result.status == ToolResultStatus.ERROR
        assert "verzeichnis" in result.error.lower()


class TestMoveFileTool:
    """Tests for MoveFileTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return MoveFileTool(workspace_path=str(temp_dir))

    async def test_move_file(self, tool, temp_dir):
        """Should move file to new location."""
        # Create source file
        source = temp_dir / "source.txt"
        source.write_text("Move me")
        
        # Create target directory
        target_dir = temp_dir / "target"
        target_dir.mkdir()
        
        result = await tool.execute(
            source="source.txt",
            destination="target/source.txt",
        )
        
        assert result.success
        assert not source.exists()
        assert (temp_dir / "target" / "source.txt").exists()

    async def test_rename_file(self, tool, temp_dir):
        """Should rename file in same directory."""
        # Create source file
        source = temp_dir / "old_name.txt"
        source.write_text("Rename me")
        
        result = await tool.execute(
            source="old_name.txt",
            destination="new_name.txt",
        )
        
        assert result.success
        assert "umbenannt" in result.output
        assert not source.exists()
        assert (temp_dir / "new_name.txt").exists()

    async def test_move_nonexistent_source(self, tool):
        """Should return error for non-existent source."""
        result = await tool.execute(
            source="nonexistent.txt",
            destination="dest.txt",
        )
        
        assert result.status == ToolResultStatus.ERROR
        assert "nicht gefunden" in result.error.lower()

    async def test_move_existing_destination_without_overwrite(self, tool, temp_dir):
        """Should return error when destination exists without overwrite."""
        # Create source and destination files
        source = temp_dir / "source.txt"
        source.write_text("Source")
        dest = temp_dir / "dest.txt"
        dest.write_text("Destination")
        
        result = await tool.execute(
            source="source.txt",
            destination="dest.txt",
        )
        
        assert result.status == ToolResultStatus.ERROR
        assert "existiert bereits" in result.error

    async def test_move_with_overwrite(self, tool, temp_dir):
        """Should overwrite destination when overwrite=True."""
        # Create source and destination files
        source = temp_dir / "source.txt"
        source.write_text("New content")
        dest = temp_dir / "dest.txt"
        dest.write_text("Old content")
        
        result = await tool.execute(
            source="source.txt",
            destination="dest.txt",
            overwrite=True,
        )
        
        assert result.success
        assert not source.exists()
        assert dest.read_text() == "New content"


class TestAppendFileTool:
    """Tests for AppendFileTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return AppendFileTool(workspace_path=str(temp_dir))

    async def test_append_to_existing_file(self, tool, temp_dir):
        """Should append content to existing file."""
        file_path = temp_dir / "append_test.txt"
        file_path.write_text("Line 1\n")
        
        result = await tool.execute(path="append_test.txt", content="Line 2")
        
        assert result.success
        assert file_path.read_text() == "Line 1\nLine 2"

    async def test_append_creates_file(self, tool, temp_dir):
        """Should create file if it doesn't exist."""
        result = await tool.execute(path="new_file.txt", content="New content")
        
        assert result.success
        assert (temp_dir / "new_file.txt").read_text() == "New content"

    async def test_append_with_newline(self, tool, temp_dir):
        """Should add newline before content if file doesn't end with newline."""
        file_path = temp_dir / "no_newline.txt"
        file_path.write_text("Line 1")  # No trailing newline
        
        result = await tool.execute(path="no_newline.txt", content="Line 2")
        
        assert result.success
        assert file_path.read_text() == "Line 1\nLine 2"


class TestCreateDirectoryTool:
    """Tests for CreateDirectoryTool."""

    @pytest.fixture
    def tool(self, temp_dir):
        return CreateDirectoryTool(workspace_path=str(temp_dir))

    async def test_create_directory(self, tool, temp_dir):
        """Should create a new directory."""
        result = await tool.execute(path="new_dir")
        
        assert result.success
        assert (temp_dir / "new_dir").is_dir()
        assert result.metadata["created"] == True

    async def test_create_nested_directories(self, tool, temp_dir):
        """Should create nested directories."""
        result = await tool.execute(path="parent/child/grandchild")
        
        assert result.success
        assert (temp_dir / "parent" / "child" / "grandchild").is_dir()

    async def test_existing_directory(self, tool, temp_dir):
        """Should succeed for existing directory."""
        existing = temp_dir / "existing"
        existing.mkdir()
        
        result = await tool.execute(path="existing")
        
        assert result.success
        assert result.metadata["created"] == False

    async def test_create_fails_if_file_exists(self, tool, temp_dir):
        """Should fail if path exists as file."""
        file_path = temp_dir / "is_a_file"
        file_path.write_text("I'm a file")
        
        result = await tool.execute(path="is_a_file")
        
        assert result.status == ToolResultStatus.ERROR
        assert "Datei" in result.error
