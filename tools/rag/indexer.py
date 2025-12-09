"""
Codebase Indexer for RAG.

Manages indexing of code files into the vector database.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .chunker import CodeChunker, Chunk
from .embeddings import EmbeddingService
from .vectordb import VectorDB


# Default file extensions to index
DEFAULT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".md", ".yaml", ".yml", ".json", ".toml",
    ".sql", ".html", ".css", ".scss",
}

# Default directories to exclude
DEFAULT_EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "__pycache__",
    ".git", "dist", "build", ".hive", ".pytest_cache",
    "htmlcov", ".tox", ".mypy_cache", ".ruff_cache",
    "egg-info", ".eggs",
}


class CodebaseIndexer:
    """
    Indexes codebase files into vector database for semantic search.
    
    Usage:
        indexer = CodebaseIndexer(workspace_path="/path/to/project")
        await indexer.index_full()
        # or
        await indexer.index_changed_files()
    """
    
    def __init__(
        self,
        workspace_path: str,
        embedding_service: Optional[EmbeddingService] = None,
        vectordb: Optional[VectorDB] = None,
        chunker: Optional[CodeChunker] = None,
        extensions: Optional[set[str]] = None,
        exclude_dirs: Optional[set[str]] = None,
    ):
        """
        Initialize indexer.
        
        Args:
            workspace_path: Root path of the codebase
            embedding_service: Service for generating embeddings
            vectordb: Vector database instance
            chunker: Code chunker instance
            extensions: File extensions to index
            exclude_dirs: Directories to exclude
        """
        self.workspace_path = Path(workspace_path).resolve()
        self.embedding_service = embedding_service  # Don't auto-create - may not be needed
        self.vectordb = vectordb or VectorDB(
            persist_dir=str(self.workspace_path / ".hive" / "vectordb")
        )
        self.chunker = chunker or CodeChunker()
        self.extensions = extensions or DEFAULT_EXTENSIONS
        self.exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
        
        # Metadata file path
        self.meta_file = self.workspace_path / ".hive" / "index_meta.json"
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate hash of file content."""
        content = file_path.read_bytes()
        return hashlib.md5(content).hexdigest()
    
    def _should_index_file(self, file_path: Path) -> bool:
        """Check if file should be indexed."""
        # Check extension
        if file_path.suffix.lower() not in self.extensions:
            return False
        
        # Check excluded directories
        for part in file_path.parts:
            if part in self.exclude_dirs:
                return False
        
        # Check .gitignore (basic implementation)
        gitignore_path = self.workspace_path / ".gitignore"
        if gitignore_path.exists():
            relative_path = str(file_path.relative_to(self.workspace_path))
            gitignore_patterns = gitignore_path.read_text().splitlines()
            
            for pattern in gitignore_patterns:
                pattern = pattern.strip()
                if not pattern or pattern.startswith("#"):
                    continue
                
                # Simple pattern matching
                if pattern.endswith("/"):
                    # Directory pattern
                    if any(part == pattern[:-1] for part in file_path.parts):
                        return False
                elif pattern in relative_path:
                    return False
        
        return True
    
    def _collect_files(self) -> list[Path]:
        """Collect all files to index."""
        files = []
        
        for file_path in self.workspace_path.rglob("*"):
            if file_path.is_file() and self._should_index_file(file_path):
                files.append(file_path)
        
        return files
    
    def _load_metadata(self) -> dict:
        """Load index metadata."""
        if self.meta_file.exists():
            return json.loads(self.meta_file.read_text())
        return {
            "last_indexed": None,
            "file_hashes": {},
            "total_chunks": 0,
        }
    
    def _save_metadata(self, metadata: dict) -> None:
        """Save index metadata."""
        self.meta_file.parent.mkdir(parents=True, exist_ok=True)
        self.meta_file.write_text(json.dumps(metadata, indent=2))
    
    def needs_reindex(self, file_path: Path) -> bool:
        """Check if file needs re-indexing."""
        metadata = self._load_metadata()
        relative_path = str(file_path.relative_to(self.workspace_path))
        
        if relative_path not in metadata["file_hashes"]:
            return True
        
        current_hash = self._get_file_hash(file_path)
        return current_hash != metadata["file_hashes"][relative_path]
    
    def _ensure_embedding_service(self) -> None:
        """Ensure embedding service is available for indexing."""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService()
    
    async def index_full(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict:
        """
        Index entire codebase (full re-index).
        
        Args:
            progress_callback: Optional callback(file_path, current, total)
            
        Returns:
            Statistics about the indexing operation
        """
        self._ensure_embedding_service()
        
        # Clear existing index
        self.vectordb.clear()
        
        files = self._collect_files()
        total_files = len(files)
        total_chunks = 0
        file_hashes = {}
        
        print(f"Indexing {total_files} files...")
        
        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(str(file_path), i + 1, total_files)
            
            try:
                # Chunk the file
                chunks = self.chunker.chunk_file(str(file_path))
                
                if chunks:
                    # Generate embeddings
                    texts = [chunk.content for chunk in chunks]
                    embeddings = await self.embedding_service.embed_batch(texts)
                    
                    # Store in vector DB
                    self.vectordb.add_chunks(chunks, embeddings)
                    total_chunks += len(chunks)
                
                # Record file hash
                relative_path = str(file_path.relative_to(self.workspace_path))
                file_hashes[relative_path] = self._get_file_hash(file_path)
                
            except Exception as e:
                print(f"  Warning: Failed to index {file_path}: {e}")
        
        # Save metadata
        metadata = {
            "last_indexed": datetime.now().isoformat(),
            "file_hashes": file_hashes,
            "total_chunks": total_chunks,
        }
        self._save_metadata(metadata)
        
        print(f"Indexed {total_chunks} chunks from {total_files} files")
        
        return {
            "files_indexed": total_files,
            "chunks_created": total_chunks,
            "last_indexed": metadata["last_indexed"],
        }
    
    async def index_file(self, file_path: str) -> int:
        """
        Index a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Number of chunks created
        """
        self._ensure_embedding_service()
        
        path = Path(file_path)
        if not path.is_absolute():
            path = self.workspace_path / path
        
        # Remove old chunks for this file
        self.vectordb.delete_by_file(str(path))
        
        # Chunk and index
        chunks = self.chunker.chunk_file(str(path))
        
        if chunks:
            texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_service.embed_batch(texts)
            self.vectordb.add_chunks(chunks, embeddings)
        
        # Update metadata
        metadata = self._load_metadata()
        relative_path = str(path.relative_to(self.workspace_path))
        metadata["file_hashes"][relative_path] = self._get_file_hash(path)
        metadata["total_chunks"] = self.vectordb.get_stats()["total_chunks"]
        self._save_metadata(metadata)
        
        return len(chunks)
    
    async def index_changed_files(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict:
        """
        Index only changed files (incremental update).
        
        Args:
            progress_callback: Optional callback(file_path, current, total)
            
        Returns:
            Statistics about the indexing operation
        """
        self._ensure_embedding_service()
        
        metadata = self._load_metadata()
        files = self._collect_files()
        
        # Find changed files
        changed_files = []
        for file_path in files:
            relative_path = str(file_path.relative_to(self.workspace_path))
            current_hash = self._get_file_hash(file_path)
            
            if relative_path not in metadata["file_hashes"]:
                changed_files.append(file_path)
            elif current_hash != metadata["file_hashes"][relative_path]:
                changed_files.append(file_path)
        
        # Find deleted files
        deleted_files = []
        for relative_path in metadata["file_hashes"]:
            full_path = self.workspace_path / relative_path
            if not full_path.exists():
                deleted_files.append(relative_path)
        
        # Remove deleted files from index
        for relative_path in deleted_files:
            self.vectordb.delete_by_file(str(self.workspace_path / relative_path))
            del metadata["file_hashes"][relative_path]
        
        # Index changed files
        total_chunks = 0
        total_files = len(changed_files)
        
        if total_files > 0:
            print(f"Indexing {total_files} changed files...")
        
        for i, file_path in enumerate(changed_files):
            if progress_callback:
                progress_callback(str(file_path), i + 1, total_files)
            
            try:
                # Remove old chunks
                self.vectordb.delete_by_file(str(file_path))
                
                # Chunk and index
                chunks = self.chunker.chunk_file(str(file_path))
                
                if chunks:
                    texts = [chunk.content for chunk in chunks]
                    embeddings = await self.embedding_service.embed_batch(texts)
                    self.vectordb.add_chunks(chunks, embeddings)
                    total_chunks += len(chunks)
                
                # Update hash
                relative_path = str(file_path.relative_to(self.workspace_path))
                metadata["file_hashes"][relative_path] = self._get_file_hash(file_path)
                
            except Exception as e:
                print(f"  Warning: Failed to index {file_path}: {e}")
        
        # Update metadata
        metadata["last_indexed"] = datetime.now().isoformat()
        metadata["total_chunks"] = self.vectordb.get_stats()["total_chunks"]
        self._save_metadata(metadata)
        
        return {
            "files_changed": total_files,
            "files_deleted": len(deleted_files),
            "chunks_created": total_chunks,
            "last_indexed": metadata["last_indexed"],
        }
    
    async def remove_file(self, file_path: str) -> int:
        """
        Remove a file from the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Number of chunks removed
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.workspace_path / path
        
        count = self.vectordb.delete_by_file(str(path))
        
        # Update metadata
        metadata = self._load_metadata()
        relative_path = str(path.relative_to(self.workspace_path))
        if relative_path in metadata["file_hashes"]:
            del metadata["file_hashes"][relative_path]
            metadata["total_chunks"] = self.vectordb.get_stats()["total_chunks"]
            self._save_metadata(metadata)
        
        return count
    
    def get_status(self) -> dict:
        """Get indexing status."""
        metadata = self._load_metadata()
        db_stats = self.vectordb.get_stats()
        
        return {
            "last_indexed": metadata.get("last_indexed"),
            "indexed_files": len(metadata.get("file_hashes", {})),
            "total_chunks": db_stats["total_chunks"],
            "workspace_path": str(self.workspace_path),
        }
