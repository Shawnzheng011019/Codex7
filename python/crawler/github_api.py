import asyncio
import aiohttp
from github import Github
from typing import List, Optional, Dict, Any
from loguru import logger
import base64
from utils.models import GitHubRepo
from utils.config import get_config

config = get_config()


class GitHubAPIClient:
    """GitHub API client for enriching repository data."""
    
    def __init__(self, token: str):
        self.token = token
        self.github = Github(token)
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_remaining = 5000
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'Authorization': f'Bearer {self.token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Codex7-RAG-System'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def enrich_repository(self, repo: GitHubRepo) -> GitHubRepo:
        """Enrich repository data using GitHub API."""
        try:
            await self._check_rate_limit()
            
            github_repo = self.github.get_repo(repo.full_name)
            
            # Get README content
            readme_content = None
            try:
                readme = github_repo.get_readme()
                readme_content = base64.b64decode(readme.content).decode('utf-8')
            except Exception as e:
                logger.debug(f"Could not get README for {repo.full_name}: {e}")
            
            # Update repository data
            enriched_repo = GitHubRepo(
                id=github_repo.id,
                name=github_repo.name,
                full_name=github_repo.full_name,
                description=github_repo.description or repo.description,
                url=github_repo.html_url,
                clone_url=github_repo.clone_url,
                star_count=github_repo.stargazers_count,
                fork_count=github_repo.forks_count,
                language=github_repo.language or repo.language,
                topics=list(github_repo.get_topics()),
                last_commit_date=github_repo.pushed_at.isoformat() if github_repo.pushed_at else "",
                created_at=github_repo.created_at.isoformat() if github_repo.created_at else "",
                updated_at=github_repo.updated_at.isoformat() if github_repo.updated_at else "",
                size=github_repo.size,
                default_branch=github_repo.default_branch,
                license=github_repo.license.name if github_repo.license else None,
                readme=readme_content
            )
            
            logger.info(f"Enriched repository: {repo.full_name}")
            return enriched_repo
            
        except Exception as e:
            logger.error(f"Error enriching repository {repo.full_name}: {e}")
            return repo  # Return original repo if enrichment fails
    
    async def get_repository_files(self, full_name: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """Get all files from a repository."""
        files = []
        
        try:
            await self._check_rate_limit()
            github_repo = self.github.get_repo(full_name)
            
            await self._collect_files_recursive(github_repo, "", files, max_depth, 0)
            
        except Exception as e:
            logger.error(f"Error getting files for {full_name}: {e}")
        
        return files
    
    async def _collect_files_recursive(self, repo, path: str, files: List[Dict[str, Any]], 
                                     max_depth: int, current_depth: int):
        """Recursively collect files from repository."""
        if current_depth >= max_depth:
            return
        
        try:
            contents = repo.get_contents(path)
            
            if not isinstance(contents, list):
                contents = [contents]
            
            for content in contents:
                if content.type == "file":
                    if self._should_include_file(content.name, content.size):
                        files.append({
                            'name': content.name,
                            'path': content.path,
                            'size': content.size,
                            'sha': content.sha,
                            'download_url': content.download_url,
                            'type': content.type
                        })
                elif content.type == "dir" and not self._should_skip_directory(content.name):
                    await self._collect_files_recursive(repo, content.path, files, max_depth, current_depth + 1)
                    
        except Exception as e:
            logger.debug(f"Error reading directory {path}: {e}")
    
    async def get_file_content(self, full_name: str, file_path: str) -> Optional[str]:
        """Get content of a specific file."""
        try:
            await self._check_rate_limit()
            github_repo = self.github.get_repo(full_name)
            file_content = github_repo.get_contents(file_path)
            
            if file_content.encoding == 'base64':
                return base64.b64decode(file_content.content).decode('utf-8')
            else:
                return file_content.content
                
        except Exception as e:
            logger.debug(f"Error getting file content {file_path} from {full_name}: {e}")
            return None
    
    async def get_repository_issues(self, full_name: str, state: str = 'closed', 
                                  sort: str = 'comments', max_issues: int = 20) -> List[Dict[str, Any]]:
        """Get high-value issues from repository."""
        issues = []
        
        try:
            await self._check_rate_limit()
            github_repo = self.github.get_repo(full_name)
            
            repo_issues = github_repo.get_issues(
                state=state,
                sort=sort,
                direction='desc'
            )
            
            for i, issue in enumerate(repo_issues):
                if i >= max_issues:
                    break
                    
                # Only include issues with significant engagement
                if issue.comments >= 5 or issue.reactions['total_count'] >= 10:
                    issues.append({
                        'id': issue.id,
                        'number': issue.number,
                        'title': issue.title,
                        'body': issue.body,
                        'state': issue.state,
                        'comments': issue.comments,
                        'reactions': issue.reactions,
                        'created_at': issue.created_at.isoformat(),
                        'updated_at': issue.updated_at.isoformat(),
                        'labels': [label.name for label in issue.labels]
                    })
                    
        except Exception as e:
            logger.error(f"Error getting issues for {full_name}: {e}")
        
        return issues
    
    async def _check_rate_limit(self):
        """Check and handle GitHub API rate limiting."""
        try:
            rate_limit = self.github.get_rate_limit()
            self.rate_limit_remaining = rate_limit.core.remaining
            
            if self.rate_limit_remaining < 10:
                reset_time = rate_limit.core.reset.timestamp()
                wait_time = reset_time - asyncio.get_event_loop().time()
                
                if wait_time > 0:
                    logger.warning(f"Rate limit low ({self.rate_limit_remaining}), waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time + 1)
                    
        except Exception as e:
            logger.debug(f"Error checking rate limit: {e}")
            # If we can't check rate limit, add a small delay
            await asyncio.sleep(0.1)
    
    def _should_include_file(self, filename: str, size: int) -> bool:
        """Check if file should be included in processing."""
        max_size = config.max_file_size_mb * 1024 * 1024
        if size > max_size:
            return False
        
        # Documentation extensions
        doc_extensions = ['.md', '.rst', '.txt', '.adoc', '.wiki']
        
        # Code extensions
        code_extensions = [
            '.py', '.js', '.ts', '.go', '.rs', '.java', '.cpp', '.c', '.h', '.hpp',
            '.php', '.rb', '.swift', '.kt', '.scala', '.r', '.m', '.sh', '.sql',
            '.html', '.css', '.vue', '.jsx', '.tsx', '.json', '.yaml', '.yml'
        ]
        
        filename_lower = filename.lower()
        
        # Always include README files
        if filename_lower.startswith('readme'):
            return True
        
        # Check extensions
        for ext in doc_extensions + code_extensions:
            if filename_lower.endswith(ext):
                return True
        
        return False
    
    def _should_skip_directory(self, dirname: str) -> bool:
        """Check if directory should be skipped."""
        skip_dirs = {
            '.git', '.github', '.vscode', '.idea', 'node_modules', 'dist', 'build',
            'target', '.next', '.nuxt', '__pycache__', '.pytest_cache', 'vendor',
            'packages', 'deps', '.deps', 'coverage', '.coverage', '.nyc_output',
            'logs', 'log', '.log', 'tmp', 'temp', 'cache', '.cache', 'public',
            'static', 'assets', 'img', 'images', 'fonts', '.DS_Store'
        }
        
        return dirname.lower() in skip_dirs or dirname.startswith('.') 