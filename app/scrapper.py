import json
import logging
import os
import random
import time
from typing import Set

from bs4 import BeautifulSoup
from ratelimit import limits, sleep_and_retry
from requests import Timeout, RequestException
from requests.exceptions import HTTPError
from requests_cache import CachedSession

from app.database import SupabaseDatabase
from app.github_api import GitHubAPI
from app.model import Project
from utils.helpers import get_headers


class PyPiScrapper:
    RATE_LIMIT_CALLS = 15
    RATE_LIMIT_PERIOD = 60

    def __init__(
        self,
        url,
        delay_range: tuple = (3, 6),
        cache_expiry: int = 3600,
        progress_file: str = "progress.json",
    ):
        self.url = url
        self.delay_range = delay_range
        self.progress_file = progress_file
        self.visited_projects: Set[str] = set()
        self.last_page = 1

        # initialize logging
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized PyPiScrapper")

        # session setup with caching
        self.session = CachedSession(
            cache_name="pypi_cache",
            expire_after=cache_expiry,  # expire after 1 hour
            allowable_methods=["GET"],
            allowable_codes=[200],
        )
        self.logger.info(
            f"Initialized CachedSession with expiry of {cache_expiry} seconds"
        )

        # initialize the database client
        self.db = SupabaseDatabase()

        # initialize GitHub API client
        self.github_api = GitHubAPI(cache_expiry=cache_expiry)

        # load progress
        self.load_progress()

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    def fetch_page(self, url: str, retries: int = 3, backoff_factor: int = 1):
        """Fetch a page with error handling and retires"""
        headers = get_headers()

        for attempt in range(retries):
            try:
                response = self.session.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                if response.from_cache:
                    self.logger.debug(f"Cache hit: {url}")
                else:
                    self.logger.debug(f"Fetched from server: {url}")

                return response.content
            except HTTPError as http_err:
                self.logger.error(f"HTTP error occurred: {http_err} -> URL: {url}")
                break
            except Timeout:
                self.logger.warning(
                    f"Timeout error: Retrying ({attempt + 1}/{retries}) -> URL: {url}"
                )
            except RequestException as req_err:
                self.logger.error(f"Request error: {req_err} -> URL: {url}")
                break

            sleep_time = backoff_factor * (2**attempt) + random.uniform(
                *self.delay_range
            )
            self.logger.info(f"Retrying after {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

        self.logger.error(f"Failed to fetch {url} after {retries} attempts.")
        return None

    def scrape_search_page(self, page: int = 1):
        """Scrape PyPi search page for project links"""
        url = f"{self.url}&page={page}"
        content = self.fetch_page(url)

        if content:
            soup = BeautifulSoup(content, "html.parser")
            project_cards = soup.find_all("a", {"class": "package-snippet"})

            # If no project cards are found, thus reached last page
            if not project_cards:
                self.logger.info(f"No projects found on page {page}.")
                return []

            time.sleep(random.uniform(*self.delay_range))
            return [card["href"] for card in project_cards]

        self.logger.warning(f"Failed to fetch search page {page}")
        return []

    def scrape_project_page(self, project_url: str):
        """Scrape individual project page for details"""
        url = f"https://pypi.org{project_url}"
        content = self.fetch_page(url)

        if not content:
            self.logger.error(f"Failed to fetch project page: {url}")
            return None

        soup = BeautifulSoup(content, "html.parser")

        project_title_tag = soup.find("h1", {"class": "package-header__name"})
        project_title = project_title_tag.text.strip() if project_title_tag else "N/A"

        project_description_tag = soup.find(
            "p", {"class": "package-description__summary"}
        )
        project_description = (
            project_description_tag.text.strip()
            if project_title_tag
            else "No description available"
        )

        project_maintainer_tag = soup.find(
            "span", {"class": "sidebar-section__maintainer"}
        )
        if project_maintainer_tag and project_title_tag.find("a"):
            project_maintainer = project_maintainer_tag.find("a").text.strip()
        else:
            project_maintainer = "Unknown"

        project_maintainer_email = None
        for link in soup.find_all("a", href=True):
            href = link.get("href")
            if href and href.startswith("mailto:"):
                project_maintainer_email = href[7:]  # Remove 'mailto:'
                break

        project_github_repo = None
        project_urls = soup.find_all("a", {"class": "vertical-tabs__tabs"}, href=True)
        for project_url in project_urls:
            href = project_url.get("href", "").lower()
            if "github.com" in href:
                project_github_repo = href
                break

        if not project_github_repo:
            for project_url in soup.find_all("a", href=True):
                href = project_url.get("href", "").lower()
                if "github.com" in href:
                    project_github_repo = href
                    break

        repo_name = None
        repo_description = None
        repo_html_url = None
        repo_stargazers_count = 0
        repo_forks_count = 0
        repo_open_issues_count = 0
        repo_language = None
        repo_updated_at = None
        repo_created_at = None
        repo_watchers_count = 0

        if project_github_repo:
            repo_data = self.github_api.get_repo_details(project_github_repo)
            if repo_data:
                repo_name = repo_data.get("name")
                repo_description = repo_data.get("description")
                repo_html_url = repo_data.get("html_url")
                repo_stargazers_count = repo_data.get("stargazers_count", 0)
                repo_forks_count = repo_data.get("forks_count", 0)
                repo_open_issues_count = repo_data.get("open_issues_count", 0)
                repo_language = repo_data.get("language")
                repo_updated_at = repo_data.get("updated_at")
                repo_created_at = repo_data.get("created_at")
                repo_watchers_count = repo_data.get("watchers_count", 0)
            else:
                self.logger.warning(
                    f"Failed to get GitHub details for {project_github_repo}"
                )

        project = Project(
            project_title=project_title,
            project_description=project_description,
            project_maintainer=project_maintainer,
            project_maintainer_email=project_maintainer_email,
            project_github_repo=project_github_repo,
            repo_name=repo_name,
            repo_description=repo_description,
            repo_html_url=repo_html_url,
            repo_stargazers_count=repo_stargazers_count,
            repo_forks_count=repo_forks_count,
            repo_open_issues_count=repo_open_issues_count,
            repo_language=repo_language,
            repo_updated_at=repo_updated_at,
            repo_created_at=repo_created_at,
            repo_watchers_count=repo_watchers_count,
        )

        self.logger.info(f"Scraped project: {project.project_title}")
        return project

    def scrape_all_projects(self):
        """Scrape all projects from multiple pages"""
        page = self.last_page
        while True:  # Continuously loop until no more projects are found
            self.logger.info(f"Scraping page {page}...")
            projects = self.scrape_search_page(page)

            if not projects:
                self.logger.info(
                    f"No more projects found on page {page}. Ending scrape."
                )
                break

            for project in projects:
                if project in self.visited_projects:
                    self.logger.info(f"Already scraped project {project}, skipping!")
                    continue

                project_data = self.scrape_project_page(project)

                if project_data:
                    res = self.db.insert_project(project_data)

                    if res.error:
                        self.logger.error(
                            f"Failed to insert project {project_data.project_title}: {res.error}."
                        )
                    else:
                        self.logger.info(
                            f"Inserted project {project_data.project_title} into database."
                        )

                    self.visited_projects.add(project)
                else:
                    self.logger.warning(
                        f"Project data for {project} is None, skipping."
                    )

            self.last_page = page  # update last scraped page
            self.save_progress()  # save progress after each page

            page += 1

            time.sleep(random.uniform(*self.delay_range))

        self.logger.info(
            f"Scraping completed. Total projects scraped: {len(self.visited_projects)}"
        )

    def load_progress(self):
        """Load saved progress if available"""
        try:
            with open(self.progress_file, "r") as file:
                data = json.load(file)
                self.visited_projects = set(data.get("visited_projects", []))
                self.last_page = data.get("last_page", 1)
                self.logger.info(
                    f"Loaded progress from {self.progress_file}. Last scraped page: {self.last_page}"
                )
        except FileNotFoundError:
            self.logger.info("No saved progress found. Starting from scratch.")
            self.visited_projects = set()
            self.last_page = 1
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding progress file: {e}")
            self.visited_projects = set()
            self.last_page = 1

    def save_progress(self):
        """Save current progress to a file"""
        data = {
            "visited_projects": list(self.visited_projects),
            "last_page": self.last_page,
        }
        temp_file = self.progress_file + ".tmp"

        try:
            with open(temp_file, "w") as file:
                json.dump(data, file)
            os.replace(temp_file, self.progress_file)
            self.logger.info(f"Progress saved to {self.progress_file}")
        except Exception as e:
            self.logger.error(f"Failed to save progress: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
