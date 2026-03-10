from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, text
from typing import Optional
from datetime import datetime, timedelta
import json
from fastapi.encoders import jsonable_encoder

from app.core.database import get_db
from app.models.pipeline import Pipeline, MetricsCache
from app.schemas.pipeline import MetricsResponse, WorkflowMetrics

router = APIRouter()

@router.get("/", response_model=MetricsResponse)
async def get_metrics(
    period: str = Query("24h", description="Time period: 1h, 24h, 7d, 30d"),
    db: Session = Depends(get_db)
):
    """Get aggregated metrics for the dashboard"""
    try:
        # Check cache first
        cache_key = f"metrics_{period}"
        cached_metrics = db.query(MetricsCache).filter(
            MetricsCache.metric_key == cache_key,
            MetricsCache.expires_at > datetime.utcnow()
        ).first()

        if cached_metrics:
            return json.loads(cached_metrics.metric_value)

        # Calculate time range
        now = datetime.utcnow()
        if period == "1h":
            start_time = now - timedelta(hours=1)
        elif period == "24h":
            start_time = now - timedelta(days=1)
        elif period == "7d":
            start_time = now - timedelta(days=7)
        elif period == "30d":
            start_time = now - timedelta(days=30)
        else:
            raise HTTPException(status_code=400, detail="Invalid period. Use: 1h, 24h, 7d, 30d")

        # Get pipeline data for the period
        pipelines = db.query(Pipeline).filter(
            Pipeline.created_at >= start_time
        ).all()

        # Calculate metrics
        total_executions = len(pipelines)
        success_count = len([p for p in pipelines if p.status == "completed" and p.conclusion == "success"])
        failure_count = len([p for p in pipelines if p.status == "completed" and p.conclusion == "failure"])

        # Calculate success rate
        completed_count = success_count + failure_count
        success_rate = (success_count / completed_count * 100) if completed_count > 0 else 0

        # Calculate build time statistics
        completed_pipelines = [p for p in pipelines if p.status == "completed" and p.duration is not None]
        build_times = [p.duration for p in completed_pipelines]

        avg_build_time = sum(build_times) / len(build_times) if build_times else None
        min_build_time = min(build_times) if build_times else None
        max_build_time = max(build_times) if build_times else None

        # Get latest execution
        latest_pipeline = db.query(Pipeline).order_by(desc(Pipeline.created_at)).first()

        # Calculate workflow-specific metrics
        workflow_metrics = []
        workflow_data = {}

        for pipeline in pipelines:
            if pipeline.workflow_name not in workflow_data:
                workflow_data[pipeline.workflow_name] = {
                    'executions': 0, 'success_count': 0, 'failure_count': 0, 'total_time': 0, 'completed_count': 0
                }
            workflow_data[pipeline.workflow_name]['executions'] += 1
            if pipeline.status == "completed":
                workflow_data[pipeline.workflow_name]['completed_count'] += 1
                if pipeline.conclusion == "success":
                    workflow_data[pipeline.workflow_name]['success_count'] += 1
                elif pipeline.conclusion == "failure":
                    workflow_data[pipeline.workflow_name]['failure_count'] += 1
                if pipeline.duration:
                    workflow_data[pipeline.workflow_name]['total_time'] += pipeline.duration

        # Convert to WorkflowMetrics objects
        for workflow_name, data in workflow_data.items():
            if data['completed_count'] > 0:
                wf_success_rate = (data['success_count'] / data['completed_count']) * 100
                avg_time = data['total_time'] / data['completed_count'] if data['completed_count'] > 0 else None
                workflow_metrics.append(WorkflowMetrics(
                    name=workflow_name,
                    executions=data['executions'],
                    success_rate=round(wf_success_rate, 2),
                    average_time=round(avg_time, 2) if avg_time else None
                ))

        workflow_metrics.sort(key=lambda x: x.executions, reverse=True)

        response = MetricsResponse(
            period=period,
            total_executions=total_executions,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=round(success_rate, 2),
            average_build_time=round(avg_build_time, 2) if avg_build_time else None,
            min_build_time=min_build_time,
            max_build_time=max_build_time,
            last_execution=latest_pipeline,
            workflows=workflow_metrics
        )

        # Cache the result, ensuring proper serialization
        db.query(MetricsCache).filter(MetricsCache.metric_key == cache_key).delete()
        db.commit()
        
        cache_entry = MetricsCache(
            metric_key=cache_key,
            metric_value=json.dumps(jsonable_encoder(response)),
            period=period,
            expires_at=datetime.utcnow() + timedelta(minutes=5)
        )
        db.add(cache_entry)
        db.commit()

        return response
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

@router.get("/trends")
async def get_metrics_trends(
    metric: str = Query(..., description="Metric type: success_rate, build_time, failure_count"),
    period: str = Query("24h", description="Time period: 24h, 7d, 30d"),
    db: Session = Depends(get_db)
):
    """Get trend data for charts"""
    try:
        now = datetime.utcnow()
        if period == "24h":
            start_time, interval_hours = now - timedelta(days=1), 1
        elif period == "7d":
            start_time, interval_hours = now - timedelta(days=7), 6
        elif period == "30d":
            start_time, interval_hours = now - timedelta(days=30), 24
        else:
            raise HTTPException(status_code=400, detail="Invalid period. Use: 24h, 7d, 30d")

        intervals = []
        current_time = start_time
        while current_time <= now:
            intervals.append(current_time)
            current_time += timedelta(hours=interval_hours)

        trend_data = []
        for i in range(len(intervals) - 1):
            interval_start, interval_end = intervals[i], intervals[i+1]
            pipelines = db.query(Pipeline).filter(
                and_(Pipeline.created_at >= interval_start, Pipeline.created_at < interval_end)
            ).all()

            value = 0
            if metric == "success_rate":
                completed = [p for p in pipelines if p.status == "completed"]
                success_count = len([p for p in completed if p.conclusion == "success"])
                value = (success_count / len(completed) * 100) if completed else 0
            elif metric == "build_time":
                completed = [p for p in pipelines if p.status == "completed" and p.duration]
                value = sum(p.duration for p in completed) / len(completed) if completed else 0
            elif metric == "failure_count":
                value = len([p for p in pipelines if p.status == "completed" and p.conclusion == "failure"])
            else:
                raise HTTPException(status_code=400, detail="Invalid metric.")

            trend_data.append({
                "timestamp": interval_start.isoformat(),
                "value": round(value, 2)
            })

        return {"metric": metric, "period": period, "data": trend_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate trends: {str(e)}")

@router.get("/workflows")
async def get_workflow_metrics(db: Session = Depends(get_db)):
    """Get metrics grouped by workflow"""
    try:
        workflows = db.query(
            Pipeline.workflow_name,
            func.count(Pipeline.id).label("total_executions"),
            func.count(Pipeline.id).filter(and_(Pipeline.status == "completed", Pipeline.conclusion == "success")).label("success_count"),
            func.avg(Pipeline.duration).filter(Pipeline.status == "completed").label("avg_build_time")
        ).group_by(Pipeline.workflow_name).order_by(desc("total_executions")).all()
        
        workflow_metrics = []
        for wf in workflows:
            total_completed = db.query(Pipeline).filter(
                Pipeline.workflow_name == wf.workflow_name, Pipeline.status == "completed"
            ).count()
            success_rate = (wf.success_count / total_completed * 100) if total_completed > 0 else 0
            workflow_metrics.append({
                "name": wf.workflow_name,
                "total_executions": wf.total_executions,
                "success_rate": round(success_rate, 2),
                "average_build_time": round(wf.avg_build_time, 2) if wf.avg_build_time else None
            })
            
        return {"workflows": workflow_metrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch workflow metrics: {str(e)}")
