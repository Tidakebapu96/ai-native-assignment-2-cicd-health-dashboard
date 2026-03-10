import httpx
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pipeline import Pipeline
from app.schemas.pipeline import PipelineCreate

class GitHubService:
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CI-CD-Dashboard/1.0"
        }

    async def get_workflow_runs(self, page: int = 1, per_page: int = 100) -> dict:
        if not all([settings.GITHUB_OWNER, settings.GITHUB_REPO]):
            raise Exception("GitHub configuration incomplete")
        url = f"{self.base_url}/repos/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}/actions/runs"
        params = {"page": page, "per_page": per_page}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self.headers, params=params, timeout=30.0)
            resp.raise_for_status()
            return resp.json()

    def parse_workflow_run(self, run_data: dict) -> PipelineCreate:
        started_at = datetime.fromisoformat(run_data["run_started_at"].replace("Z", "+00:00")) if run_data.get("run_started_at") else None
        completed_at = datetime.fromisoformat(run_data["updated_at"].replace("Z", "+00:00")) if run_data["status"] == "completed" else None
        duration = int((completed_at - started_at).total_seconds()) if started_at and completed_at else None

        return PipelineCreate(
            github_run_id=run_data["id"],
            workflow_name=run_data["name"],
            status=run_data["status"],
            conclusion=run_data.get("conclusion"),
            branch=run_data.get("head_branch"),
            commit_sha=run_data.get("head_sha"),
            commit_message=run_data.get("head_commit", {}).get("message"),
            actor=run_data.get("actor", {}).get("login"),
            started_at=started_at,
            completed_at=completed_at,
            duration=duration,
            html_url=run_data["html_url"],
            logs_url=run_data["logs_url"]
        )

    async def sync_workflow_runs(self, db: Session) -> list[Pipeline]:
        synced_pipelines: list[Pipeline] = []
        page = 1
        while True:
            try:
                runs_data = await self.get_workflow_runs(page=page)
                runs = runs_data.get("workflow_runs", [])
                if not runs:
                    break
                
                for run in runs:
                    try:
                        pipeline_data = self.parse_workflow_run(run)
                        existing = db.query(Pipeline).filter(Pipeline.github_run_id == pipeline_data.github_run_id).first()
                        if existing:
                            if existing.status != pipeline_data.status or existing.conclusion != pipeline_data.conclusion:
                                for key, value in pipeline_data.model_dump(exclude_unset=True).items():
                                    setattr(existing, key, value)
                                synced_pipelines.append(existing)
                        else:
                            new_pipeline = Pipeline(**pipeline_data.model_dump())
                            db.add(new_pipeline)
                            # We must flush to get the ID for the alert table foreign key
                            db.flush()
                            db.refresh(new_pipeline)
                            synced_pipelines.append(new_pipeline)
                    except Exception as e:
                        print(f"[WARN] Failed to parse or add run {run.get('id')}: {e}")

                db.commit()
                if len(runs) < 100:
                    break
                page += 1
            except Exception as e:
                print(f"[ERROR] Failed to fetch page {page} from GitHub: {e}")
                db.rollback()
                break # Stop sync on page failure
        return synced_pipelines
