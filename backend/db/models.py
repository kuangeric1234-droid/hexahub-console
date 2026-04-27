"""
SQLAlchemy ORM models for the Hexa Hub portal.

All primary keys are UUIDs. All timestamps are timezone-aware.
The `assets.embedding` column requires the pgvector extension (enabled in the
initial Alembic migration).
"""
import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


# ── Enums ─────────────────────────────────────────────────────────────────────

class CampaignStatus(str, enum.Enum):
    draft     = "draft"
    active    = "active"
    paused    = "paused"
    completed = "completed"
    archived  = "archived"


class Platform(str, enum.Enum):
    linkedin       = "linkedin"
    blog           = "blog"
    instagram      = "instagram"
    xiaohongshu    = "xiaohongshu"
    wechat_moments = "wechat_moments"


class PostStatus(str, enum.Enum):
    pending    = "pending"
    generating = "generating"
    draft      = "draft"
    approved   = "approved"
    rejected   = "rejected"
    scheduled  = "scheduled"
    published  = "published"
    failed     = "failed"


class ApprovalDecision(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class AssetType(str, enum.Enum):
    image    = "image"
    video    = "video"
    document = "document"


class AgentLogStatus(str, enum.Enum):
    running = "running"
    success = "success"
    failed  = "failed"


class WordSeverity(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

class Campaign(Base):
    __tablename__ = "campaigns"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       = Column(String(255), nullable=False)
    brief      = Column(Text, nullable=False)
    objective  = Column(Text, nullable=False)
    kpis       = Column(JSONB, nullable=False, default=dict)
    start_date = Column(Date, nullable=False)
    end_date   = Column(Date, nullable=False)
    status     = Column(Enum(CampaignStatus), nullable=False, default=CampaignStatus.draft)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    pillars = relationship("ContentPillar", back_populates="campaign", cascade="all, delete-orphan")
    posts   = relationship("Post", back_populates="campaign", cascade="all, delete-orphan")


class ContentPillar(Base):
    __tablename__ = "content_pillars"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    weight      = Column(Float, nullable=False, default=1.0)

    campaign = relationship("Campaign", back_populates="pillars")
    posts    = relationship("Post", back_populates="pillar")


class Post(Base):
    __tablename__ = "posts"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id     = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    pillar_id       = Column(UUID(as_uuid=True), ForeignKey("content_pillars.id", ondelete="SET NULL"), nullable=True)
    platform        = Column(Enum(Platform), nullable=False)
    scheduled_at    = Column(DateTime(timezone=True), nullable=True)
    status          = Column(Enum(PostStatus), nullable=False, default=PostStatus.pending)
    copy            = Column(Text, nullable=True)
    visual_url      = Column(String(2048), nullable=True)
    metadata_json   = Column(JSONB, nullable=False, default=dict)
    approval_status = Column(Enum(ApprovalDecision), nullable=False, default=ApprovalDecision.pending)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at      = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign  = relationship("Campaign", back_populates="posts")
    pillar    = relationship("ContentPillar", back_populates="posts")
    approvals = relationship("Approval", back_populates="post", cascade="all, delete-orphan")
    metrics   = relationship("Metric", back_populates="post", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type              = Column(Enum(AssetType), nullable=False)
    url               = Column(String(2048), nullable=False)
    tags              = Column(ARRAY(String), nullable=False, default=list)
    performance_score = Column(Float, nullable=True)
    embedding         = Column(Vector(1536), nullable=True)  # 1536-dim for OpenAI / compatible models
    created_at        = Column(DateTime(timezone=True), default=datetime.utcnow)


class Approval(Base):
    __tablename__ = "approvals"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id   = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    reviewer  = Column(String(255), nullable=False)
    decision  = Column(Enum(ApprovalDecision), nullable=False, default=ApprovalDecision.pending)
    feedback  = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("Post", back_populates="approvals")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name  = Column(String(255), nullable=False)
    task        = Column(String(255), nullable=False)
    input_json  = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=True)
    status      = Column(Enum(AgentLogStatus), nullable=False, default=AgentLogStatus.running)
    duration_ms = Column(Integer, nullable=True)
    timestamp   = Column(DateTime(timezone=True), default=datetime.utcnow)


class Metric(Base):
    __tablename__ = "metrics"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id     = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    platform    = Column(Enum(Platform), nullable=False)
    reach       = Column(Integer, nullable=True)
    engagement  = Column(Integer, nullable=True)
    ctr         = Column(Float, nullable=True)
    conversions = Column(Integer, nullable=True)
    fetched_at  = Column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("Post", back_populates="metrics")


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    word       = Column(String(255), nullable=False)
    language   = Column(String(10), nullable=False, default="en")
    severity   = Column(Enum(WordSeverity), nullable=False, default=WordSeverity.medium)
    category   = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
