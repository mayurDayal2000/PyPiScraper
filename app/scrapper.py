import logging
import random
import re
import time

import requests
from bs4 import BeautifulSoup
from requests import Timeout, RequestException
from requests.exceptions import HTTPError

from utils.helpers import get_headers


class PyPiScrapper:
    def __init__(self, url, rate_limit=15, delay_range=(3, 6), log_file="scrapper.log"):
        self.url = url
        self.projects = []
        self.rate_limit = rate_limit
        self.delay_range = delay_range
        self.requests_made = 0
        self.start_time = time.time()

        logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized PyPiScrapper")

    def rate_limit_check(self):
        """Rate limit control to ensure we don't exceed the set rate limit"""
        if self.requests_made >= self.rate_limit:
            elapsed_time = time.time() - self.start_time
            if elapsed_time < 60:
                sleep_time = 60 - elapsed_time
                self.logger.info(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds.")
                time.sleep(sleep_time)

            self.requests_made = 0
            self.start_time = time.time()

    def fetch_page(self, url, retries=3):
        """Fetch a page with error handling and retires"""
        headers = get_headers()
        self.rate_limit_check()

        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                self.requests_made += 1
                self.logger.debug(f"Successfully fetched {url}")
                return response.content
            except HTTPError as http_err:
                self.logger.error(f"HTTP error occurred: {http_err} -> URL: {url}")
            except Timeout:
                self.logger.warning(f"Timeout error: Retrying ({attempt + 1}/{retries}) -> URL: {url}")
            except RequestException as req_err:
                self.logger.error(f"Request error: {req_err} -> URL: {url}")

            time.sleep(random.uniform(*self.delay_range))  # delay between retries

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

        self.logger.info(f"Scraped project: {project_title}")
        return {"project_title": project_title, "project_description": project_description,
                "project_maintainer": project_maintainer, "project_maintainer_email": maintainer_email,
                "github_repo": github_link}

    def scrape_all_projects(self):
        """Scrape all projects from multiple pages"""
        page = 1
        while True:  # Continuously loop until no more projects are found
            self.logger.info(f"Scraping page {page}...")
            projects = self.scrape_search_page(page)

            if not projects:
                self.logger.info(f"No more projects found on page {page}. Ending scrape.")
                break

            for project in projects:
                project_data = self.scrape_project_page(project)

                if project_data:
                    self.projects.append(project_data)

            page += 1

            time.sleep(random.uniform(*self.delay_range))

        self.logger.info(f"Scraping completed. Total projects scraped: {len(self.projects)}")
