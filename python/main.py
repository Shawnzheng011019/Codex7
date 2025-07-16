#!/usr/bin/env python3
"""
Codex7 RAG System - Python Processing Pipeline

This script handles the complete data processing pipeline:
1. Crawl GitHub repositories
2. Extract and clean content
3. Generate embeddings
4. Store in vector database
5. Build search indices

Usage:
    python main.py --crawl --extract --chunk --embed --store
    python main.py --full-pipeline
"""

import asyncio
import argparse
import sys
from pathlib import Path
from loguru import logger
from typing import List

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from utils.config import get_config
from utils.models import GitHubRepo, ProcessingPipeline, ProcessingStep
from crawler.gitstar_ranking import GitStarRankingCrawler
from crawler.github_api import GitHubAPIClient
from extractor.content_extractor import ContentExtractor

config = get_config()

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    level=config.log_level.upper(),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(
    config.log_file,
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    rotation="100 MB",
    retention="30 days"
)


class ProcessingPipelineManager:
    """Manages the complete data processing pipeline."""
    
    def __init__(self):
        self.config = config
        
    async def run_full_pipeline(self):
        """Run the complete processing pipeline."""
        logger.info("Starting full processing pipeline")
        
        try:
            # Step 1: Crawl repositories
            repos = await self.crawl_repositories()
            if not repos:
                logger.error("No repositories found, stopping pipeline")
                return
            
            # Step 2: Extract content
            all_content = await self.extract_content(repos)
            if not all_content:
                logger.error("No content extracted, stopping pipeline")
                return
            
            # Step 3: Generate chunks
            chunks = await self.generate_chunks(all_content)
            if not chunks:
                logger.error("No chunks generated, stopping pipeline")
                return
            
            # Step 4: Generate embeddings
            vectors = await self.generate_embeddings(chunks)
            if not vectors:
                logger.error("No embeddings generated, stopping pipeline")
                return
            
            # Step 5: Store in vector database
            await self.store_vectors(vectors)
            

            
            logger.success("Full processing pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
    
    async def crawl_repositories(self) -> List[GitHubRepo]:
        """Crawl and enrich GitHub repositories."""
        logger.info(f"Crawling top {config.max_repos} repositories")
        
        repos = []
        
        try:
            # Crawl repositories from GitStar ranking
            async with GitStarRankingCrawler() as crawler:
                crawl_result = await crawler.crawl_top_repositories(config.max_repos)
                
                if crawl_result.errors:
                    logger.warning(f"Crawling had {len(crawl_result.errors)} errors")
                    for error in crawl_result.errors[:5]:  # Show first 5 errors
                        logger.warning(f"Crawl error: {error}")
                
                repos = crawl_result.repos
                logger.info(f"Found {len(repos)} repositories from GitStar ranking")
            
            # Enrich with GitHub API
            if repos and config.github_token:
                logger.info("Enriching repositories with GitHub API data")
                async with GitHubAPIClient(config.github_token) as github_client:
                    enriched_repos = []
                    
                    for i, repo in enumerate(repos):
                        try:
                            enriched_repo = await github_client.enrich_repository(repo)
                            enriched_repos.append(enriched_repo)
                            
                            if (i + 1) % 10 == 0:
                                logger.info(f"Enriched {i + 1}/{len(repos)} repositories")
                                
                        except Exception as e:
                            logger.warning(f"Failed to enrich {repo.full_name}: {e}")
                            enriched_repos.append(repo)  # Use original
                    
                    repos = enriched_repos
            
            # Save repository list
            await self._save_repositories(repos)
            
            logger.success(f"Successfully processed {len(repos)} repositories")
            return repos
            
        except Exception as e:
            logger.error(f"Error in repository crawling: {e}")
            raise
    
    async def extract_content(self, repos: List[GitHubRepo]):
        """Extract content from repositories."""
        logger.info(f"Extracting content from {len(repos)} repositories")
        
        all_content = []
        
        try:
            async with GitHubAPIClient(config.github_token) as github_client:
                extractor = ContentExtractor(github_client)
                
                for i, repo in enumerate(repos):
                    try:
                        repo_content = await extractor.extract_repository_content(repo)
                        all_content.extend(repo_content)
                        
                        logger.info(f"Extracted {len(repo_content)} items from {repo.full_name} ({i+1}/{len(repos)})")
                        
                    except Exception as e:
                        logger.error(f"Failed to extract content from {repo.full_name}: {e}")
            
            # Save extracted content
            await self._save_extracted_content(all_content)
            
            logger.success(f"Successfully extracted {len(all_content)} content items")
            return all_content
            
        except Exception as e:
            logger.error(f"Error in content extraction: {e}")
            raise
    
    async def generate_chunks(self, content_list):
        """Generate text chunks from extracted content."""
        logger.info(f"Generating chunks from {len(content_list)} content items")
        
        # Import chunking module when needed
        from chunking.text_chunker import TextChunker
        
        try:
            chunker = TextChunker()
            chunks = await chunker.chunk_content_list(content_list)
            
            # Save chunks
            await self._save_chunks(chunks)
            
            logger.success(f"Successfully generated {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in chunk generation: {e}")
            raise
    
    async def generate_embeddings(self, chunks):
        """Generate embeddings for text chunks."""
        logger.info(f"Generating embeddings for {len(chunks)} chunks")
        
        # Import embedding module when needed
        from embedding.embedding_generator import EmbeddingGenerator
        
        try:
            embedding_gen = EmbeddingGenerator()
            vectors = await embedding_gen.generate_embeddings(chunks)
            
            # Save embeddings
            await self._save_embeddings(vectors)
            
            logger.success(f"Successfully generated {len(vectors)} embeddings")
            return vectors
            
        except Exception as e:
            logger.error(f"Error in embedding generation: {e}")
            raise
    
    async def store_vectors(self, vectors):
        """Store vectors in Milvus database."""
        logger.info(f"Storing {len(vectors)} vectors in Milvus")
        
        # Import vectordb module when needed
        from vectordb.milvus_client import MilvusClient
        
        try:
            async with MilvusClient() as milvus_client:
                await milvus_client.create_collection()
                await milvus_client.insert_vectors(vectors)
                await milvus_client.create_index()
            
            logger.success("Successfully stored vectors in Milvus")
            
        except Exception as e:
            logger.error(f"Error storing vectors: {e}")
            raise
    

    
    async def _save_repositories(self, repos: List[GitHubRepo]):
        """Save repository list to file."""
        import json
        
        repos_data = [repo.model_dump() for repo in repos]
        
        output_path = Path(config.cache_dir) / "repositories.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(repos_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(repos)} repositories to {output_path}")
    
    async def _save_extracted_content(self, content_list):
        """Save extracted content to file."""
        import json
        
        content_data = [content.model_dump() for content in content_list]
        
        output_path = Path(config.cache_dir) / "extracted_content.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(content_list)} content items to {output_path}")
    
    async def _save_chunks(self, chunks):
        """Save chunks to file."""
        import json
        
        chunks_data = [chunk.model_dump() for chunk in chunks]
        
        output_path = Path(config.cache_dir) / "chunks.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(chunks)} chunks to {output_path}")
    
    async def _save_embeddings(self, vectors):
        """Save embeddings to file."""
        import json
        import numpy as np
        
        # Convert numpy arrays to lists for JSON serialization
        vectors_data = []
        for vector in vectors:
            vector_dict = vector.model_dump()
            if isinstance(vector_dict['vector'], np.ndarray):
                vector_dict['vector'] = vector_dict['vector'].tolist()
            vectors_data.append(vector_dict)
        
        output_path = Path(config.cache_dir) / "embeddings.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(vectors_data, f, indent=2)
        
        logger.info(f"Saved {len(vectors)} embeddings to {output_path}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Codex7 RAG System Processing Pipeline")
    
    # Pipeline steps
    parser.add_argument("--crawl", action="store_true", help="Crawl GitHub repositories")
    parser.add_argument("--extract", action="store_true", help="Extract content from repositories")
    parser.add_argument("--chunk", action="store_true", help="Generate text chunks")
    parser.add_argument("--embed", action="store_true", help="Generate embeddings")
    parser.add_argument("--store", action="store_true", help="Store vectors in database")

    parser.add_argument("--full-pipeline", action="store_true", help="Run complete pipeline")
    
    # Configuration
    parser.add_argument("--max-repos", type=int, default=100, help="Maximum repositories to process")
    parser.add_argument("--config-file", type=str, help="Configuration file path")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.crawl, args.extract, args.chunk, args.embed, args.store, args.full_pipeline]):
        parser.print_help()
        return
    
    # Update config if provided
    if args.max_repos:
        config.max_repos = args.max_repos
    
    # Initialize pipeline manager
    pipeline = ProcessingPipelineManager()
    
    try:
        if args.full_pipeline:
            await pipeline.run_full_pipeline()
        else:
            # Run individual steps
            repos = None
            content = None
            chunks = None
            vectors = None
            
            if args.crawl:
                repos = await pipeline.crawl_repositories()
            
            if args.extract:
                if not repos:
                    # Load from cache
                    repos = await load_repositories_from_cache()
                content = await pipeline.extract_content(repos)
            
            if args.chunk:
                if not content:
                    content = await load_content_from_cache()
                chunks = await pipeline.generate_chunks(content)
            
            if args.embed:
                if not chunks:
                    chunks = await load_chunks_from_cache()
                vectors = await pipeline.generate_embeddings(chunks)
            
            if args.store:
                if not vectors:
                    vectors = await load_embeddings_from_cache()
                await pipeline.store_vectors(vectors)
            

        
        logger.success("Pipeline execution completed successfully!")
        
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


async def load_repositories_from_cache():
    """Load repositories from cache file."""
    import json
    from utils.models import GitHubRepo
    
    cache_path = Path(config.cache_dir) / "repositories.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"Repository cache not found: {cache_path}")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        repos_data = json.load(f)
    
    return [GitHubRepo(**repo_data) for repo_data in repos_data]


async def load_content_from_cache():
    """Load extracted content from cache file."""
    import json
    from utils.models import ExtractedContent, ContentMetadata
    
    cache_path = Path(config.cache_dir) / "extracted_content.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"Content cache not found: {cache_path}")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        content_data = json.load(f)
    
    content_list = []
    for item in content_data:
        metadata = ContentMetadata(**item['metadata'])
        content = ExtractedContent(**{**item, 'metadata': metadata})
        content_list.append(content)
    
    return content_list


async def load_chunks_from_cache():
    """Load chunks from cache file."""
    import json
    from utils.models import TextChunk, ContentMetadata
    
    cache_path = Path(config.cache_dir) / "chunks.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"Chunks cache not found: {cache_path}")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        chunks_data = json.load(f)
    
    chunks = []
    for item in chunks_data:
        metadata = ContentMetadata(**item['metadata'])
        chunk = TextChunk(**{**item, 'metadata': metadata})
        chunks.append(chunk)
    
    return chunks


async def load_embeddings_from_cache():
    """Load embeddings from cache file."""
    import json
    import numpy as np
    from utils.models import EmbeddingVector, VectorMetadata
    
    cache_path = Path(config.cache_dir) / "embeddings.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"Embeddings cache not found: {cache_path}")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        vectors_data = json.load(f)
    
    vectors = []
    for item in vectors_data:
        metadata = VectorMetadata(**item['metadata'])
        vector = EmbeddingVector(
            id=item['id'],
            vector=np.array(item['vector']),
            metadata=metadata
        )
        vectors.append(vector)
    
    return vectors


if __name__ == "__main__":
    asyncio.run(main()) 