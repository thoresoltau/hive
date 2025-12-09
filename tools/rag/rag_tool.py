"""
RAG Search Tool for Hive Agents.

Provides semantic search capability over the codebase.
"""

from typing import Any, Optional

from tools.base import Tool, ToolResult, ToolResultStatus, ToolParameter

from .embeddings import EmbeddingService
from .vectordb import VectorDB


class RAGSearchTool(Tool):
    """
    Tool for semantic search in the codebase.
    
    Allows agents to find relevant code by describing what they're looking for
    in natural language.
    """
    
    name = "rag_search"
    description = """Search the codebase semantically. Use this to find relevant code, 
functions, classes, or documentation by describing what you're looking for.
Returns the most relevant code snippets with file paths and line numbers."""
    
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Natural language description of what you're looking for. Be specific about functionality, patterns, or concepts.",
            required=True,
        ),
        ToolParameter(
            name="n_results",
            type="integer",
            description="Number of results to return (default: 5, max: 20)",
            required=False,
            default=5,
        ),
        ToolParameter(
            name="language",
            type="string",
            description="Optional: filter by programming language (e.g., 'python', 'javascript')",
            required=False,
        ),
        ToolParameter(
            name="file_path",
            type="string",
            description="Optional: filter by specific file path",
            required=False,
        ),
    ]
    
    def __init__(
        self,
        workspace_path: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None,
        vectordb: Optional[VectorDB] = None,
    ):
        """
        Initialize RAG search tool.
        
        Args:
            workspace_path: Path to workspace (for relative paths in output)
            embedding_service: Service for generating embeddings
            vectordb: Vector database instance
        """
        super().__init__(workspace_path)
        self.embedding_service = embedding_service
        self.vectordb = vectordb
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Ensure services are initialized."""
        if self._initialized:
            return
        
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService()
        
        if self.vectordb is None:
            persist_dir = ".hive/vectordb"
            if self.workspace_path:
                persist_dir = f"{self.workspace_path}/.hive/vectordb"
            self.vectordb = VectorDB(persist_dir=persist_dir)
        
        self._initialized = True
    
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute semantic search.
        
        Args:
            query: Search query
            n_results: Number of results (default 5)
            language: Optional language filter
            file_path: Optional file filter
            
        Returns:
            ToolResult with search results
        """
        query = kwargs.get("query", "")
        n_results = min(kwargs.get("n_results", 5), 20)
        language = kwargs.get("language")
        file_path = kwargs.get("file_path")
        
        if not query:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error="Query is required",
            )
        
        self._ensure_initialized()
        
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.embed_text(query)
            
            # Search vector DB
            results = self.vectordb.search(
                query_embedding=query_embedding,
                n_results=n_results,
                filter_language=language,
                filter_file=file_path,
                score_threshold=0.3,
            )
            
            if not results:
                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    output="No relevant results found for query.",
                )
            
            # Format results
            formatted_results = []
            for i, result in enumerate(results, 1):
                chunk = result.chunk
                
                # Make path relative if workspace_path is set
                display_path = chunk.file_path
                if self.workspace_path and display_path.startswith(self.workspace_path):
                    display_path = display_path[len(self.workspace_path):].lstrip("/")
                
                formatted_results.append({
                    "rank": i,
                    "file": display_path,
                    "lines": f"{chunk.start_line}-{chunk.end_line}",
                    "language": chunk.language,
                    "type": chunk.chunk_type,
                    "score": round(result.score, 3),
                    "content": chunk.content,
                })
            
            # Format output for LLM
            output = self._format_results(formatted_results)
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output,
                metadata={"results_count": len(formatted_results), "query": query},
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                output=None,
                error=str(e),
            )
    
    def _format_results(self, results: list[dict]) -> str:
        """Format search results for LLM consumption."""
        if not results:
            return "No relevant code found."
        
        output_lines = [
            f"Found {len(results)} relevant code snippets:",
            "",
        ]
        
        for item in results:
            output_lines.extend([
                f"### {item['rank']}. {item['file']} (lines {item['lines']})",
                f"Language: {item['language']} | Type: {item['type']} | Score: {item['score']}",
                "```" + item['language'],
                item['content'],
                "```",
                "",
            ])
        
        return "\n".join(output_lines)
