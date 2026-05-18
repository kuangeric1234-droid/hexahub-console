"""
SQLAlchemy ORM models for the Hexa Hub portal.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
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
    facebook       = "facebook"
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

class User(Base):
    __tablename__ = "users"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name       = Column(String(255), nullable=True)
    role            = Column(String(50), nullable=False, default="member")  # admin / member / viewer
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_login_at   = Column(DateTime(timezone=True), nullable=True)

    ad_creative_runs = relationship("AdCreativeRun", back_populates="user")


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

    pillars          = relationship("ContentPillar", back_populates="campaign", cascade="all, delete-orphan")
    posts            = relationship("Post", back_populates="campaign", cascade="all, delete-orphan")
    ad_creative_runs = relationship("AdCreativeRun", back_populates="campaign")
    ad_campaigns     = relationship("AdCampaign", back_populates="campaign")


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
    campaign_id     = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
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
    versions  = relationship("PostVersion", back_populates="post", cascade="all, delete-orphan",
                             order_by="PostVersion.version_number")


class PostVersion(Base):
    """Snapshot of a post's editable fields before each PATCH."""
    __tablename__ = "post_versions"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id        = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    copy           = Column(Text, nullable=True)
    visual_url     = Column(String(2048), nullable=True)
    scheduled_at   = Column(DateTime(timezone=True), nullable=True)
    edited_by      = Column(String(255), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=datetime.utcnow)

    post = relationship("Post", back_populates="versions")


class Asset(Base):
    __tablename__ = "assets"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type              = Column(Enum(AssetType), nullable=False)
    url               = Column(String(2048), nullable=False)
    name              = Column(String(255), nullable=True)
    tags              = Column(ARRAY(String), nullable=False, default=list)
    performance_score = Column(Float, nullable=True)
    # embedding column omitted — requires pgvector extension
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


class AdCreativeRun(Base):
    __tablename__ = "ad_creative_runs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    platform    = Column(String(50), nullable=False)
    input_json  = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=False, default=dict)
    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow)

    user     = relationship("User", back_populates="ad_creative_runs")
    campaign = relationship("Campaign", back_populates="ad_creative_runs")


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


class SocialConnection(Base):
    """Stores OAuth-connected social account credentials (single account per provider)."""
    __tablename__ = "social_connections"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider          = Column(String(50), nullable=False, unique=True)  # e.g. "meta"
    page_id           = Column(String(255), nullable=True)               # Facebook Page ID
    page_name         = Column(String(255), nullable=True)               # display name
    page_access_token = Column(Text, nullable=False)                     # long-lived Page token
    ig_user_id        = Column(String(255), nullable=True)               # Instagram Business Account ID
    ig_username       = Column(String(255), nullable=True)               # Instagram handle
    connected_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at        = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AdCampaign(Base):
    """
    Maps a Hexa Hub content campaign to a Meta Ads campaign/adset/ad triple.
    Always created with status PAUSED — never activated without explicit user action.
    daily_budget stored in AUD cents (Meta's unit).
    """
    __tablename__ = "ad_campaigns"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id       = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    meta_campaign_id  = Column(String(255), nullable=False, unique=True)
    meta_adset_id     = Column(String(255), nullable=True)
    meta_ad_id        = Column(String(255), nullable=True)
    status            = Column(String(50),  nullable=False, default="PAUSED")
    daily_budget      = Column(Integer,     nullable=True)   # AUD cents
    objective         = Column(String(100), nullable=True)
    targeting_summary = Column(Text,        nullable=True)
    synced_at         = Column(DateTime(timezone=True), nullable=True)
    created_at        = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at        = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="ad_campaigns")
