import logging
import pickle
import random
import re
import time

from bs4 import BeautifulSoup
from ratelimit import limits, sleep_and_retry
from requests import Timeout, RequestException
from requests.exceptions import HTTPError
from requests_cache import CachedSession

from app.database import SupabaseDatabase
from app.model import Project
from utils.helpers import get_headers


class PyPiScrapper:
    RATE_LIMIT_CALLS = 15
    RATE_LIMIT_PERIOD = 60

    def __init__(self, url, delay_range=(3, 6), log_file="scrapper.log", cache_expiry=3600,
                 progress_file="progress.pkl"):
        self.url = url
        self.delay_range = delay_range
        self.progress_file = progress_file
        self.visited_projects = set()
        self.last_page = 1

        # logging setup
        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized PyPiScrapper")

        # session setup
        self.session = CachedSession("pypi_cache", expire_after=cache_expiry,  # expire after 1 hour
                                     allowable_methods=["GET"], allowable_codes=[200])
        self.logger.info("Initialized CachedSession with expiry of {} seconds".format(cache_expiry))

        # initialize the database client
        self.db = SupabaseDatabase()

        # load progress
        self.load_progress()

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    def fetch_page(self, url, retries=3, backoff_factor=1):
        """Fetch a page with error handling and retires"""
        headers = get_headers()

        for attempt in range(retries):
            try:
                response = self.session.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                if response.from_cache:
                    self.logger.info(f"Cache hit: {url}")
                else:
                    self.logger.debug(f"Fetched from server: {url}")

                return response.content
            except HTTPError as http_err:
                self.logger.error(f"HTTP error occurred: {http_err} -> URL: {url}")
            except Timeout:
                self.logger.warning(f"Timeout error: Retrying ({attempt + 1}/{retries}) -> URL: {url}")
            except RequestException as req_err:
                self.logger.error(f"Request error: {req_err} -> URL: {url}")

            sleep_time = backoff_factor * (2 ** attempt) + random.uniform(*self.delay_range)
            self.logger.info(f"Retrying after {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

        self.logger.error(f"Failed to fetch {url} after {retries} attempts.")
        return None

    def scrape_search_page(self, page=1):
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
            return [card['href'] for card in project_cards]

        self.logger.warning(f"Failed to fetch search page {page}")
        return []

    def scrape_project_page(self, project_url):
        """Scrape individual project page for details"""
        url = f"https://pypi.org{project_url}"
        content = self.fetch_page(url)

        if not content:
            self.logger.error(f"Failed to fetch project page: {url}")
            return None

        soup = BeautifulSoup(content, "html.parser")

        try:
            project_title = soup.find("h1", {"class": "package-header__name"}).text.strip()
        except AttributeError:
            project_title = "N/A"

        try:
            project_description = soup.find("p", {"class": "package-description__summary"}).text.strip()
        except AttributeError:
            project_description = "No description available"

        try:
            project_maintainer = soup.find("span", {"class": "sidebar-section__maintainer"}).find("a").text.strip()
        except AttributeError:
            project_maintainer = "Unknown"

        maintainer_email = None
        for link in soup.find_all("a", href=True):
            if re.match(r"mailto:.*", link.get("href")):
                maintainer_email = link.get('href')
                break

        github_link = None
        for link in soup.find_all("a", href=True):
            if re.match(r"https://github.com/.*", link.get("href")):
                github_link = link.get('href')
                break

        project = Project(project_title=project_title, project_description=project_description,
                          project_maintainer=project_maintainer, project_maintainer_email=maintainer_email,
                          github_repo=github_link)

        self.logger.info(f"Scraped project: {project.project_title}")
        return project

    def scrape_all_projects(self):
        """Scrape all projects from multiple pages"""
        page = self.last_page
        while True:  # Continuously loop until no more projects are found
            self.logger.info(f"Scraping page {page}...")
            projects = self.scrape_search_page(page)

            if not projects:
                self.logger.info(f"No more projects found on page {page}. Ending scrape.")
                break

            for project in projects:
                if project in self.visited_projects:
                    self.logger.info(f"Already scraped project {project}, skipping!")
                    continue
                project_data = self.scrape_project_page(project)

                if project_data:
                    res = self.db.insert_project(project_data)

                    if res.error:
                        self.logger.error(f"Failed to insert project {project_data.project_title}: {res.error}.")
                    else:
                        self.logger.info(f"Inserted project {project_data.project_title} into database.")

                    self.visited_projects.add(project)

            self.last_page = page  # update last scraped page
            self.save_progress()  # save progress after each page

            page += 1

            time.sleep(random.uniform(*self.delay_range))

        self.logger.info(f"Scraping completed. Total projects scraped: {len(self.visited_projects)}")

    def load_progress(self):
        """Load saved progress if available"""
        try:
            with open(self.progress_file, "rb") as f:
                data = pickle.load(f)
                self.visited_projects = set(data.get("visited_projects", []))
                self.last_page = data.get("last_page", 1)
                self.logger.info(f"Loaded progress from {self.progress_file}. Last scraped page: {self.last_page}")
        except FileNotFoundError:
            self.logger.info("No saved progress found. Starting from scratch.")
            self.visited_projects = set()
            self.last_page = 1

    def save_progress(self):
        """Save current progress to a file"""
        data = {"visited_projects": list(self.visited_projects), "last_page": self.last_page}

        with open(self.progress_file, "wb") as f:
            pickle.dump(data, f)
        self.logger.info(f"Progress saved to {self.progress_file}")
