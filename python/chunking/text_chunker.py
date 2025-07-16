"""
Text chunking implementation for documents and code.
"""

import re
import hashlib
from typing import List, Optional, Dict, Any
from pathlib import Path
from loguru import logger

from utils.models import ContentItem, TextChunk, ContentMetadata
from .code_chunker import CodeChunker


class TextChunker:
    """Text chunker that handles both documents and code."""
    
    def __init__(self, 
                 doc_chunk_size: int = 512,
                 doc_overlap: int = 50,
                 code_chunk_size: int = 1024,
                 code_overlap: int = 100,
                 min_chunk_size: int = 50):
        """
        Initialize text chunker.
        
        Args:
            doc_chunk_size: Max tokens for document chunks
            doc_overlap: Overlap tokens between document chunks
            code_chunk_size: Max tokens for code chunks
            code_overlap: Overlap tokens between code chunks  
            min_chunk_size: Minimum chunk size to keep
        """
        self.doc_chunk_size = doc_chunk_size
        self.doc_overlap = doc_overlap
        self.code_chunk_size = code_chunk_size
        self.code_overlap = code_overlap
        self.min_chunk_size = min_chunk_size
        
        # Initialize code chunker for function-level chunking
        self.code_chunker = CodeChunker()
        
        # Code file extensions
        self.code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
            '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.r',
            '.sh', '.bash', '.ps1', '.sql', '.yaml', '.yml', '.json', '.xml',
            '.html', '.css', '.scss', '.less', '.vue', '.svelte'
        }
        
        # Documentation file patterns
        self.doc_patterns = {
            'readme', 'changelog', 'license', 'contributing', 'docs', 'wiki',
            'tutorial', 'guide', 'faq', 'install', 'setup'
        }
    
    async def chunk_content_list(self, content_list: List[ContentItem]) -> List[TextChunk]:
        """
        Chunk a list of content items.
        
        Args:
            content_list: List of content items to chunk
            
        Returns:
            List of text chunks
        """
        all_chunks = []
        
        for content_item in content_list:
            try:
                chunks = await self.chunk_content_item(content_item)
                all_chunks.extend(chunks)
                
                if len(chunks) > 0:
                    logger.debug(f"Generated {len(chunks)} chunks from {content_item.path}")
                    
            except Exception as e:
                logger.error(f"Error chunking {content_item.path}: {e}")
                continue
        
        logger.info(f"Generated {len(all_chunks)} total chunks from {len(content_list)} content items")
        return all_chunks
    
    async def chunk_content_item(self, content_item: ContentItem) -> List[TextChunk]:
        """
        Chunk a single content item.
        
        Args:
            content_item: Content item to chunk
            
        Returns:
            List of text chunks
        """
        # Determine chunk type based on file path
        chunk_type = self._determine_chunk_type(content_item.path)
        
        if chunk_type == 'code':
            # Use function-level chunking for code
            return await self._chunk_code_content(content_item)
        else:
            # Use sliding window for documentation
            return await self._chunk_doc_content(content_item)
    
    def _determine_chunk_type(self, file_path: str) -> str:
        """Determine if file is code or documentation."""
        path = Path(file_path)
        
        # Check file extension
        if path.suffix.lower() in self.code_extensions:
            return 'code'
        
        # Check if it's a documentation file
        filename_lower = path.name.lower()
        for pattern in self.doc_patterns:
            if pattern in filename_lower:
                return 'doc'
        
        # Check if it's in docs directory
        if 'docs' in path.parts or 'doc' in path.parts:
            return 'doc'
        
        # Default to doc for text files
        return 'doc'
    
    async def _chunk_doc_content(self, content_item: ContentItem) -> List[TextChunk]:
        """
        Chunk documentation using sliding window.
        
        Args:
            content_item: Documentation content to chunk
            
        Returns:
            List of document chunks
        """
        chunks = []
        content = content_item.content
        
        # Split content into paragraphs and sections
        sections = self._split_into_sections(content)
        
        for section_idx, section in enumerate(sections):
            # Split section into sentences
            sentences = self._split_into_sentences(section)
            
            if not sentences:
                continue
            
            # Create chunks with sliding window
            current_chunk = []
            current_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = self._estimate_tokens(sentence)
                
                # If adding this sentence exceeds chunk size, create chunk
                if current_tokens + sentence_tokens > self.doc_chunk_size and current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    if len(chunk_text.strip()) >= self.min_chunk_size:
                        chunk = self._create_chunk(
                            content_item, chunk_text, 'doc', 
                            chunk_idx=len(chunks)
                        )
                        chunks.append(chunk)
                    
                    # Start new chunk with overlap
                    overlap_sentences = self._get_overlap_sentences(current_chunk, self.doc_overlap)
                    current_chunk = overlap_sentences + [sentence]
                    current_tokens = sum(self._estimate_tokens(s) for s in current_chunk)
                else:
                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens
            
            # Add remaining content as final chunk
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                if len(chunk_text.strip()) >= self.min_chunk_size:
                    chunk = self._create_chunk(
                        content_item, chunk_text, 'doc', 
                        chunk_idx=len(chunks)
                    )
                    chunks.append(chunk)
        
        return chunks
    
    async def _chunk_code_content(self, content_item: ContentItem) -> List[TextChunk]:
        """
        Chunk code using function-level analysis.
        
        Args:
            content_item: Code content to chunk
            
        Returns:
            List of code chunks
        """
        chunks = []
        
        # Use code chunker to extract functions/classes
        code_units = await self.code_chunker.extract_code_units(
            content_item.content, 
            content_item.path
        )
        
        if not code_units:
            # Fallback to simple text chunking for unrecognized code
            return await self._chunk_code_fallback(content_item)
        
        # Create chunks for each code unit
        for unit in code_units:
            chunk_text = unit.content
            
            # Skip very small chunks
            if len(chunk_text.strip()) < self.min_chunk_size:
                continue
            
            # If chunk is too large, split it
            if self._estimate_tokens(chunk_text) > self.code_chunk_size:
                sub_chunks = self._split_large_code_chunk(chunk_text)
                for i, sub_chunk in enumerate(sub_chunks):
                    chunk = self._create_chunk(
                        content_item, sub_chunk, 'code',
                        start_line=unit.start_line + i * 20,  # Estimate
                        end_line=unit.end_line,
                        chunk_idx=len(chunks)
                    )
                    chunks.append(chunk)
            else:
                chunk = self._create_chunk(
                    content_item, chunk_text, 'code',
                    start_line=unit.start_line,
                    end_line=unit.end_line,
                    chunk_idx=len(chunks)
                )
                chunks.append(chunk)
        
        return chunks
    
    async def _chunk_code_fallback(self, content_item: ContentItem) -> List[TextChunk]:
        """
        Fallback chunking for code files that couldn't be parsed.
        
        Args:
            content_item: Code content to chunk
            
        Returns:
            List of code chunks
        """
        chunks = []
        lines = content_item.content.split('\n')
        
        current_chunk_lines = []
        current_tokens = 0
        start_line = 1
        
        for line_num, line in enumerate(lines, 1):
            line_tokens = self._estimate_tokens(line)
            
            # If adding this line exceeds chunk size, create chunk
            if current_tokens + line_tokens > self.code_chunk_size and current_chunk_lines:
                chunk_text = '\n'.join(current_chunk_lines)
                if len(chunk_text.strip()) >= self.min_chunk_size:
                    chunk = self._create_chunk(
                        content_item, chunk_text, 'code',
                        start_line=start_line,
                        end_line=line_num - 1,
                        chunk_idx=len(chunks)
                    )
                    chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_lines = max(0, self.code_overlap // 10)  # Roughly estimate lines
                if len(current_chunk_lines) > overlap_lines:
                    current_chunk_lines = current_chunk_lines[-overlap_lines:]
                    start_line = line_num - overlap_lines
                else:
                    current_chunk_lines = []
                    start_line = line_num
                
                current_tokens = sum(self._estimate_tokens(l) for l in current_chunk_lines)
            
            current_chunk_lines.append(line)
            current_tokens += line_tokens
        
        # Add remaining lines as final chunk
        if current_chunk_lines:
            chunk_text = '\n'.join(current_chunk_lines)
            if len(chunk_text.strip()) >= self.min_chunk_size:
                chunk = self._create_chunk(
                    content_item, chunk_text, 'code',
                    start_line=start_line,
                    end_line=len(lines),
                    chunk_idx=len(chunks)
                )
                chunks.append(chunk)
        
        return chunks
    
    def _split_into_sections(self, content: str) -> List[str]:
        """Split content into logical sections."""
        # Split by markdown headers
        sections = re.split(r'\n\s*#+\s+', content)
        
        # If no headers found, split by double newlines
        if len(sections) == 1:
            sections = re.split(r'\n\s*\n\s*', content)
        
        return [s.strip() for s in sections if s.strip()]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _get_overlap_sentences(self, sentences: List[str], overlap_tokens: int) -> List[str]:
        """Get overlap sentences for sliding window."""
        if not sentences:
            return []
        
        overlap_sentences = []
        total_tokens = 0
        
        # Take sentences from the end until we reach overlap size
        for sentence in reversed(sentences):
            sentence_tokens = self._estimate_tokens(sentence)
            if total_tokens + sentence_tokens > overlap_tokens:
                break
            overlap_sentences.insert(0, sentence)
            total_tokens += sentence_tokens
        
        return overlap_sentences
    
    def _split_large_code_chunk(self, code_text: str) -> List[str]:
        """Split large code chunks into smaller pieces."""
        lines = code_text.split('\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = self._estimate_tokens(line)
            
            if current_tokens + line_tokens > self.code_chunk_size and current_chunk:
                chunks.append('\n'.join(current_chunk))
                
                # Keep some overlap
                overlap_lines = max(0, self.code_overlap // 10)
                if len(current_chunk) > overlap_lines:
                    current_chunk = current_chunk[-overlap_lines:]
                    current_tokens = sum(self._estimate_tokens(l) for l in current_chunk)
                else:
                    current_chunk = []
                    current_tokens = 0
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        # Simple estimation: ~4 characters per token
        return len(text) // 4
    
    def _create_chunk(self, content_item: ContentItem, chunk_text: str, chunk_type: str,
                     start_line: Optional[int] = None, end_line: Optional[int] = None,
                     chunk_idx: int = 0) -> TextChunk:
        """Create a text chunk from content."""
        chunk_id = self._generate_chunk_id(content_item, chunk_idx)
        text_hash = hashlib.md5(chunk_text.encode('utf-8')).hexdigest()
        token_count = self._estimate_tokens(chunk_text)
        
        # Extract language from file extension
        language = None
        if chunk_type == 'code':
            path = Path(content_item.path)
            language = path.suffix.lstrip('.') if path.suffix else None
        
        return TextChunk(
            id=chunk_id,
            repo=content_item.repo,
            path=content_item.path,
            chunk_type=chunk_type,
            content=chunk_text,
            start_line=start_line,
            end_line=end_line,
            token_count=token_count,
            language=language,
            metadata=content_item.metadata,
            text_hash=text_hash
        )
    
    def _generate_chunk_id(self, content_item: ContentItem, chunk_idx: int) -> str:
        """Generate unique chunk ID."""
        repo_name = content_item.repo.replace('/', '_')
        file_name = Path(content_item.path).name
        return f"{repo_name}_{file_name}_{chunk_idx}" 