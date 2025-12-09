"""
Vector Database wrapper for RAG.

Uses ChromaDB for persistent vector storage.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings

from .chunker import Chunk


@dataclass
class SearchResult:
    """Result from a vector search."""
    chunk: Chunk
    score: float  # Similarity score (higher is better, 0-1 range)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
        }


class VectorDB:
    """
    ChromaDB wrapper for vector storage and retrieval.
    
    Usage:
        db = VectorDB(persist_dir=".hive/vectordb")
        db.add_chunks(chunks, embeddings)
        results = db.search(query_embedding, n_results=5)
    """
    
    def __init__(
        self,
        persist_dir: str = ".hive/vectordb",
        collection_name: str = "hive_codebase",
    ):
        """
        Initialize vector database.
        
        Args:
            persist_dir: Directory for persistent storage
            collection_name: Name of the collection
        """
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        
        # Ensure directory exists
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        
        self.collection = self.get_or_create_collection(collection_name)
    
    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get existing collection or create new one."""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
    
    def add_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """
        Add chunks with their embeddings to the database.
        
        Args:
            chunks: List of Chunk objects
            embeddings: Corresponding embedding vectors
        """
        if not chunks:
            return
        
        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
        
        # Prepare data for ChromaDB
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language,
                "chunk_type": chunk.chunk_type,
            }
            for chunk in chunks
        ]
        
        # Add to collection (ChromaDB handles duplicates by ID)
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
    
    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        filter_file: Optional[str] = None,
        filter_language: Optional[str] = None,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        Search for similar chunks.
        
        Args:
            query_embedding: Query vector
            n_results: Maximum number of results
            filter_file: Optional file path filter
            filter_language: Optional language filter
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of SearchResult objects, sorted by relevance
        """
        # Build where filter
        where_filter = None
        if filter_file or filter_language:
            conditions = []
            if filter_file:
                conditions.append({"file_path": filter_file})
            if filter_language:
                conditions.append({"language": filter_language})
            
            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        
        # Convert to SearchResult objects
        search_results = []
        
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # ChromaDB returns distance, convert to similarity score
                # For cosine distance: similarity = 1 - distance
                distance = results["distances"][0][i]
                score = 1 - distance
                
                if score < score_threshold:
                    continue
                
                metadata = results["metadatas"][0][i]
                content = results["documents"][0][i]
                
                chunk = Chunk(
                    content=content,
                    file_path=metadata["file_path"],
                    start_line=metadata["start_line"],
                    end_line=metadata["end_line"],
                    language=metadata["language"],
                    chunk_type=metadata.get("chunk_type", "code"),
                )
                
                search_results.append(SearchResult(chunk=chunk, score=score))
        
        return search_results
    
    def delete_by_file(self, file_path: str) -> int:
        """
        Delete all chunks from a specific file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Number of chunks deleted
        """
        # Get IDs of chunks from this file
        results = self.collection.get(
            where={"file_path": file_path},
            include=[],
        )
        
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        
        return 0
    
    def get_file_chunks(self, file_path: str) -> list[Chunk]:
        """Get all chunks from a specific file."""
        results = self.collection.get(
            where={"file_path": file_path},
            include=["documents", "metadatas"],
        )
        
        chunks = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                content = results["documents"][i]
                
                chunk = Chunk(
                    content=content,
                    file_path=metadata["file_path"],
                    start_line=metadata["start_line"],
                    end_line=metadata["end_line"],
                    language=metadata["language"],
                    chunk_type=metadata.get("chunk_type", "code"),
                )
                chunks.append(chunk)
        
        return chunks
    
    def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        count = self.collection.count()
        
        return {
            "collection_name": self.collection_name,
            "total_chunks": count,
            "persist_dir": str(self.persist_dir),
        }
    
    def clear(self) -> None:
        """Clear all data from the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.get_or_create_collection(self.collection_name)
    
    def reset(self) -> None:
        """Reset the entire database."""
        self.client.reset()
        self.collection = self.get_or_create_collection(self.collection_name)
