import json
import logging
import os
import random
import time

import urllib3.util
from ratelimit import sleep_and_retry, limits
from requests import Timeout, RequestException
from requests.exceptions import HTTPError
from requests_cache import CachedSession

from utils.helpers import get_headers


class GitHubAPI:
    RATE_LIMIT_CALLS = 5000
    RATE_LIMIT_PERIOD = 3600

    def __init__(self, cache_expiry: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initialized GitHubAPI")

        self.session = CachedSession(
            cache_name="github_cache",
            expire_after=cache_expiry,
            allowable_methods=["GET"],
            allowable_codes=[200],
        )

        self.logger.info(
            f"Initialized CachedSession with expiry of {cache_expiry} seconds"
        )

        self.github_token = os.environ.get("GITHUB_TOKEN")
        if not self.github_token:
            self.logger.warning(
                "No GITHUB_TOKEN found in environment variable. Using unauthenticated requests."
            )
            self.RATE_LIMIT_CALLS = 60

    @sleep_and_retry
    @limits(calls=RATE_LIMIT_CALLS, period=RATE_LIMIT_PERIOD)
    def fetch_github_api(self, url: str, retries: int = 3, backoff_factor: int = 1):
        """Fetch a GitHub api url with error handling and retries"""
        headers = get_headers()
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
            headers["Accept"] = "application/vnd.github.v3+json"
        else:
            headers["Accept"] = "application/vnd.github.v3+json"

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
                status_code = http_err.response.status_code

                self.logger.error(
                    f"HTTP error {status_code} occurred: {http_err} -> URL: {url}"
                )

                if status_code == 404:
                    # Not found; no point in retrying
                    break
                elif status_code == 403:
                    # Rate limit exceeded
                    self.logger.error("GitHub API rate limit exceeded.")
                    time.sleep(60)  # Wait a minute before retrying
                else:
                    self.logger.error(f"HTTP error {status_code}: {http_err}")

            except Timeout:
                self.logger.warning(
                    f"Timeout error: Retrying ({attempt + 1}/{retries}) -> URL: {url}"
                )

            except RequestException as req_err:
                self.logger.error(f"Request error: {req_err} -> URL: {url}")
                break  # Non-recoverable error

            sleep_time = backoff_factor * (2**attempt) + random.uniform(3, 6)
            self.logger.info(f"Retrying after {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

        self.logger.error(f"Failed to fetch {url} after {retries} attempts.")
        return None

    @staticmethod
    def extract_owner_repo(github_url: str):
        """Extract owner and repo from a GitHub URL."""
        parsed_url = urllib3.util.parse_url(github_url)
        path_parts = parsed_url.path.strip("/").split("/")

        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1].split(".git")[0]  # Remove '.git' if present
            return owner, repo
        return None, None

    def get_repo_details(self, github_url: str):
        """Get GitHub repository details using the GitHub API."""
        owner, repo = self.extract_owner_repo(github_url)

        if not owner or not repo:
            self.logger.warning(f"Invalid GitHub URL: {github_url}")
            return None

        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        content = self.fetch_github_api(api_url)

        if not content:
            self.logger.error(f"Failed to fetch GitHub API for {github_url}")
            return None

        try:
            repo_data = json.loads(content)

            if "message" in repo_data and repo_data["message"] == "Not Found":
                self.logger.warning(f"Repository not found: {github_url}")
                return None
            return repo_data

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON response for {github_url}: {e}")
            return None
