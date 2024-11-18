from dataclasses import dataclass
from typing import Optional


@dataclass
class Project:
    project_title: str
    project_description: str
    project_maintainer: str
    project_maintainer_email: Optional[str] = None
    project_github_repo: Optional[str] = None
