from dataclasses import dataclass


@dataclass
class Project:
    project_title: str
    project_description: str
    project_maintainer: str
    project_maintainer_email: str
    github_repo: str
