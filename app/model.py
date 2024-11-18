from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    project_title: str
    project_description: str
    project_maintainer: str
    project_maintainer_email: Optional[str] = None
    project_github_repo: Optional[str] = None

    repo_name: Optional[str] = None
    repo_description: Optional[str] = None
    repo_html_url: Optional[str] = None
    repo_stargazers_count: int = 0
    repo_forks_count: int = 0
    repo_open_issues_count: int = 0
    repo_language: Optional[str] = None
    repo_updated_at: Optional[str] = None
    repo_created_at: Optional[str] = None
    repo_watchers_count: int = 0
