"""
Embedding Service for RAG.

Generates embeddings using OpenAI's text-embedding models.
"""

import asyncio
from typing import Optional

import tiktoken
from openai import AsyncOpenAI

from pydantic import BaseModel


class EmbeddingConfig(BaseModel):
    """Configuration for embedding service."""
    model: str = "text-embedding-3-small"
    dimensions: int = 1536
    batch_size: int = 100


class EmbeddingService:
    """
    Service for generating text embeddings via OpenAI API.
    
    Usage:
        service = EmbeddingService()
        embedding = await service.embed_text("Hello world")
        embeddings = await service.embed_batch(["Hello", "World"])
    """
    
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        batch_size: int = 100,
        api_key: Optional[str] = None,
    ):
        """
        Initialize embedding service.
        
        Args:
            model: OpenAI embedding model name
            dimensions: Output embedding dimensions
            batch_size: Maximum texts per API call
            api_key: Optional API key (uses OPENAI_API_KEY env var if not provided)
        """
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Initialize tokenizer for the model
        try:
            self.tokenizer = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback for embedding models
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Max tokens for embedding models
        self.max_tokens = 8191
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
    
    def truncate_text(self, text: str, max_tokens: Optional[int] = None) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens (defaults to model limit)
            
        Returns:
            Truncated text
        """
        max_tokens = max_tokens or self.max_tokens
        tokens = self.tokenizer.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)
    
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        # Truncate if too long
        text = self.truncate_text(text)
        
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        
        return response.data[0].embedding
    
    async def embed_batch(
        self,
        texts: list[str],
        show_progress: bool = False,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            show_progress: Whether to print progress
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Truncate all texts
        texts = [self.truncate_text(t) for t in texts]
        
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            if show_progress:
                print(f"  Embedding batch {i // self.batch_size + 1}/{(len(texts) - 1) // self.batch_size + 1}")
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
            )
            
            # Extract embeddings in order
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
            # Small delay to avoid rate limits
            if i + self.batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        return all_embeddings
    
    async def embed_with_retry(
        self,
        text: str,
        max_retries: int = 3,
        delay: float = 1.0,
    ) -> list[float]:
        """
        Generate embedding with retry logic.
        
        Args:
            text: Text to embed
            max_retries: Maximum retry attempts
            delay: Delay between retries (doubles each retry)
            
        Returns:
            Embedding vector
            
        Raises:
            Exception: If all retries fail
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self.embed_text(text)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))
        
        raise last_error
