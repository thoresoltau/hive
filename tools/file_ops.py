"""File operation tools for agents."""

import re
from pathlib import Path
from typing import Optional
import fnmatch

import aiofiles

from .base import Tool, ToolResult, ToolResultStatus, ToolParameter
from .guardrails import get_validator, get_audit_logger


class ReadFileTool(Tool):
    """Read contents of a file."""

    name = "read_file"
    description = "Reads the content of a file. Returns the content with line numbers."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to file (relative to workspace)",
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="Start line (1-indexed, optional)",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="End line (optional, reads to end if not specified)",
            required=False,
        ),
    ]

    async def execute(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
    ) -> ToolResult:
        """Read file contents."""
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"File not found: {path}",
                )

            if not full_path.is_file():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Path is not a file: {path}",
                )

            async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
                lines = await f.readlines()

            # Apply line range
            total_lines = len(lines)
            start_idx = max(0, start_line - 1)
            end_idx = end_line if end_line else total_lines

            selected_lines = lines[start_idx:end_idx]

            # Format with line numbers
            formatted = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                formatted.append(f"{i:4d} | {line.rstrip()}")

            content = "\n".join(formatted)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=content,
                metadata={
                    "path": path,
                    "total_lines": total_lines,
                    "lines_shown": len(selected_lines),
                    "range": f"{start_idx + 1}-{end_idx}",
                },
            )

        except UnicodeDecodeError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"File is not a text file or has unknown encoding: {path}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error reading: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to workspace."""
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class WriteFileTool(Tool):
    """Write or create a file."""

    name = "write_file"
    description = "Creates a new file or overwrites an existing one. Creates directories automatically."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to file (relative to workspace)",
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content of the file",
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Allows overwriting existing files (default: true)",
            required=False,
            default=True,
        ),
    ]

    async def execute(
        self,
        path: str,
        content: str,
        overwrite: bool = True,
    ) -> ToolResult:
        """Write file contents."""
        validator = get_validator(self.workspace_path)
        audit = get_audit_logger(self.workspace_path)

        # Validate path
        valid, reason = validator.validate_for_write(path)
        if not valid:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="write",
                path=path,
                result="blocked",
                details=reason,
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Operation blocked: {reason}",
            )

        try:
            full_path = self._resolve_path(path)
            is_new = not full_path.exists()

            # Safety check: don't overwrite without explicit permission
            if full_path.exists() and not overwrite:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"File already exists: {path}. Set overwrite=true to overwrite.",
                )

            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
                await f.write(content)

            line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

            # Log successful write
            audit.log(
                agent="unknown",
                tool=self.name,
                action="write" if is_new else "overwrite",
                path=path,
                result="success",
                details=f"{line_count} lines",
            )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"File written: {path} ({line_count} lines)",
                metadata={
                    "path": path,
                    "lines": line_count,
                    "bytes": len(content.encode("utf-8")),
                    "created": is_new,
                },
            )

        except Exception as e:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="write",
                path=path,
                result="error",
                details=str(e),
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error writing: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class EditFileTool(Tool):
    """Edit a file by replacing text."""

    name = "edit_file"
    description = "Edits a file by replacing text. Finds old_string and replaces with new_string."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to file (relative to workspace)",
        ),
        ToolParameter(
            name="old_string",
            type="string",
            description="Text to be replaced (must match exactly)",
        ),
        ToolParameter(
            name="new_string",
            type="string",
            description="New text",
        ),
        ToolParameter(
            name="replace_all",
            type="boolean",
            description="Replace all occurrences (default: false, only first)",
            required=False,
            default=False,
        ),
    ]

    async def execute(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> ToolResult:
        """Edit file by string replacement."""
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"File not found: {path}",
                )

            async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
                content = await f.read()

            # Check if old_string exists
            if old_string not in content:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Text not found in {path}. Ensure that the text matches exactly (incl. whitespace).",
                )

            # Count occurrences
            occurrences = content.count(old_string)

            if occurrences > 1 and not replace_all:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Text occurs {occurrences}x. Set replace_all=true or use more specific text.",
                )

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced = occurrences
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced = 1

            # Write back
            async with aiofiles.open(full_path, "w", encoding="utf-8") as f:
                await f.write(new_content)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"File edited: {path} ({replaced} replacement(s))",
                metadata={
                    "path": path,
                    "replacements": replaced,
                    "old_length": len(old_string),
                    "new_length": len(new_string),
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error editing: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class ListDirectoryTool(Tool):
    """List contents of a directory."""

    name = "list_directory"
    description = "Lists files and folders in a directory."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to directory (relative to workspace, '.' for root)",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="List recursively (default: false)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern for filtering (e.g. '*.py')",
            required=False,
        ),
    ]

    async def execute(
        self,
        path: str = ".",
        recursive: bool = False,
        pattern: Optional[str] = None,
    ) -> ToolResult:
        """List directory contents."""
        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Directory not found: {path}",
                )

            if not full_path.is_dir():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Path is not a directory: {path}",
                )

            entries = []

            if recursive:
                items = full_path.rglob("*")
            else:
                items = full_path.iterdir()

            for item in sorted(items):
                # Skip hidden files/directories
                if any(part.startswith(".") for part in item.parts):
                    continue

                # Apply pattern filter
                if pattern and not fnmatch.fnmatch(item.name, pattern):
                    continue

                rel_path = item.relative_to(full_path)

                if item.is_dir():
                    entries.append(f"📁 {rel_path}/")
                else:
                    size = item.stat().st_size
                    size_str = self._format_size(size)
                    entries.append(f"📄 {rel_path} ({size_str})")

            if not entries:
                output = f"Directory {path} is empty"
                if pattern:
                    output += f" (Filter: {pattern})"
            else:
                output = "\n".join(entries[:100])  # Limit output
                if len(entries) > 100:
                    output += f"\n... and {len(entries) - 100} more"

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output,
                metadata={
                    "path": path,
                    "total_entries": len(entries),
                    "recursive": recursive,
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error listing: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)

    def _format_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
            size /= 1024
        return f"{size:.1f}TB"


class FindFilesTool(Tool):
    """Find files by name or content."""

    name = "find_files"
    description = "Searches files by name (Glob) or content (Regex)."
    parameters = [
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob pattern for filenames (e.g. '*.py', '**/*test*.py')",
            required=False,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Regex pattern for file content",
            required=False,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Start directory (default: workspace root)",
            required=False,
            default=".",
        ),
    ]

    async def execute(
        self,
        pattern: Optional[str] = None,
        content: Optional[str] = None,
        path: str = ".",
    ) -> ToolResult:
        """Find files matching criteria."""
        try:
            if not pattern and not content:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error="At least pattern or content must be specified.",
                )

            full_path = self._resolve_path(path)

            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Directory not found: {path}",
                )

            results = []

            # Find by filename pattern
            if pattern:
                files = list(full_path.rglob(pattern))
            else:
                files = list(full_path.rglob("*"))

            # Filter by content if specified
            content_regex = re.compile(content) if content else None

            for file_path in files:
                if not file_path.is_file():
                    continue

                # Skip hidden and binary files
                if any(part.startswith(".") for part in file_path.parts):
                    continue

                rel_path = file_path.relative_to(full_path)

                if content_regex:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            file_content = f.read()

                        matches = list(content_regex.finditer(file_content))
                        if matches:
                            # Find line numbers
                            lines = file_content[:matches[0].start()].count("\n") + 1
                            results.append(f"📄 {rel_path}:{lines} ({len(matches)} matches)")
                    except (UnicodeDecodeError, IOError):
                        continue
                else:
                    results.append(f"📄 {rel_path}")

            if not results:
                output = "No files found"
            else:
                output = "\n".join(results[:50])
                if len(results) > 50:
                    output += f"\n... und {len(results) - 50} weitere"

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output,
                metadata={
                    "matches": len(results),
                    "pattern": pattern,
                    "content_search": content is not None,
                },
            )

        except re.error as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Invalid regex: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error searching: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class DeleteFileTool(Tool):
    """Delete a file."""

    name = "delete_file"
    description = "Deletes a file. Cannot delete directories."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to file (relative to workspace)",
        ),
    ]

    async def execute(self, path: str) -> ToolResult:
        """Delete a file."""
        validator = get_validator(self.workspace_path)
        audit = get_audit_logger(self.workspace_path)

        # Validate path before any operation
        valid, reason = validator.validate_for_delete(path)
        if not valid:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="delete",
                path=path,
                result="blocked",
                details=reason,
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Operation blocked: {reason}",
            )

        try:
            full_path = self._resolve_path(path)

            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"File not found: {path}",
                )

            if full_path.is_dir():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Path is a directory, not a file: {path}. Use delete_directory for directories.",
                )

            # Delete the file
            full_path.unlink()

            # Log successful deletion
            audit.log(
                agent="unknown",
                tool=self.name,
                action="delete",
                path=path,
                result="success",
            )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"File deleted: {path}",
                metadata={"path": path, "deleted": True},
            )

        except PermissionError:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="delete",
                path=path,
                result="error",
                details="Permission denied",
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"No permission to delete: {path}",
            )
        except Exception as e:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="delete",
                path=path,
                result="error",
                details=str(e),
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error deleting: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class AppendFileTool(Tool):
    """Append content to a file."""

    name = "append_file"
    description = "Appends content to an existing file. Creates the file if it does not exist."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to file (relative to workspace)",
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to be appended",
        ),
        ToolParameter(
            name="newline",
            type="boolean",
            description="Inserts line break before content (default: true)",
            required=False,
            default=True,
        ),
    ]

    async def execute(
        self,
        path: str,
        content: str,
        newline: bool = True,
    ) -> ToolResult:
        """Append content to file."""
        try:
            full_path = self._resolve_path(path)

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare content
            if newline and full_path.exists():
                # Check if file ends with newline
                with open(full_path, 'r', encoding='utf-8') as f:
                    existing = f.read()
                    if existing and not existing.endswith('\n'):
                        content = '\n' + content

            # Append to file
            async with aiofiles.open(full_path, "a", encoding="utf-8") as f:
                await f.write(content)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Content appended to {path} ({len(content)} characters)",
                metadata={"path": path, "appended_chars": len(content)},
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error appending: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class CreateDirectoryTool(Tool):
    """Create a directory."""

    name = "create_directory"
    description = "Creates a directory (including all parent directories)."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zum Verzeichnis (relativ zum Workspace)",
        ),
    ]

    async def execute(self, path: str) -> ToolResult:
        """Create directory."""
        try:
            full_path = self._resolve_path(path)

            if full_path.exists():
                if full_path.is_dir():
                    return ToolResult(
                        status=ToolResultStatus.SUCCESS,
                        output=f"Directory already exists: {path}",
                        metadata={"path": path, "created": False},
                    )
                else:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        output=None,
                        error=f"Path already exists as a file: {path}",
                    )

            full_path.mkdir(parents=True, exist_ok=True)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Directory created: {path}",
                metadata={"path": path, "created": True},
            )

        except PermissionError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"No permission to create: {path}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error creating: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class MoveFileTool(Tool):
    """Move or rename a file or directory."""

    name = "move_file"
    description = "Moves or renames a file/directory."
    parameters = [
        ToolParameter(
            name="source",
            type="string",
            description="Source path (relative to workspace)",
        ),
        ToolParameter(
            name="destination",
            type="string",
            description="Destination path (relative to workspace)",
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Overwrite if destination exists (default: false)",
            required=False,
            default=False,
        ),
    ]

    async def execute(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> ToolResult:
        """Move or rename a file/directory."""
        import shutil

        validator = get_validator(self.workspace_path)
        audit = get_audit_logger(self.workspace_path)

        # Validate both paths
        valid, reason = validator.validate_for_move(source, destination)
        if not valid:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="move",
                path=f"{source} → {destination}",
                result="blocked",
                details=reason,
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Operation blocked: {reason}",
            )

        try:
            source_path = self._resolve_path(source)
            dest_path = self._resolve_path(destination)

            if not source_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Source not found: {source}",
                )

            if dest_path.exists() and not overwrite:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Destination already exists: {destination}. Set overwrite=true to overwrite.",
                )

            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move/rename
            if dest_path.exists() and overwrite:
                if dest_path.is_dir():
                    shutil.rmtree(dest_path)
                else:
                    dest_path.unlink()

            shutil.move(str(source_path), str(dest_path))

            is_rename = source_path.parent == dest_path.parent
            action = "renamed" if is_rename else "moved"

            # Log successful move
            audit.log(
                agent="unknown",
                tool=self.name,
                action="rename" if is_rename else "move",
                path=f"{source} → {destination}",
                result="success",
            )

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"File {action}: {source} → {destination}",
                metadata={
                    "source": source,
                    "destination": destination,
                    "action": "rename" if is_rename else "move",
                },
            )

        except PermissionError:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="move",
                path=f"{source} → {destination}",
                result="error",
                details="Permission denied",
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"No permission for operation: {source} → {destination}",
            )
        except Exception as e:
            audit.log(
                agent="unknown",
                tool=self.name,
                action="move",
                path=f"{source} → {destination}",
                result="error",
                details=str(e),
            )
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Error moving: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)
