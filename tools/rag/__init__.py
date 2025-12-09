"""
RAG (Retrieval-Augmented Generation) module for Hive Agent Swarm.

Components:
- EmbeddingService: Generate embeddings via OpenAI
- CodeChunker: Split code files into semantic chunks
- VectorDB: ChromaDB wrapper for vector storage
- CodebaseIndexer: Index management for codebase
- RAGSearchTool: Tool for agents to search codebase
"""

from .embeddings import EmbeddingService
from .chunker import CodeChunker, Chunk
from .vectordb import VectorDB, SearchResult
from .indexer import CodebaseIndexer
from .rag_tool import RAGSearchTool

__all__ = [
    "EmbeddingService",
    "CodeChunker",
    "Chunk",
    "VectorDB",
    "SearchResult",
    "CodebaseIndexer",
    "RAGSearchTool",
]
