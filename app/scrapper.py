import re

import requests
from bs4 import BeautifulSoup


class PyPiScrapper:
    def __init__(self, url):
        self.url = url
        self.projects = []

    def scrape_search_page(self, page=1):
        """Scrape PyPi search page for project links"""
        url = f"{self.url}&page={page}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        project_cards = soup.find_all("a", {"class": "package-snippet"})
        return [card['href'] for card in project_cards]

    def scrape_project_page(self, project_url):
        """Scrape individual project page for details"""
        response = requests.get(f"https://pypi.org{project_url}")
        soup = BeautifulSoup(response.content, "html.parser")

        project_title = soup.find("h1", {"class": "package-header__name"}).text.strip()
        project_description = soup.find("p", {"class": "package-description__summary"}).text.strip()

        project_maintainer = soup.find("span", {"class": "sidebar-section__maintainer"})
        project_maintainer = project_maintainer.find("a").text.strip()

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
