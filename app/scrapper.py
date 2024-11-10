import random
import re
import time

import requests
from bs4 import BeautifulSoup
from requests import Timeout, RequestException
from requests.exceptions import HTTPError


class PyPiScrapper:
    def __init__(self, url):
        self.url = url
        self.projects = []

    def fetch_page(self, url, retries=3):
        """Fetch a page with error handling and retires"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}

        for attempt in range(retries):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.content
            except HTTPError as http_err:
                print(f"HTTP error occurred: {http_err} -> URL: {url}")
            except Timeout:
                print(f"Timeout error: Retrying ({attempt + 1}/{retries}) -> URL: {url}")
            except RequestException as req_err:
                print(f"Request error: {req_err} -> URL: {url}")
            time.sleep(random.uniform(1, 3))  # delay between retries
        return None

    def scrape_search_page(self, page=1):
        """Scrape PyPi search page for project links"""
        url = f"{self.url}&page={page}"
        content = self.fetch_page(url)

        if content:
            soup = BeautifulSoup(content, "html.parser")
            project_cards = soup.find_all("a", {"class": "package-snippet"})
            return [card['href'] for card in project_cards]
        return []

    def scrape_project_page(self, project_url):
        """Scrape individual project page for details"""
        url = f"https://pypi.org{project_url}"
        content = self.fetch_page(url)

        if not content:
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

        return {"project_title": project_title, "project_description": project_description,
                "project_maintainer": project_maintainer, "project_maintainer_email": maintainer_email,
                "github_repo": github_link}

    def scrape_all_projects(self):
        """Scrape all projects from multiple pages"""
        page = 1
        while page == 1:
            print(f"Scraping page {page}...")
            projects = self.scrape_search_page(page)

            if not projects:
                break

            for project in projects:
                project_data = self.scrape_project_page(project)

                if project_data:
                    self.projects.append(project_data)

            page += 1

        print("Scraping completed. ")
