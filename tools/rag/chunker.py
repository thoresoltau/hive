"""
Code Chunker for RAG.

Splits code files into semantic chunks for embedding.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Chunk:
    """A chunk of code or text with metadata."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    chunk_type: str = "code"  # code, function, class, markdown, etc.
    metadata: dict = field(default_factory=dict)
    
    @property
    def id(self) -> str:
        """Unique identifier for this chunk."""
        return f"{self.file_path}:{self.start_line}-{self.end_line}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "content": self.content,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
        }


# Language detection by file extension
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sh": "shell",
    ".bash": "shell",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
}


class CodeChunker:
    """
    Splits code files into semantic chunks.
    
    Supports intelligent splitting for Python (functions/classes),
    Markdown (headings), and falls back to line-based splitting.
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
    ):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target characters per chunk
            chunk_overlap: Overlap between consecutive chunks
            min_chunk_size: Minimum chunk size (smaller chunks are merged)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        return EXTENSION_TO_LANGUAGE.get(ext, "text")
    
    def chunk_file(self, file_path: str, content: Optional[str] = None) -> list[Chunk]:
        """
        Split a file into chunks.
        
        Args:
            file_path: Path to the file
            content: Optional file content (read from file if not provided)
            
        Returns:
            List of Chunk objects
        """
        if content is None:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        
        if not content.strip():
            return []
        
        language = self.detect_language(file_path)
        
        # Choose chunking strategy based on language
        if language == "python":
            chunks = self._chunk_python(file_path, content)
        elif language == "markdown":
            chunks = self._chunk_markdown(file_path, content)
        elif language in ("javascript", "typescript"):
            chunks = self._chunk_javascript(file_path, content)
        else:
            chunks = self._chunk_by_lines(file_path, content, language)
        
        # Merge small chunks
        chunks = self._merge_small_chunks(chunks)
        
        return chunks
    
    def _chunk_python(self, file_path: str, content: str) -> list[Chunk]:
        """Chunk Python file by functions and classes."""
        chunks = []
        lines = content.split("\n")
        
        # Regex patterns for Python constructs
        func_pattern = re.compile(r"^(\s*)(async\s+)?def\s+(\w+)")
        class_pattern = re.compile(r"^(\s*)class\s+(\w+)")
        
        current_chunk_lines = []
        current_start = 1
        current_indent = 0
        current_type = "module"
        
        for i, line in enumerate(lines, 1):
            func_match = func_pattern.match(line)
            class_match = class_pattern.match(line)
            
            # Check if this starts a new top-level definition
            if func_match and len(func_match.group(1)) == 0:
                # Save previous chunk if it exists
                if current_chunk_lines:
                    chunk_content = "\n".join(current_chunk_lines)
                    if chunk_content.strip():
                        chunks.append(Chunk(
                            content=chunk_content,
                            file_path=file_path,
                            start_line=current_start,
                            end_line=i - 1,
                            language="python",
                            chunk_type=current_type,
                        ))
                
                current_chunk_lines = [line]
                current_start = i
                current_type = "function"
                current_indent = 0
                
            elif class_match and len(class_match.group(1)) == 0:
                # Save previous chunk
                if current_chunk_lines:
                    chunk_content = "\n".join(current_chunk_lines)
                    if chunk_content.strip():
                        chunks.append(Chunk(
                            content=chunk_content,
                            file_path=file_path,
                            start_line=current_start,
                            end_line=i - 1,
                            language="python",
                            chunk_type=current_type,
                        ))
                
                current_chunk_lines = [line]
                current_start = i
                current_type = "class"
                current_indent = 0
            else:
                current_chunk_lines.append(line)
                
                # Check if chunk is getting too large
                chunk_content = "\n".join(current_chunk_lines)
                if len(chunk_content) > self.chunk_size * 2:
                    # Split at a reasonable point
                    chunks.append(Chunk(
                        content=chunk_content,
                        file_path=file_path,
                        start_line=current_start,
                        end_line=i,
                        language="python",
                        chunk_type=current_type,
                    ))
                    current_chunk_lines = []
                    current_start = i + 1
                    current_type = "code"
        
        # Don't forget the last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            if chunk_content.strip():
                chunks.append(Chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=len(lines),
                    language="python",
                    chunk_type=current_type,
                ))
        
        return chunks
    
    def _chunk_javascript(self, file_path: str, content: str) -> list[Chunk]:
        """Chunk JavaScript/TypeScript by functions."""
        chunks = []
        lines = content.split("\n")
        
        # Patterns for JS/TS constructs
        func_patterns = [
            re.compile(r"^(export\s+)?(async\s+)?function\s+\w+"),
            re.compile(r"^(export\s+)?const\s+\w+\s*=\s*(async\s+)?\("),
            re.compile(r"^(export\s+)?class\s+\w+"),
        ]
        
        current_chunk_lines = []
        current_start = 1
        current_type = "module"
        
        for i, line in enumerate(lines, 1):
            is_new_definition = any(p.match(line.strip()) for p in func_patterns)
            
            if is_new_definition and current_chunk_lines:
                chunk_content = "\n".join(current_chunk_lines)
                if chunk_content.strip():
                    chunks.append(Chunk(
                        content=chunk_content,
                        file_path=file_path,
                        start_line=current_start,
                        end_line=i - 1,
                        language=self.detect_language(file_path),
                        chunk_type=current_type,
                    ))
                current_chunk_lines = [line]
                current_start = i
                current_type = "function"
            else:
                current_chunk_lines.append(line)
                
                # Check size limit
                chunk_content = "\n".join(current_chunk_lines)
                if len(chunk_content) > self.chunk_size * 2:
                    chunks.append(Chunk(
                        content=chunk_content,
                        file_path=file_path,
                        start_line=current_start,
                        end_line=i,
                        language=self.detect_language(file_path),
                        chunk_type=current_type,
                    ))
                    current_chunk_lines = []
                    current_start = i + 1
                    current_type = "code"
        
        # Last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            if chunk_content.strip():
                chunks.append(Chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=len(lines),
                    language=self.detect_language(file_path),
                    chunk_type=current_type,
                ))
        
        return chunks
    
    def _chunk_markdown(self, file_path: str, content: str) -> list[Chunk]:
        """Chunk Markdown by headings."""
        chunks = []
        lines = content.split("\n")
        
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)")
        
        current_chunk_lines = []
        current_start = 1
        current_heading = ""
        
        for i, line in enumerate(lines, 1):
            heading_match = heading_pattern.match(line)
            
            if heading_match:
                # Save previous section
                if current_chunk_lines:
                    chunk_content = "\n".join(current_chunk_lines)
                    if chunk_content.strip():
                        chunks.append(Chunk(
                            content=chunk_content,
                            file_path=file_path,
                            start_line=current_start,
                            end_line=i - 1,
                            language="markdown",
                            chunk_type="section",
                            metadata={"heading": current_heading},
                        ))
                
                current_chunk_lines = [line]
                current_start = i
                current_heading = heading_match.group(2)
            else:
                current_chunk_lines.append(line)
        
        # Last section
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            if chunk_content.strip():
                chunks.append(Chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=len(lines),
                    language="markdown",
                    chunk_type="section",
                    metadata={"heading": current_heading},
                ))
        
        return chunks
    
    def _chunk_by_lines(
        self,
        file_path: str,
        content: str,
        language: str,
    ) -> list[Chunk]:
        """Fallback: chunk by character count with line boundaries."""
        chunks = []
        lines = content.split("\n")
        
        current_chunk_lines = []
        current_start = 1
        current_size = 0
        
        for i, line in enumerate(lines, 1):
            line_size = len(line) + 1  # +1 for newline
            
            if current_size + line_size > self.chunk_size and current_chunk_lines:
                # Save current chunk
                chunk_content = "\n".join(current_chunk_lines)
                chunks.append(Chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=i - 1,
                    language=language,
                    chunk_type="code",
                ))
                
                # Start new chunk with overlap
                overlap_lines = current_chunk_lines[-3:] if len(current_chunk_lines) > 3 else []
                current_chunk_lines = overlap_lines + [line]
                current_start = max(1, i - len(overlap_lines))
                current_size = sum(len(l) + 1 for l in current_chunk_lines)
            else:
                current_chunk_lines.append(line)
                current_size += line_size
        
        # Last chunk
        if current_chunk_lines:
            chunk_content = "\n".join(current_chunk_lines)
            if chunk_content.strip():
                chunks.append(Chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=len(lines),
                    language=language,
                    chunk_type="code",
                ))
        
        return chunks
    
    def _merge_small_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Merge chunks that are too small."""
        if len(chunks) <= 1:
            return chunks
        
        merged = []
        current = chunks[0]
        
        for next_chunk in chunks[1:]:
            # If current chunk is small, merge with next
            if len(current.content) < self.min_chunk_size:
                current = Chunk(
                    content=current.content + "\n" + next_chunk.content,
                    file_path=current.file_path,
                    start_line=current.start_line,
                    end_line=next_chunk.end_line,
                    language=current.language,
                    chunk_type=current.chunk_type,
                )
            else:
                merged.append(current)
                current = next_chunk
        
        merged.append(current)
        return merged
