import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from loguru import logger
import markdown
import re
from pathlib import Path
import hashlib
from datetime import datetime

from utils.models import GitHubRepo, ExtractedContent, ContentMetadata
from utils.config import get_config
from crawler.github_api import GitHubAPIClient

config = get_config()


class ContentExtractor:
    """Extract and clean content from GitHub repositories."""
    
    def __init__(self, github_client: GitHubAPIClient):
        self.github_client = github_client
        
    async def extract_repository_content(self, repo: GitHubRepo) -> List[ExtractedContent]:
        """Extract all relevant content from a repository."""
        extracted_content = []
        
        logger.info(f"Extracting content from repository: {repo.full_name}")
        
        try:
            # Get all files from repository
            files = await self.github_client.get_repository_files(repo.full_name)
            
            # Extract documentation
            doc_content = await self._extract_documentation(repo, files)
            extracted_content.extend(doc_content)
            
            # Extract code content
            code_content = await self._extract_code(repo, files)
            extracted_content.extend(code_content)
            
            # Extract issues (high-value ones)
            issue_content = await self._extract_issues(repo)
            extracted_content.extend(issue_content)
            
            logger.info(f"Extracted {len(extracted_content)} content items from {repo.full_name}")
            
        except Exception as e:
            logger.error(f"Error extracting content from {repo.full_name}: {e}")
        
        return extracted_content
    
    async def _extract_documentation(self, repo: GitHubRepo, files: List[Dict[str, Any]]) -> List[ExtractedContent]:
        """Extract documentation files."""
        doc_content = []
        
        # Documentation file patterns
        doc_patterns = [
            r'readme.*\.(md|rst|txt)$',
            r'.*\.md$',
            r'.*\.rst$',
            r'docs?/.*\.(md|rst|txt)$',
            r'wiki.*\.(md|rst|txt)$',
            r'.*\.adoc$'
        ]
        
        doc_files = []
        for file_info in files:
            filename = file_info['name'].lower()
            filepath = file_info['path'].lower()
            
            for pattern in doc_patterns:
                if re.match(pattern, filename) or re.match(pattern, filepath):
                    doc_files.append(file_info)
                    break
        
        # Process documentation files
        for file_info in doc_files[:50]:  # Limit to prevent overwhelming
            try:
                content = await self.github_client.get_file_content(repo.full_name, file_info['path'])
                if content:
                    cleaned_content = self._clean_markdown_content(content)
                    if cleaned_content.strip():
                        metadata = ContentMetadata(
                            repo=repo.full_name,
                            path=file_info['path'],
                            language=self._detect_file_language(file_info['name']),
                            file_size=file_info['size'],
                            last_modified=repo.last_commit_date,
                            star_count=repo.star_count,
                            last_commit_date=repo.last_commit_date,
                            content_type=self._get_content_type(file_info['path'])
                        )
                        
                        doc_content.append(ExtractedContent(
                            repo=repo.full_name,
                            path=file_info['path'],
                            type='doc',
                            content=cleaned_content,
                            metadata=metadata
                        ))
                        
            except Exception as e:
                logger.debug(f"Error extracting doc file {file_info['path']}: {e}")
        
        return doc_content
    
    async def _extract_code(self, repo: GitHubRepo, files: List[Dict[str, Any]]) -> List[ExtractedContent]:
        """Extract code files."""
        code_content = []
        
        # Code file extensions
        code_extensions = {
            '.py', '.js', '.ts', '.go', '.rs', '.java', '.cpp', '.c', '.h', '.hpp',
            '.php', '.rb', '.swift', '.kt', '.scala', '.r', '.m', '.sh', '.sql',
            '.html', '.css', '.vue', '.jsx', '.tsx', '.json', '.yaml', '.yml'
        }
        
        code_files = []
        for file_info in files:
            file_ext = Path(file_info['name']).suffix.lower()
            if file_ext in code_extensions:
                code_files.append(file_info)
        
        # Process code files (sample representative files)
        sampled_files = self._sample_code_files(code_files, max_files=100)
        
        for file_info in sampled_files:
            try:
                content = await self.github_client.get_file_content(repo.full_name, file_info['path'])
                if content:
                    cleaned_content = self._clean_code_content(content, file_info['name'])
                    if cleaned_content.strip():
                        metadata = ContentMetadata(
                            repo=repo.full_name,
                            path=file_info['path'],
                            language=self._detect_file_language(file_info['name']),
                            file_size=file_info['size'],
                            last_modified=repo.last_commit_date,
                            star_count=repo.star_count,
                            last_commit_date=repo.last_commit_date,
                            content_type='code'
                        )
                        
                        code_content.append(ExtractedContent(
                            repo=repo.full_name,
                            path=file_info['path'],
                            type='code',
                            language=metadata.language,
                            content=cleaned_content,
                            metadata=metadata
                        ))
                        
            except Exception as e:
                logger.debug(f"Error extracting code file {file_info['path']}: {e}")
        
        return code_content
    
    async def _extract_issues(self, repo: GitHubRepo) -> List[ExtractedContent]:
        """Extract high-value issues from repository."""
        issue_content = []
        
        try:
            issues = await self.github_client.get_repository_issues(repo.full_name)
            
            for issue in issues:
                if issue['body'] and len(issue['body'].strip()) > 100:  # Substantial content
                    cleaned_content = self._clean_issue_content(issue)
                    
                    metadata = ContentMetadata(
                        repo=repo.full_name,
                        path=f"issues/{issue['number']}",
                        file_size=len(cleaned_content),
                        last_modified=issue['updated_at'],
                        star_count=repo.star_count,
                        last_commit_date=repo.last_commit_date,
                        content_type='issue'
                    )
                    
                    issue_content.append(ExtractedContent(
                        repo=repo.full_name,
                        path=f"issues/{issue['number']}",
                        type='doc',
                        content=cleaned_content,
                        metadata=metadata
                    ))
                    
        except Exception as e:
            logger.debug(f"Error extracting issues from {repo.full_name}: {e}")
        
        return issue_content
    
    def _clean_markdown_content(self, content: str) -> str:
        """Clean and normalize markdown content."""
        # Convert markdown to plain text while preserving structure
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables'])
        
        # Remove HTML tags but keep content
        content = re.sub(r'<[^>]+>', '', content)
        
        # Clean up common markdown artifacts
        content = re.sub(r'!\[.*?\]\(.*?\)', '', content)  # Remove images
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # Convert links to text
        content = re.sub(r'`([^`]+)`', r'\1', content)  # Remove inline code backticks
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)  # Remove header markers
        content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Remove bold markers
        content = re.sub(r'\*([^*]+)\*', r'\1', content)  # Remove italic markers
        
        # Clean up whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Multiple newlines to double
        content = re.sub(r'[ \t]+', ' ', content)  # Multiple spaces to single
        
        return content.strip()
    
    def _clean_code_content(self, content: str, filename: str) -> str:
        """Clean code content."""
        # Remove comments based on file type
        file_ext = Path(filename).suffix.lower()
        
        if file_ext in ['.py', '.sh', '.r']:
            # Remove Python/Shell/R style comments
            content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
        elif file_ext in ['.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.swift', '.kt', '.scala']:
            # Remove C-style comments
            content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        elif file_ext in ['.html', '.xml']:
            # Remove HTML comments
            content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        
        # Clean up whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        return content.strip()
    
    def _clean_issue_content(self, issue: Dict[str, Any]) -> str:
        """Clean issue content."""
        title = issue['title']
        body = issue['body'] or ''
        
        # Combine title and body
        content = f"Issue: {title}\n\n{body}"
        
        # Clean markdown
        content = self._clean_markdown_content(content)
        
        return content
    
    def _detect_file_language(self, filename: str) -> Optional[str]:
        """Detect programming language from filename."""
        ext_to_lang = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.go': 'Go',
            '.rs': 'Rust',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C',
            '.hpp': 'C++',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.r': 'R',
            '.m': 'Objective-C',
            '.sh': 'Shell',
            '.sql': 'SQL',
            '.html': 'HTML',
            '.css': 'CSS',
            '.vue': 'Vue',
            '.jsx': 'JavaScript',
            '.tsx': 'TypeScript',
            '.json': 'JSON',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.md': 'Markdown',
            '.rst': 'reStructuredText',
            '.txt': 'Text'
        }
        
        ext = Path(filename).suffix.lower()
        return ext_to_lang.get(ext)
    
    def _get_content_type(self, filepath: str) -> str:
        """Determine content type from filepath."""
        filepath_lower = filepath.lower()
        
        if 'readme' in filepath_lower:
            return 'readme'
        elif 'doc' in filepath_lower or 'wiki' in filepath_lower:
            return 'doc'
        elif filepath_lower.endswith('.md'):
            return 'doc'
        else:
            return 'code'
    
    def _sample_code_files(self, code_files: List[Dict[str, Any]], max_files: int = 100) -> List[Dict[str, Any]]:
        """Sample representative code files."""
        if len(code_files) <= max_files:
            return code_files
        
        # Prioritize important files
        priority_patterns = [
            r'main\.',
            r'index\.',
            r'app\.',
            r'server\.',
            r'client\.',
            r'config\.',
            r'setup\.',
            r'__init__\.',
            r'package\.json',
            r'requirements\.txt',
            r'Cargo\.toml',
            r'pom\.xml'
        ]
        
        priority_files = []
        regular_files = []
        
        for file_info in code_files:
            filename = file_info['name'].lower()
            is_priority = any(re.search(pattern, filename) for pattern in priority_patterns)
            
            if is_priority:
                priority_files.append(file_info)
            else:
                regular_files.append(file_info)
        
        # Take all priority files and sample from regular files
        sampled = priority_files[:max_files//4]  # Reserve 1/4 for priority
        remaining_slots = max_files - len(sampled)
        
        if remaining_slots > 0:
            # Sample regular files by language diversity
            sampled.extend(self._sample_by_language_diversity(regular_files, remaining_slots))
        
        return sampled
    
    def _sample_by_language_diversity(self, files: List[Dict[str, Any]], max_files: int) -> List[Dict[str, Any]]:
        """Sample files to maximize language diversity."""
        by_language = {}
        
        for file_info in files:
            lang = self._detect_file_language(file_info['name'])
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(file_info)
        
        sampled = []
        files_per_lang = max(1, max_files // len(by_language))
        
        for lang_files in by_language.values():
            sampled.extend(lang_files[:files_per_lang])
            if len(sampled) >= max_files:
                break
        
        return sampled[:max_files] 