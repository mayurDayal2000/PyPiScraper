import logging
import os

from ratelimit import limits, sleep_and_retry
from supabase import create_client, Client

from app.model import Project


class SupabaseDatabase:
    SUPABASE_RATE_LIMIT_CALLS = 5
    SUPABASE_RATE_LIMIT_PERIOD = 1

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            self.logger.error(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set."
            )
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_KEY environment variables must be set."
            )

        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.logger.info("Initialized Supabase client.")

    @sleep_and_retry
    @limits(calls=SUPABASE_RATE_LIMIT_CALLS, period=SUPABASE_RATE_LIMIT_PERIOD)
    def insert_project(self, project: Project):
        data = {
            "project_title": project.project_title,
            "project_description": project.project_description,
            "project_maintainer": project.project_maintainer,
            "project_maintainer_email": project.project_maintainer_email,
            "project_github_repo": project.project_github_repo,
        }

        try:
            res = self.supabase.table("projects").insert(data).execute()
            if res.error:
                self.logger.error(f"Error inserting project: {res.error}")
                return None
            self.logger.info(f"Successfully inserted project: {project.project_title}")
            return res.data
        except Exception as e:
            self.logger.error(f"Exception occurred while inserting project: {e}")
            return None

    def get_projects(self):
        try:
            res = self.supabase.table("projects").select("*").execute()
            if res.error:
                self.logger.error(f"Error fetching projects: {res.error}")
                return []
            return res.data
        except Exception as e:
            self.logger.error(f"Exception occurred while fetching projects: {e}")
            return []
