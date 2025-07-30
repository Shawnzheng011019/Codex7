import os
from pathlib import Path
from typing import List, Set, Optional, Iterator
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..config import settings
from ..types import CodeFile, FileType
from ..utils.logger import app_logger


class LocalCodebaseScanner:
    """Scanner for local codebase analysis."""
    
    def __init__(self, root_path: Optional[str] = None):
        if root_path is None:
            self.root_path = Path.cwd().resolve()
        else:
            self.root_path = Path(root_path).resolve()
        
        self.supported_extensions = set(settings.supported_extensions_list)
        self.ignored_dirs = {
            '.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules',
            '.idea', '.vscode', '.pytest_cache', '.mypy_cache', 'build', 'dist'
        }
        self.logger = app_logger.bind(component="scanner")
    
    def scan_directory(self, max_workers: int = 4) -> List[CodeFile]:
        """Scan directory and return list of code files."""
        self.logger.info(f"Scanning directory: {self.root_path}")
        
        all_files = []
        for file_path in self._walk_directory():
            all_files.append(file_path)
        
        self.logger.info(f"Found {len(all_files)} files to process")
        return all_files
    
    def _walk_directory(self) -> Iterator[CodeFile]:
        """Walk through directory and yield code files."""
        try:
            for root, dirs, files in os.walk(self.root_path):
                # Remove ignored directories
                dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
                
                for file_name in files:
                    file_path = Path(root) / file_name
                    
                    if self._should_include_file(file_path):
                        code_file = self._create_code_file(file_path)
                        if code_file:
                            yield code_file
                            
        except Exception as e:
            self.logger.error(f"Error scanning directory: {e}")
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in scan."""
        # Check file extension
        if file_path.suffix.lower() not in self.supported_extensions:
            return False
        
        # Check file size (skip files larger than 10MB)
        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:
                self.logger.warning(f"Skipping large file: {file_path}")
                return False
        except OSError:
            return False
        
        return True
    
    def _create_code_file(self, file_path: Path) -> Optional[CodeFile]:
        """Create CodeFile object from file path."""
        try:
            stat = file_path.stat()
            relative_path = file_path.relative_to(self.root_path)
            
            file_type = self._determine_file_type(file_path)
            language = self._determine_language(file_path)
            
            return CodeFile(
                path=str(relative_path),
                absolute_path=str(file_path.resolve()),
                file_type=file_type,
                language=language,
                size=stat.st_size,
                last_modified=stat.st_mtime,
                content=None  # Will be loaded later
            )
            
        except Exception as e:
            self.logger.error(f"Error creating code file for {file_path}: {e}")
            return None
    
    def _determine_file_type(self, file_path: Path) -> FileType:
        """Determine file type based on extension."""
        ext = file_path.suffix.lower()
        
        code_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', 
                          '.sh', '.rb', '.php', '.swift', '.kt', '.scala', '.dart'}
        
        documentation_extensions = {'.md', '.txt', '.rst', '.doc', '.docx'}
        
        configuration_extensions = {'.json', '.yaml', '.yml', '.xml', '.ini', '.cfg', 
                                 '.toml', '.conf', '.properties'}
        
        markup_extensions = {'.html', '.css', '.scss', '.sass', '.less', '.vue', '.jsx', '.tsx'}
        
        if ext in code_extensions:
            return FileType.CODE
        elif ext in documentation_extensions:
            return FileType.DOCUMENTATION
        elif ext in configuration_extensions:
            return FileType.CONFIGURATION
        elif ext in markup_extensions:
            return FileType.MARKUP
        else:
            return FileType.UNKNOWN
    
    def _determine_language(self, file_path: Path) -> Optional[str]:
        """Determine programming language based on extension."""
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust',
            '.sh': 'shell',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.dart': 'dart',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',
            '.vue': 'vue',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.md': 'markdown',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.sql': 'sql',
        }
        
        return ext_to_lang.get(file_path.suffix.lower())
    
    def load_file_content(self, code_file: CodeFile) -> Optional[str]:
        """Load content of a code file."""
        try:
            with open(code_file.absolute_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Error loading file {code_file.absolute_path}: {e}")
            return None
    
    def load_files_content(self, code_files: List[CodeFile], max_workers: int = 4) -> List[CodeFile]:
        """Load content for multiple files in parallel."""
        self.logger.info(f"Loading content for {len(code_files)} files")
        
        def load_content(file: CodeFile) -> CodeFile:
            content = self.load_file_content(file)
            if content:
                file.content = content
            return file
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(load_content, file) for file in code_files]
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Error loading file content: {e}")
        
        # Filter out files that couldn't be loaded
        loaded_files = [f for f in code_files if f.content is not None]
        self.logger.info(f"Successfully loaded content for {len(loaded_files)} files")
        
        return loaded_files