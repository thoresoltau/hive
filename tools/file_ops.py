"""File operation tools for agents."""

import os
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
    description = "Liest den Inhalt einer Datei. Gibt den Inhalt mit Zeilennummern zurück."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zur Datei (relativ zum Workspace)",
        ),
        ToolParameter(
            name="start_line",
            type="integer",
            description="Startzeile (1-indexiert, optional)",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="end_line",
            type="integer",
            description="Endzeile (optional, liest bis Ende wenn nicht angegeben)",
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
                    error=f"Datei nicht gefunden: {path}",
                )
            
            if not full_path.is_file():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Pfad ist keine Datei: {path}",
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
                error=f"Datei ist keine Textdatei oder hat unbekannte Kodierung: {path}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Fehler beim Lesen: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to workspace."""
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class WriteFileTool(Tool):
    """Write or create a file."""
    
    name = "write_file"
    description = "Erstellt eine neue Datei oder überschreibt eine bestehende. Erstellt Verzeichnisse automatisch."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zur Datei (relativ zum Workspace)",
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Inhalt der Datei",
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Erlaubt Überschreiben existierender Dateien (default: false)",
            required=False,
            default=False,
        ),
    ]

    async def execute(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
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
                error=f"Operation blockiert: {reason}",
            )
        
        try:
            full_path = self._resolve_path(path)
            is_new = not full_path.exists()
            
            # Safety check: don't overwrite without explicit permission
            if full_path.exists() and not overwrite:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Datei existiert bereits: {path}. Setze overwrite=true um zu überschreiben.",
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
                output=f"Datei geschrieben: {path} ({line_count} Zeilen)",
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
                error=f"Fehler beim Schreiben: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class EditFileTool(Tool):
    """Edit a file by replacing text."""
    
    name = "edit_file"
    description = "Bearbeitet eine Datei durch Ersetzen von Text. Sucht old_string und ersetzt mit new_string."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zur Datei (relativ zum Workspace)",
        ),
        ToolParameter(
            name="old_string",
            type="string",
            description="Text der ersetzt werden soll (muss exakt matchen)",
        ),
        ToolParameter(
            name="new_string",
            type="string",
            description="Neuer Text",
        ),
        ToolParameter(
            name="replace_all",
            type="boolean",
            description="Alle Vorkommen ersetzen (default: false, nur erstes)",
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
                    error=f"Datei nicht gefunden: {path}",
                )
            
            async with aiofiles.open(full_path, "r", encoding="utf-8") as f:
                content = await f.read()
            
            # Check if old_string exists
            if old_string not in content:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Text nicht gefunden in {path}. Stelle sicher, dass der Text exakt übereinstimmt (inkl. Whitespace).",
                )
            
            # Count occurrences
            occurrences = content.count(old_string)
            
            if occurrences > 1 and not replace_all:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Text kommt {occurrences}x vor. Setze replace_all=true oder verwende eindeutigeren Text.",
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
                output=f"Datei bearbeitet: {path} ({replaced} Ersetzung(en))",
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
                error=f"Fehler beim Bearbeiten: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class ListDirectoryTool(Tool):
    """List contents of a directory."""
    
    name = "list_directory"
    description = "Listet Dateien und Ordner in einem Verzeichnis auf."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zum Verzeichnis (relativ zum Workspace, '.' für Root)",
        ),
        ToolParameter(
            name="recursive",
            type="boolean",
            description="Rekursiv auflisten (default: false)",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob-Pattern zum Filtern (z.B. '*.py')",
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
                    error=f"Verzeichnis nicht gefunden: {path}",
                )
            
            if not full_path.is_dir():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Pfad ist kein Verzeichnis: {path}",
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
                output = f"Verzeichnis {path} ist leer"
                if pattern:
                    output += f" (Filter: {pattern})"
            else:
                output = "\n".join(entries[:100])  # Limit output
                if len(entries) > 100:
                    output += f"\n... und {len(entries) - 100} weitere"
            
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
                error=f"Fehler beim Auflisten: {str(e)}",
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
    description = "Sucht Dateien nach Name (Glob) oder Inhalt (Regex)."
    parameters = [
        ToolParameter(
            name="pattern",
            type="string",
            description="Glob-Pattern für Dateinamen (z.B. '*.py', '**/*test*.py')",
            required=False,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Regex-Pattern für Dateiinhalt",
            required=False,
        ),
        ToolParameter(
            name="path",
            type="string",
            description="Startverzeichnis (default: Workspace-Root)",
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
                    error="Mindestens pattern oder content muss angegeben werden.",
                )
            
            full_path = self._resolve_path(path)
            
            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Verzeichnis nicht gefunden: {path}",
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
                output = "Keine Dateien gefunden"
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
                error=f"Ungültiger Regex: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Fehler bei Suche: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class DeleteFileTool(Tool):
    """Delete a file."""
    
    name = "delete_file"
    description = "Löscht eine Datei. Kann keine Verzeichnisse löschen."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zur Datei (relativ zum Workspace)",
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
                error=f"Operation blockiert: {reason}",
            )
        
        try:
            full_path = self._resolve_path(path)
            
            if not full_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Datei nicht gefunden: {path}",
                )
            
            if full_path.is_dir():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Pfad ist ein Verzeichnis, keine Datei: {path}. Nutze delete_directory für Verzeichnisse.",
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
                output=f"Datei gelöscht: {path}",
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
                error=f"Keine Berechtigung zum Löschen: {path}",
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
                error=f"Fehler beim Löschen: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class AppendFileTool(Tool):
    """Append content to a file."""
    
    name = "append_file"
    description = "Hängt Inhalt an eine bestehende Datei an. Erstellt die Datei falls nicht vorhanden."
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Pfad zur Datei (relativ zum Workspace)",
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Inhalt der angehängt werden soll",
        ),
        ToolParameter(
            name="newline",
            type="boolean",
            description="Fügt Zeilenumbruch vor dem Content ein (default: true)",
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
                output=f"Inhalt an {path} angehängt ({len(content)} Zeichen)",
                metadata={"path": path, "appended_chars": len(content)},
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Fehler beim Anhängen: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class CreateDirectoryTool(Tool):
    """Create a directory."""
    
    name = "create_directory"
    description = "Erstellt ein Verzeichnis (inklusive aller Elternverzeichnisse)."
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
                        output=f"Verzeichnis existiert bereits: {path}",
                        metadata={"path": path, "created": False},
                    )
                else:
                    return ToolResult(
                        status=ToolResultStatus.ERROR,
                        output=None,
                        error=f"Pfad existiert bereits als Datei: {path}",
                    )
            
            full_path.mkdir(parents=True, exist_ok=True)
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Verzeichnis erstellt: {path}",
                metadata={"path": path, "created": True},
            )
            
        except PermissionError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Keine Berechtigung zum Erstellen: {path}",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=f"Fehler beim Erstellen: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)


class MoveFileTool(Tool):
    """Move or rename a file or directory."""
    
    name = "move_file"
    description = "Verschiebt oder benennt eine Datei/Verzeichnis um."
    parameters = [
        ToolParameter(
            name="source",
            type="string",
            description="Quellpfad (relativ zum Workspace)",
        ),
        ToolParameter(
            name="destination",
            type="string",
            description="Zielpfad (relativ zum Workspace)",
        ),
        ToolParameter(
            name="overwrite",
            type="boolean",
            description="Überschreiben falls Ziel existiert (default: false)",
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
                error=f"Operation blockiert: {reason}",
            )
        
        try:
            source_path = self._resolve_path(source)
            dest_path = self._resolve_path(destination)
            
            if not source_path.exists():
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Quelle nicht gefunden: {source}",
                )
            
            if dest_path.exists() and not overwrite:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=None,
                    error=f"Ziel existiert bereits: {destination}. Setze overwrite=true zum Überschreiben.",
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
            action = "umbenannt" if is_rename else "verschoben"
            
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
                output=f"Datei {action}: {source} → {destination}",
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
                error=f"Keine Berechtigung für Operation: {source} → {destination}",
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
                error=f"Fehler beim Verschieben: {str(e)}",
            )

    def _resolve_path(self, path: str) -> Path:
        if self.workspace_path:
            return Path(self.workspace_path) / path
        return Path(path)
