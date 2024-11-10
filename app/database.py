import os

from supabase import create_client, Client

from app.model import Project

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL and not SUPABASE_KEY:
    raise Exception("Please set SUPABASE_URL and SUPABASE_KEY environment variable")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_project(project: Project):
    data = {
        "project_title": project.project_title,
        "project_description": project.project_description,
        "project_maintainer": project.project_maintainer,
        "project_maintainer_email": project.project_maintainer_email,
        "github_repo": project.github_repo
    }

    res = supabase.table("projects").insert(data).execute()
    if res.error:
        print(f"Error inserting project: {res.error}")

    return res


def get_projects():
    res = supabase.table("projects").select("*").execute()

    if res.error:
        print(f"Error fetching projects: {res.error}")
        return []

    return res.data
