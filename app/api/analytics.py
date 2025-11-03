from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import Analytics, PostAnalytics, Post, SocialAccount
from app.tasks.analytics_tasks import sync_platform_analytics

router = APIRouter()


class AnalyticsResponse(BaseModel):
    platform: str
    followers_count: int
    following_count: int
    posts_count: int
    followers_growth: int
    engagement_growth: float
    date: datetime


class PostAnalyticsResponse(BaseModel):
    post_id: int
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    reach: int
    impressions: int
    engagement_rate: float


@router.get("/overview")
async def get_analytics_overview(
    user_id: int = 1,  # TODO: Get from authentication
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get analytics overview for all platforms"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get user's social accounts
    social_accounts = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.is_active == True
    ).all()
    
    overview = {}
    
    for account in social_accounts:
        # Get latest analytics for this platform
        latest_analytics = db.query(Analytics).filter(
            Analytics.social_account_id == account.id,
            Analytics.date >= start_date
        ).order_by(Analytics.date.desc()).first()
        
        if latest_analytics:
            overview[account.platform] = {
                "followers_count": latest_analytics.followers_count,
                "following_count": latest_analytics.following_count,
                "posts_count": latest_analytics.posts_count,
                "followers_growth": latest_analytics.followers_growth,
                "engagement_growth": latest_analytics.engagement_growth,
                "last_updated": latest_analytics.created_at
            }
        else:
            overview[account.platform] = {
                "followers_count": 0,
                "following_count": 0,
                "posts_count": 0,
                "followers_growth": 0,
                "engagement_growth": 0.0,
                "last_updated": None
            }
    
    return {"overview": overview, "period_days": days}


@router.get("/platform/{platform}")
async def get_platform_analytics(
    platform: str,
    user_id: int = 1,  # TODO: Get from authentication
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get detailed analytics for a specific platform"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get social account for this platform
    social_account = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.platform == platform,
        SocialAccount.is_active == True
    ).first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail=f"No active {platform} account found")
    
    # Get analytics data
    analytics_data = db.query(Analytics).filter(
        Analytics.social_account_id == social_account.id,
        Analytics.date >= start_date
    ).order_by(Analytics.date.asc()).all()
    
    # Get post analytics for this platform
    posts = db.query(Post).filter(
        Post.user_id == user_id,
        Post.social_account_id == social_account.id,
        Post.posted_at >= start_date
    ).all()
    
    post_analytics = []
    for post in posts:
        analytics = db.query(PostAnalytics).filter(
            PostAnalytics.post_id == post.id
        ).order_by(PostAnalytics.collected_at.desc()).first()
        
        if analytics:
            post_analytics.append({
                "post_id": post.id,
                "title": post.title,
                "posted_at": post.posted_at,
                "views": analytics.views,
                "likes": analytics.likes,
                "comments": analytics.comments,
                "shares": analytics.shares,
                "saves": analytics.saves,
                "engagement_rate": analytics.engagement_rate
            })
    
    return {
        "platform": platform,
        "account_name": social_account.account_name,
        "analytics_timeline": [
            {
                "date": analytics.date,
                "followers_count": analytics.followers_count,
                "following_count": analytics.following_count,
                "posts_count": analytics.posts_count,
                "followers_growth": analytics.followers_growth,
                "engagement_growth": analytics.engagement_growth
            }
            for analytics in analytics_data
        ],
        "post_analytics": post_analytics,
        "period_days": days
    }


@router.get("/posts/{post_id}")
async def get_post_analytics(
    post_id: int,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Get analytics for a specific post"""
    
    # Verify post ownership
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.user_id == user_id
    ).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Get all analytics records for this post
    analytics_records = db.query(PostAnalytics).filter(
        PostAnalytics.post_id == post_id
    ).order_by(PostAnalytics.collected_at.desc()).all()
    
    if not analytics_records:
        return {
            "post_id": post_id,
            "title": post.title,
            "posted_at": post.posted_at,
            "analytics": [],
            "message": "No analytics data available yet"
        }
    
    latest_analytics = analytics_records[0]
    
    return {
        "post_id": post_id,
        "title": post.title,
        "posted_at": post.posted_at,
        "latest_analytics": {
            "views": latest_analytics.views,
            "likes": latest_analytics.likes,
            "comments": latest_analytics.comments,
            "shares": latest_analytics.shares,
            "saves": latest_analytics.saves,
            "reach": latest_analytics.reach,
            "impressions": latest_analytics.impressions,
            "engagement_rate": latest_analytics.engagement_rate,
            "collected_at": latest_analytics.collected_at
        },
        "analytics_history": [
            {
                "views": record.views,
                "likes": record.likes,
                "comments": record.comments,
                "shares": record.shares,
                "engagement_rate": record.engagement_rate,
                "collected_at": record.collected_at
            }
            for record in analytics_records
        ]
    }


@router.post("/sync/{platform}")
async def sync_platform_analytics_endpoint(
    platform: str,
    background_tasks: BackgroundTasks,
    user_id: int = 1,  # TODO: Get from authentication
    db: Session = Depends(get_db)
):
    """Trigger analytics sync for a platform"""
    
    # Verify user has this platform connected
    social_account = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.platform == platform,
        SocialAccount.is_active == True
    ).first()
    
    if not social_account:
        raise HTTPException(status_code=404, detail=f"No active {platform} account found")
    
    # Trigger background sync
    background_tasks.add_task(sync_platform_analytics, social_account.id)
    
    return {
        "message": f"Analytics sync started for {platform}",
        "platform": platform,
        "account_name": social_account.account_name
    }


@router.get("/growth")
async def get_growth_metrics(
    user_id: int = 1,  # TODO: Get from authentication
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get growth metrics across all platforms"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get user's social accounts
    social_accounts = db.query(SocialAccount).filter(
        SocialAccount.user_id == user_id,
        SocialAccount.is_active == True
    ).all()
    
    growth_data = {}
    total_followers_growth = 0
    total_engagement_growth = 0.0
    
    for account in social_accounts:
        # Get analytics data for the period
        analytics_data = db.query(Analytics).filter(
            Analytics.social_account_id == account.id,
            Analytics.date >= start_date
        ).order_by(Analytics.date.asc()).all()
        
        if len(analytics_data) >= 2:
            first_record = analytics_data[0]
            last_record = analytics_data[-1]
            
            followers_growth = last_record.followers_count - first_record.followers_count
            engagement_growth = last_record.engagement_growth
            
            growth_data[account.platform] = {
                "followers_growth": followers_growth,
                "engagement_growth": engagement_growth,
                "start_followers": first_record.followers_count,
                "end_followers": last_record.followers_count,
                "growth_percentage": (followers_growth / first_record.followers_count * 100) if first_record.followers_count > 0 else 0
            }
            
            total_followers_growth += followers_growth
            total_engagement_growth += engagement_growth
    
    return {
        "period_days": days,
        "total_followers_growth": total_followers_growth,
        "average_engagement_growth": total_engagement_growth / len(social_accounts) if social_accounts else 0,
        "platform_growth": growth_data
    }


@router.get("/top-posts")
async def get_top_performing_posts(
    user_id: int = 1,  # TODO: Get from authentication
    limit: int = 10,
    metric: str = "engagement_rate",  # views, likes, comments, engagement_rate
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get top performing posts"""
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Get posts with analytics
    posts_query = db.query(Post, PostAnalytics).join(
        PostAnalytics, Post.id == PostAnalytics.post_id
    ).filter(
        Post.user_id == user_id,
        Post.posted_at >= start_date
    )
    
    # Order by the specified metric
    if metric == "views":
        posts_query = posts_query.order_by(PostAnalytics.views.desc())
    elif metric == "likes":
        posts_query = posts_query.order_by(PostAnalytics.likes.desc())
    elif metric == "comments":
        posts_query = posts_query.order_by(PostAnalytics.comments.desc())
    elif metric == "engagement_rate":
        posts_query = posts_query.order_by(PostAnalytics.engagement_rate.desc())
    else:
        posts_query = posts_query.order_by(PostAnalytics.engagement_rate.desc())
    
    top_posts = posts_query.limit(limit).all()
    
    return {
        "metric": metric,
        "period_days": days,
        "top_posts": [
            {
                "post_id": post.id,
                "title": post.title,
                "description": post.description,
                "posted_at": post.posted_at,
                "file_type": post.file_type,
                "thumbnail_path": post.thumbnail_path,
                "analytics": {
                    "views": analytics.views,
                    "likes": analytics.likes,
                    "comments": analytics.comments,
                    "shares": analytics.shares,
                    "saves": analytics.saves,
                    "engagement_rate": analytics.engagement_rate
                }
            }
            for post, analytics in top_posts
        ]
    }