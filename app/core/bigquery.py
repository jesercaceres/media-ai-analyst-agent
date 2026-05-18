import os
from functools import lru_cache
from typing import Any

from google.cloud import bigquery
from google.oauth2 import service_account

from app.core.config import get_settings


@lru_cache
def get_bq_client() -> bigquery.Client:
    settings = get_settings()

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials

    credentials = service_account.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=[
            "https://www.googleapis.com/auth/bigquery",
            "https://www.googleapis.com/auth/cloud-platform",
        ],
    )
    return bigquery.Client(project=settings.gcp_project_id, credentials=credentials)


def run_query(sql: str, params: list[bigquery.ScalarQueryParameter] | None = None) -> list[dict[str, Any]]:
    """Execute a parameterized BigQuery query and return rows as dicts."""
    client = get_bq_client()

    job_config = bigquery.QueryJobConfig()
    if params:
        job_config.query_parameters = params

    query_job = client.query(sql, job_config=job_config)
    result = query_job.result()

    return [dict(row) for row in result]
