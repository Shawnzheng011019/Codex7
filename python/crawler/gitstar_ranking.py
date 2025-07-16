import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Optional
from loguru import logger
import re
from utils.models import GitHubRepo, CrawlResult
from utils.config import get_config

config = get_config()


class GitStarRankingCrawler:
    """Crawler for gitstar-ranking.com to get top GitHub repositories."""
    
    def __init__(self):
        self.base_url = "https://gitstar-ranking.com/repositories"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def crawl_top_repositories(self, max_repos: int = 100) -> CrawlResult:
        """Crawl top repositories from gitstar-ranking.com."""
        repos: List[GitHubRepo] = []
        errors: List[str] = []
        page = 1
        
        logger.info(f"Starting to crawl top {max_repos} repositories from GitStar Ranking")
        
        try:
            while len(repos) < max_repos:
                page_url = f"{self.base_url}?page={page}"
                logger.info(f"Crawling page {page}: {page_url}")
                
                try:
                    async with self.session.get(page_url) as response:
                        if response.status != 200:
                            error_msg = f"Failed to fetch page {page}, status: {response.status}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            break
                            
                        html = await response.text()
                        page_repos = self._parse_repositories_from_html(html)
                        
                        if not page_repos:
                            logger.info(f"No repositories found on page {page}, stopping")
                            break
                            
                        for repo in page_repos:
                            if len(repos) < max_repos:
                                repos.append(repo)
                            
                        logger.info(f"Found {len(page_repos)} repos on page {page}, total: {len(repos)}")
                        
                except Exception as e:
                    error_msg = f"Error crawling page {page}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    break
                
                page += 1
                # Be respectful to the server
                await asyncio.sleep(1)
                
        except Exception as e:
            error_msg = f"General crawling error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        logger.info(f"Crawling completed. Found {len(repos)} repositories with {len(errors)} errors")
        
        return CrawlResult(
            repos=repos[:max_repos],
            total_found=len(repos),
            processed_count=len(repos),
            errors=errors
        )
    
    def _parse_repositories_from_html(self, html: str) -> List[GitHubRepo]:
        """Parse repositories from HTML content."""
        repos: List[GitHubRepo] = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find repository entries using correct selector
        repo_elements = soup.find_all('a', class_='list-group-item paginated_item')
        
        logger.debug(f"Found {len(repo_elements)} repository elements")
        
        for element in repo_elements:
            try:
                repo = self._parse_repository_from_element(element)
                if repo:
                    repos.append(repo)
                    logger.debug(f"Successfully parsed: {repo.full_name} ({repo.star_count} stars)")
            except Exception as e:
                logger.debug(f"Error parsing repository element: {e}")
                continue
        
        return repos
    
    def _parse_repository_from_element(self, element) -> Optional[GitHubRepo]:
        """Parse a single repository from HTML element."""
        try:
            # Extract repository name from the href attribute
            href = element.get('href')
            if not href or not href.startswith('/'):
                return None
            
            # href format: "/owner/repo"
            repo_path = href.strip('/')
            if '/' not in repo_path:
                return None
            
            owner, repo_name = repo_path.split('/', 1)
            
            # Filter out repositories containing "996" in the name
            if '996' in repo_name.lower() or '996' in owner.lower():
                logger.debug(f"Filtered out repository containing '996': {owner}/{repo_name}")
                return None
            
            # Extract stars count from span with class 'stargazers_count'
            stars_element = element.find('span', class_='stargazers_count')
            if not stars_element:
                logger.debug(f"No stars element found for {owner}/{repo_name}")
                return None
            
            # Get the text content and clean it
            stars_text = stars_element.get_text().strip()
            # Remove the star icon and any whitespace
            stars_text = re.sub(r'[^\d,]', '', stars_text)
            # Remove commas for parsing
            stars_text = stars_text.replace(',', '')
            
            try:
                stars = int(stars_text) if stars_text else 0
            except ValueError:
                logger.debug(f"Failed to parse stars: '{stars_element.get_text()}'")
                stars = 0
            
            # Extract description from div with class 'repo-description'
            description_element = element.find('div', class_='repo-description')
            description = ""
            if description_element:
                # Use title attribute first, fallback to text content
                description = description_element.get('title', '')
                if not description:
                    description = description_element.get_text().strip()
            
            # Extract language from div with class 'repo-language'
            language_element = element.find('div', class_='repo-language')
            language = ""
            if language_element:
                lang_span = language_element.find('span')
                if lang_span:
                    language = lang_span.get_text().strip()
            
            # Create GitHubRepo object with all required fields
            return GitHubRepo(
                id=0,  # Will be enriched by GitHub API later
                name=repo_name,
                full_name=f"{owner}/{repo_name}",
                description=description,
                url=f"https://github.com/{owner}/{repo_name}",
                clone_url=f"https://github.com/{owner}/{repo_name}.git",
                star_count=stars,
                fork_count=0,  # Will be enriched by GitHub API later
                language=language,
                topics=[],
                last_commit_date="",  # Will be enriched by GitHub API later
                created_at="",  # Will be enriched by GitHub API later
                updated_at="",  # Will be enriched by GitHub API later
                size=0,  # Will be enriched by GitHub API later
                default_branch="main",  # Will be enriched by GitHub API later
                license=None,
                readme=None
            )
            
        except Exception as e:
            logger.debug(f"Error parsing repository element: {e}")
            return None
 