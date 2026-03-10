from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, BigInteger, Index
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime

class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(BigInteger, primary_key=True, index=True)
    github_run_id = Column(BigInteger, unique=True, nullable=False, index=True)
    workflow_name = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    conclusion = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Integer, nullable=True)
    branch = Column(String(255), nullable=True)
    commit_sha = Column(String(40), nullable=True)
    commit_message = Column(Text, nullable=True)
    actor = Column(String(255), nullable=True)
    html_url = Column(Text, nullable=True)
    logs_url = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Pipeline(id={self.id}, workflow_name='{self.workflow_name}', status='{self.status}')>"

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Workflow(id={self.id}, name='{self.name}')>"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(BigInteger, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=func.now())
    status = Column(String(50), default="sent")

    def __repr__(self):
        return f"<Alert(id={self.id}, pipeline_id={self.pipeline_id}, type='{self.alert_type}')>"

class MetricsCache(Base):
    __tablename__ = "metrics_cache"

    id = Column(Integer, primary_key=True, index=True)
    metric_key = Column(String(255), unique=True, nullable=False, index=True)
    metric_value = Column(Text, nullable=False)  # JSON string
    period = Column(String(20), nullable=False)
    calculated_at = Column(DateTime(timezone=True), default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    def __repr__(self):
        return f"<MetricsCache(id={self.id}, key='{self.metric_key}', period='{self.period}')>"

# Create indexes for better performance
Index('idx_pipelines_status', Pipeline.status)
Index('idx_pipelines_created_at', Pipeline.created_at)
Index('idx_pipelines_workflow', Pipeline.workflow_name)
Index('idx_alerts_pipeline_id', Alert.pipeline_id)
Index('idx_alerts_sent_at', Alert.sent_at)
Index('idx_metrics_cache_expires', MetricsCache.expires_at)
