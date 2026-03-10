from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class PipelineBase(BaseModel):
    workflow_name: str = Field(..., description="Name of the workflow")
    status: str = Field(..., description="Current status of the pipeline")
    conclusion: Optional[str] = Field(None, description="Conclusion of the pipeline run")
    branch: Optional[str] = Field(None, description="Branch name")
    commit_sha: Optional[str] = Field(None, description="Commit SHA")
    commit_message: Optional[str] = Field(None, description="Commit message")
    actor: Optional[str] = Field(None, description="User who triggered the pipeline")

class PipelineCreate(PipelineBase):
    github_run_id: int = Field(..., description="GitHub Actions run ID")
    started_at: Optional[datetime] = Field(None, description="Pipeline start time")
    completed_at: Optional[datetime] = Field(None, description="Pipeline completion time")
    duration: Optional[int] = Field(None, description="Duration in seconds")
    html_url: Optional[str] = Field(None, description="GitHub Actions run URL")
    logs_url: Optional[str] = Field(None, description="Logs URL")

class Pipeline(PipelineBase):
    id: int = Field(..., description="Pipeline ID")
    github_run_id: int = Field(..., description="GitHub Actions run ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Pipeline start time")
    completed_at: Optional[datetime] = Field(None, description="Pipeline completion time")
    duration: Optional[int] = Field(None, description="Duration in seconds")
    html_url: Optional[str] = Field(None, description="GitHub Actions run URL")
    logs_url: Optional[str] = Field(None, description="Logs URL")

    class Config:
        from_attributes = True

class PipelineList(BaseModel):
    pipelines: List[Pipeline] = Field(..., description="List of pipelines")
    total: int = Field(..., description="Total number of pipelines")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")

class Metrics(BaseModel):
    period: str = Field(..., description="Time period for metrics")
    total_executions: int = Field(..., description="Total number of executions")
    success_count: int = Field(..., description="Number of successful executions")
    failure_count: int = Field(..., description="Number of failed executions")
    success_rate: float = Field(..., description="Success rate percentage")
    average_build_time: Optional[float] = Field(None, description="Average build time in seconds")
    min_build_time: Optional[int] = Field(None, description="Minimum build time in seconds")
    max_build_time: Optional[int] = Field(None, description="Maximum build time in seconds")
    last_execution: Optional[Pipeline] = Field(None, description="Most recent execution")

class WorkflowMetrics(BaseModel):
    name: str = Field(..., description="Workflow name")
    executions: int = Field(..., description="Number of executions")
    success_rate: float = Field(..., description="Success rate percentage")
    average_time: Optional[float] = Field(None, description="Average build time")

class MetricsResponse(BaseModel):
    period: str = Field(..., description="Time period for metrics")
    total_executions: int = Field(..., description="Total number of executions")
    success_count: int = Field(..., description="Number of successful executions")
    failure_count: int = Field(..., description="Number of failed executions")
    success_rate: float = Field(..., description="Success rate percentage")
    average_build_time: Optional[float] = Field(None, description="Average build time in seconds")
    min_build_time: Optional[int] = Field(None, description="Minimum build time in seconds")
    max_build_time: Optional[int] = Field(None, description="Maximum build time in seconds")
    last_execution: Optional[Pipeline] = Field(None, description="Most recent execution")
    workflows: List[WorkflowMetrics] = Field(..., description="Metrics per workflow")

class SyncResponse(BaseModel):
    success: bool = Field(..., description="Sync operation success status")
    message: str = Field(..., description="Sync operation message")
    new_executions: int = Field(..., description="Number of new executions synced")
    total_executions: int = Field(..., description="Total number of executions")
    sync_time: datetime = Field(..., description="Sync operation timestamp")

class HealthResponse(BaseModel):
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Application version")
    uptime: Optional[float] = Field(None, description="Application uptime in seconds")
    database: str = Field(..., description="Database connection status")
    github: str = Field(..., description="GitHub API connection status")
    slack: str = Field(..., description="Slack webhook connection status")

