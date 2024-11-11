import os

from ratelimit import limits, sleep_and_retry
from supabase import create_client, Client

from app.model import Project


class SupabaseDatabase:
    SUPABASE_RATE_LIMIT_CALLS = 5
    SUPABASE_RATE_LIMIT_PERIOD = 1

    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise Exception("Please set SUPABASE_URL and SUPABASE_KEY environment variable")

        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)

    @sleep_and_retry
    @limits(calls=SUPABASE_RATE_LIMIT_CALLS, period=SUPABASE_RATE_LIMIT_PERIOD)
    def insert_project(self, project: Project):
        data = {"project_title": project.project_title, "project_description": project.project_description,
                "project_maintainer": project.project_maintainer,
                "project_maintainer_email": project.project_maintainer_email, "github_repo": project.github_repo}

        res = self.supabase.table("projects").insert(data).execute()
        if res.error:
            print(f"Error inserting project: {res.error}")

        return res

    def get_projects(self):
        res = self.supabase.table("projects").select("*").execute()

        if res.error:
            print(f"Error fetching projects: {res.error}")
            return []

        return res.data
