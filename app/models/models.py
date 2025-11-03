from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    posts = relationship("Post", back_populates="owner")
    social_accounts = relationship("SocialAccount", back_populates="user")


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    platform = Column(String, index=True)  # instagram, facebook, twitter, youtube, tiktok
    account_name = Column(String)
    access_token = Column(Text)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="social_accounts")
    posts = relationship("Post", back_populates="social_account")


class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    social_account_id = Column(Integer, ForeignKey("social_accounts.id"))
    
    # Content
    title = Column(String)
    description = Column(Text)
    file_path = Column(String)
    file_type = Column(String)  # image, video
    thumbnail_path = Column(String, nullable=True)
    
    # Scheduling
    scheduled_time = Column(DateTime(timezone=True))
    posted_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="scheduled")  # scheduled, posted, failed, cancelled
    
    # Platform-specific data
    platform_post_id = Column(String, nullable=True)
    platform_data = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="posts")
    social_account = relationship("SocialAccount", back_populates="posts")
    analytics = relationship("PostAnalytics", back_populates="post")


class PostAnalytics(Base):
    __tablename__ = "post_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    
    # Engagement metrics
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    
    # Reach metrics
    reach = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    
    # Performance metrics
    engagement_rate = Column(Float, default=0.0)
    click_through_rate = Column(Float, default=0.0)
    
    # Timestamps
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    post = relationship("Post", back_populates="analytics")


class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Schedule configuration
    name = Column(String)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timing
    schedule_type = Column(String)  # once, daily, weekly, monthly, custom
    schedule_data = Column(JSON)  # cron expression or specific times
    
    # Content queue
    content_queue = Column(JSON)  # List of file paths and metadata
    current_index = Column(Integer, default=0)
    
    # Platform targeting
    target_platforms = Column(JSON)  # List of platform IDs
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_executed = Column(DateTime(timezone=True), nullable=True)
    next_execution = Column(DateTime(timezone=True), nullable=True)


class Analytics(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    social_account_id = Column(Integer, ForeignKey("social_accounts.id"))
    
    # Account metrics
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    
    # Growth metrics
    followers_growth = Column(Integer, default=0)
    engagement_growth = Column(Float, default=0.0)
    
    # Period data
    date = Column(DateTime(timezone=True))
    period_type = Column(String)  # daily, weekly, monthly
    
    # Platform-specific metrics
    platform_metrics = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())