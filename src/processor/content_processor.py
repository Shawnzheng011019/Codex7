import re
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from tree_sitter import Language, Parser
    from tree_sitter_languages import get_language
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from langchain.text_splitter import (
    RecursiveCharacterTextSplitter,
    Language as LangchainLanguage,
)

from ..config import settings
from ..types import CodeChunk, CodeFile
from ..utils.logger import app_logger


class ASTParser:
    """AST-based code parser for intelligent chunking."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="ast_parser")
        self.parsers = {}
        self._initialize_parsers()
    
    def _initialize_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        if not TREE_SITTER_AVAILABLE:
            self.logger.warning("Tree-sitter not available, AST parsing will be disabled")
            return
        
        supported_languages = {
            'python': 'python',
            'javascript': 'javascript',
            'typescript': 'typescript',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'go': 'go',
            'rust': 'rust',
        }
        
        for lang_name, lang_id in supported_languages.items():
            try:
                language = get_language(lang_id)
                parser = Parser()
                parser.set_language(language)
                self.parsers[lang_name] = parser
                self.logger.info(f"Initialized parser for {lang_name}")
            except Exception as e:
                self.logger.warning(f"Failed to initialize parser for {lang_name}: {e}")
    
    def parse_code(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Parse code and extract AST nodes."""
        if language not in self.parsers:
            return []
        
        try:
            parser = self.parsers[language]
            tree = parser.parse(bytes(code, 'utf8'))
            
            nodes = []
            self._extract_nodes(tree.root_node, nodes, code)
            return nodes
            
        except Exception as e:
            self.logger.error(f"Error parsing {language} code: {e}")
            return []
    
    def _extract_nodes(self, node, nodes: List[Dict[str, Any]], code: str):
        """Extract nodes from AST."""
        if node.type in ['function_definition', 'class_definition', 'method_definition']:
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
            
            nodes.append({
                'type': node.type,
                'start_line': start_line,
                'end_line': end_line,
                'content': code.split('\n')[start_line-1:end_line],
                'node': node,
            })
        
        for child in node.children:
            self._extract_nodes(child, nodes, code)


class ContentProcessor:
    """Content processor for chunking and embedding generation."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="content_processor")
        self.ast_parser = ASTParser()
        self.text_splitter = self._create_text_splitter()
    
    def _create_text_splitter(self):
        """Create text splitter based on configuration."""
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.max_chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",
                "\n",
                " ",
                ".",
                ",",
                "\t",
            ],
        )
    
    def process_file(self, code_file: CodeFile) -> List[CodeChunk]:
        """Process a single code file into chunks."""
        if not code_file.content:
            return []
        
        self.logger.info(f"Processing file: {code_file.path}")
        
        # Force AST usage - skip file if AST is not available for the language
        if not code_file.language:
            self.logger.warning(f"No language detected for {code_file.path}, skipping file")
            return []
            
        if code_file.language not in self.ast_parser.parsers:
            self.logger.warning(f"AST parser not available for {code_file.language}, skipping file: {code_file.path}")
            return []
            
        if not self.ast_parser.parsers[code_file.language]:
            self.logger.warning(f"AST parser failed to initialize for {code_file.language}, skipping file: {code_file.path}")
            return []
        
        return self._process_with_ast(code_file)
    
    def _process_with_ast(self, code_file: CodeFile) -> List[CodeChunk]:
        """Process file using AST-based chunking."""
        chunks = []
        lines = code_file.content.split('\n')
        
        try:
            ast_nodes = self.ast_parser.parse_code(code_file.content, code_file.language)
            
            for node in ast_nodes:
                chunk_id = self._generate_chunk_id(code_file.path, node['start_line'], node['end_line'])
                chunk_content = '\n'.join(node['content'])
                
                chunk = CodeChunk(
                    id=chunk_id,
                    file_path=code_file.path,
                    content=chunk_content,
                    start_line=node['start_line'],
                    end_line=node['end_line'],
                    language=code_file.language or "unknown",
                    chunk_type=node['type'],
                    metadata={
                        'file_size': code_file.size,
                        'file_type': code_file.file_type.value,
                        'ast_node_type': node['type'],
                    },
                )
                chunks.append(chunk)
                
        except Exception as e:
            self.logger.error(f"Error processing {code_file.path} with AST: {e}")
            # Don't fallback to text splitter, just return empty list
            return []
        
        # If no AST nodes found, log warning and return empty list
        if not chunks:
            self.logger.warning(f"No AST nodes found in {code_file.path}, file will be skipped")
            return []
        
        return chunks
    
    def _process_with_text_splitter(self, code_file: CodeFile) -> List[CodeChunk]:
        """Process file using text-based chunking."""
        chunks = []
        lines = code_file.content.split('\n')
        
        try:
            # Add language-specific separators if available
            lang_separators = self._get_language_separators(code_file.language)
            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.max_chunk_size,
                chunk_overlap=settings.chunk_overlap,
                length_function=len,
                separators=lang_separators,
            )
            
            text_chunks = splitter.split_text(code_file.content)
            
            for i, chunk_content in enumerate(text_chunks):
                # Find line numbers for this chunk
                start_line = self._find_line_number(code_file.content, chunk_content)
                end_line = start_line + chunk_content.count('\n')
                
                chunk_id = self._generate_chunk_id(code_file.path, start_line, end_line)
                
                chunk = CodeChunk(
                    id=chunk_id,
                    file_path=code_file.path,
                    content=chunk_content,
                    start_line=start_line,
                    end_line=end_line,
                    language=code_file.language or "unknown",
                    chunk_type="text_chunk",
                    metadata={
                        'file_size': code_file.size,
                        'file_type': code_file.file_type.value,
                        'chunk_index': i,
                    },
                )
                chunks.append(chunk)
                
        except Exception as e:
            self.logger.error(f"Error processing {code_file.path} with text splitter: {e}")
            
            # Fallback to simple line-based chunking
            return self._simple_line_chunking(code_file)
        
        return chunks
    
    def _get_language_separators(self, language: str) -> List[str]:
        """Get language-specific separators for text splitting."""
        if language == 'python':
            return [
                "\n\n\n",  # Triple newline
                "\n\n",   # Double newline
                "\ndef ",  # Function definitions
                "\nclass ",  # Class definitions
                "\n    ",  # Indented blocks
                "\n",
                " ",
                ".",
                ",",
                "\t",
            ]
        elif language in ['javascript', 'typescript']:
            return [
                "\n\n\n",
                "\n\n",
                "\nfunction ",
                "\nclass ",
                "\nconst ",
                "\nlet ",
                "\nvar ",
                "\n    ",
                "\n",
                " ",
                ".",
                ",",
                "\t",
            ]
        else:
            return [
                "\n\n",
                "\n",
                " ",
                ".",
                ",",
                "\t",
            ]
    
    def _simple_line_chunking(self, code_file: CodeFile) -> List[CodeChunk]:
        """Simple line-based chunking as fallback."""
        chunks = []
        lines = code_file.content.split('\n')
        lines_per_chunk = settings.max_chunk_size // 50  # Rough estimate
        
        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i:i + lines_per_chunk]
            chunk_content = '\n'.join(chunk_lines)
            
            start_line = i + 1
            end_line = i + len(chunk_lines)
            
            chunk_id = self._generate_chunk_id(code_file.path, start_line, end_line)
            
            chunk = CodeChunk(
                id=chunk_id,
                file_path=code_file.path,
                content=chunk_content,
                start_line=start_line,
                end_line=end_line,
                language=code_file.language or "unknown",
                chunk_type="line_chunk",
                metadata={
                    'file_size': code_file.size,
                    'file_type': code_file.file_type.value,
                    'chunk_index': i // lines_per_chunk,
                },
            )
            chunks.append(chunk)
        
        return chunks
    
    def _find_line_number(self, content: str, chunk: str) -> int:
        """Find the starting line number of a chunk in the original content."""
        index = content.find(chunk)
        if index == -1:
            return 1
        
        return content[:index].count('\n') + 1
    
    def _generate_chunk_id(self, file_path: str, start_line: int, end_line: int) -> str:
        """Generate a unique ID for a chunk."""
        unique_string = f"{file_path}:{start_line}-{end_line}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def process_files(self, code_files: List[CodeFile]) -> List[CodeChunk]:
        """Process multiple files into chunks."""
        self.logger.info(f"Processing {len(code_files)} files")
        
        all_chunks = []
        for code_file in code_files:
            chunks = self.process_file(code_file)
            all_chunks.extend(chunks)
        
        self.logger.info(f"Generated {len(all_chunks)} chunks from {len(code_files)} files")
        return all_chunks