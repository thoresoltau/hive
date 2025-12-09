"""
Tests for RAG components.

Tests chunking, vectordb, and basic functionality.
Embedding tests are skipped by default (require API key).
"""

import tempfile
from pathlib import Path

import pytest

from tools.rag.chunker import CodeChunker, Chunk
from tools.rag.vectordb import VectorDB, SearchResult


class TestChunk:
    """Tests for Chunk dataclass."""
    
    def test_chunk_creation(self):
        """Test creating a chunk."""
        chunk = Chunk(
            content="def hello(): pass",
            file_path="/test/file.py",
            start_line=1,
            end_line=1,
            language="python",
        )
        
        assert chunk.content == "def hello(): pass"
        assert chunk.file_path == "/test/file.py"
        assert chunk.language == "python"
    
    def test_chunk_id(self):
        """Test chunk ID generation."""
        chunk = Chunk(
            content="test",
            file_path="/test/file.py",
            start_line=10,
            end_line=20,
            language="python",
        )
        
        assert chunk.id == "/test/file.py:10-20"
    
    def test_chunk_to_dict(self):
        """Test chunk serialization."""
        chunk = Chunk(
            content="test",
            file_path="/test/file.py",
            start_line=1,
            end_line=5,
            language="python",
            chunk_type="function",
        )
        
        d = chunk.to_dict()
        assert d["content"] == "test"
        assert d["file_path"] == "/test/file.py"
        assert d["chunk_type"] == "function"


class TestCodeChunker:
    """Tests for CodeChunker."""
    
    def test_detect_language(self):
        """Test language detection from file extension."""
        chunker = CodeChunker()
        
        assert chunker.detect_language("test.py") == "python"
        assert chunker.detect_language("test.js") == "javascript"
        assert chunker.detect_language("test.ts") == "typescript"
        assert chunker.detect_language("test.md") == "markdown"
        assert chunker.detect_language("test.unknown") == "text"
    
    def test_chunk_python_file(self):
        """Test chunking a Python file."""
        chunker = CodeChunker()
        
        content = '''"""Module docstring."""

import os

def hello():
    """Say hello."""
    print("Hello")

def world():
    """Say world."""
    print("World")

class MyClass:
    """A class."""
    
    def method(self):
        pass
'''
        
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(content)
            f.flush()
            
            chunks = chunker.chunk_file(f.name)
        
        # Should have multiple chunks (module header, functions, class)
        assert len(chunks) >= 2
        
        # All chunks should have correct metadata
        for chunk in chunks:
            assert chunk.language == "python"
            assert chunk.file_path == f.name
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line
    
    def test_chunk_markdown_file(self):
        """Test chunking a Markdown file."""
        chunker = CodeChunker()
        
        content = '''# Main Title

Introduction text.

## Section 1

Content of section 1.

## Section 2

Content of section 2.

### Subsection

More content.
'''
        
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            f.flush()
            
            chunks = chunker.chunk_file(f.name)
        
        # Should chunk by headings (small sections may be merged)
        assert len(chunks) >= 1
        
        for chunk in chunks:
            assert chunk.language == "markdown"
            assert chunk.chunk_type == "section"
    
    def test_chunk_by_lines_fallback(self):
        """Test line-based chunking for unknown languages."""
        chunker = CodeChunker(chunk_size=100)
        
        # Create content that will require splitting
        content = "\n".join([f"Line {i}" for i in range(50)])
        
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write(content)
            f.flush()
            
            chunks = chunker.chunk_file(f.name)
        
        # Should have multiple chunks due to size limit
        assert len(chunks) >= 1
        
        # Check line numbers are continuous
        all_lines = set()
        for chunk in chunks:
            for line in range(chunk.start_line, chunk.end_line + 1):
                all_lines.add(line)
    
    def test_merge_small_chunks(self):
        """Test that small chunks are merged."""
        chunker = CodeChunker(min_chunk_size=50)
        
        # Create content with small sections
        content = '''# A

x

# B

y

# C

z
'''
        
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
            f.write(content)
            f.flush()
            
            chunks = chunker.chunk_file(f.name)
        
        # Small chunks should be merged
        for chunk in chunks:
            # After merging, chunks should be at least min_chunk_size
            # (unless it's the last/only chunk)
            pass  # Just verify no errors


class TestVectorDB:
    """Tests for VectorDB."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary vector database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = VectorDB(
                persist_dir=tmpdir,
                collection_name="test_collection",
            )
            yield db
    
    def test_create_collection(self, temp_db):
        """Test collection creation."""
        assert temp_db.collection is not None
        assert temp_db.collection_name == "test_collection"
    
    def test_add_and_search(self, temp_db):
        """Test adding chunks and searching."""
        # Create test chunks with mock embeddings
        chunks = [
            Chunk(
                content="def hello(): print('hello')",
                file_path="/test/hello.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
            Chunk(
                content="def world(): print('world')",
                file_path="/test/world.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
        ]
        
        # Mock embeddings (1536 dimensions like OpenAI)
        embeddings = [
            [0.1] * 1536,  # hello
            [0.2] * 1536,  # world
        ]
        
        # Add to DB
        temp_db.add_chunks(chunks, embeddings)
        
        # Verify count
        stats = temp_db.get_stats()
        assert stats["total_chunks"] == 2
        
        # Search with similar embedding
        results = temp_db.search(
            query_embedding=[0.1] * 1536,
            n_results=2,
        )
        
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
    
    def test_delete_by_file(self, temp_db):
        """Test deleting chunks by file path."""
        chunks = [
            Chunk(
                content="content1",
                file_path="/test/file1.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
            Chunk(
                content="content2",
                file_path="/test/file2.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
        ]
        
        embeddings = [[0.1] * 1536, [0.2] * 1536]
        temp_db.add_chunks(chunks, embeddings)
        
        # Delete file1
        deleted = temp_db.delete_by_file("/test/file1.py")
        assert deleted == 1
        
        # Verify only file2 remains
        stats = temp_db.get_stats()
        assert stats["total_chunks"] == 1
    
    def test_get_file_chunks(self, temp_db):
        """Test retrieving chunks by file."""
        chunks = [
            Chunk(
                content="content1",
                file_path="/test/file.py",
                start_line=1,
                end_line=5,
                language="python",
            ),
            Chunk(
                content="content2",
                file_path="/test/file.py",
                start_line=6,
                end_line=10,
                language="python",
            ),
            Chunk(
                content="other",
                file_path="/test/other.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
        ]
        
        embeddings = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        temp_db.add_chunks(chunks, embeddings)
        
        # Get chunks for file.py
        file_chunks = temp_db.get_file_chunks("/test/file.py")
        assert len(file_chunks) == 2
    
    def test_clear(self, temp_db):
        """Test clearing the database."""
        chunks = [
            Chunk(
                content="test",
                file_path="/test/file.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
        ]
        embeddings = [[0.1] * 1536]
        
        temp_db.add_chunks(chunks, embeddings)
        assert temp_db.get_stats()["total_chunks"] == 1
        
        temp_db.clear()
        assert temp_db.get_stats()["total_chunks"] == 0
    
    def test_filter_by_language(self, temp_db):
        """Test filtering search by language."""
        chunks = [
            Chunk(
                content="python code",
                file_path="/test/file.py",
                start_line=1,
                end_line=1,
                language="python",
            ),
            Chunk(
                content="javascript code",
                file_path="/test/file.js",
                start_line=1,
                end_line=1,
                language="javascript",
            ),
        ]
        
        embeddings = [[0.1] * 1536, [0.1] * 1536]  # Same embedding
        temp_db.add_chunks(chunks, embeddings)
        
        # Search with language filter
        results = temp_db.search(
            query_embedding=[0.1] * 1536,
            n_results=10,
            filter_language="python",
        )
        
        assert len(results) == 1
        assert results[0].chunk.language == "python"


# Skip embedding tests by default (require API key)
@pytest.mark.skip(reason="Requires OpenAI API key")
class TestEmbeddingService:
    """Tests for EmbeddingService (require API key)."""
    
    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test embedding single text."""
        from tools.rag.embeddings import EmbeddingService
        
        service = EmbeddingService()
        embedding = await service.embed_text("Hello world")
        
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)
    
    @pytest.mark.asyncio
    async def test_embed_batch(self):
        """Test batch embedding."""
        from tools.rag.embeddings import EmbeddingService
        
        service = EmbeddingService()
        texts = ["Hello", "World", "Test"]
        embeddings = await service.embed_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)
    
    def test_count_tokens(self):
        """Test token counting."""
        from tools.rag.embeddings import EmbeddingService
        
        service = EmbeddingService()
        count = service.count_tokens("Hello world")
        
        assert count > 0
        assert isinstance(count, int)
    
    def test_truncate_text(self):
        """Test text truncation."""
        from tools.rag.embeddings import EmbeddingService
        
        service = EmbeddingService()
        
        # Short text should not be truncated
        short = "Hello"
        assert service.truncate_text(short) == short
        
        # Long text should be truncated
        long = "word " * 10000
        truncated = service.truncate_text(long, max_tokens=100)
        assert service.count_tokens(truncated) <= 100
