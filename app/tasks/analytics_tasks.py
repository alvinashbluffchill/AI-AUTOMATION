from celery import current_task
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Dict, List

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.models import Analytics, PostAnalytics, Post, SocialAccount
from app.services.instagram_service import InstagramService
from app.services.facebook_service import FacebookService
from app.services.twitter_service import TwitterService
from app.services.youtube_service import YouTubeService
from app.services.tiktok_service import TikTokService


@celery_app.task(bind=True)
def sync_platform_analytics(self, social_account_id: int):
    """Sync analytics for a specific social media account"""
    
    try:
        db = SessionLocal()
        social_account = db.query(SocialAccount).filter(SocialAccount.id == social_account_id).first()
        
        if not social_account:
            raise Exception("Social account not found")
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': f'Syncing {social_account.platform} analytics...'})
        
        # Get appropriate service
        service = get_analytics_service(social_account.platform, social_account)
        
        if not service:
            raise Exception(f"Analytics service not available for {social_account.platform}")
        
        # Fetch account metrics
        self.update_state(state='PROGRESS', meta={'progress': 30, 'status': 'Fetching account metrics...'})
        account_metrics = service.get_account_metrics()
        
        # Fetch post analytics
        self.update_state(state='PROGRESS', meta={'progress': 60, 'status': 'Fetching post analytics...'})
        post_analytics = service.get_posts_analytics()
        
        # Save account analytics
        analytics = Analytics(
            user_id=social_account.user_id,
            social_account_id=social_account_id,
            followers_count=account_metrics.get('followers_count', 0),
            following_count=account_metrics.get('following_count', 0),
            posts_count=account_metrics.get('posts_count', 0),
            followers_growth=account_metrics.get('followers_growth', 0),
            engagement_growth=account_metrics.get('engagement_growth', 0.0),
            date=datetime.now(),
            period_type='daily',
            platform_metrics=account_metrics
        )
        
        db.add(analytics)
        
        # Save post analytics
        for post_data in post_analytics:
            post = db.query(Post).filter(
                Post.platform_post_id == post_data.get('post_id'),
                Post.social_account_id == social_account_id
            ).first()
            
            if post:
                post_analytics_record = PostAnalytics(
                    post_id=post.id,
                    views=post_data.get('views', 0),
                    likes=post_data.get('likes', 0),
                    comments=post_data.get('comments', 0),
                    shares=post_data.get('shares', 0),
                    saves=post_data.get('saves', 0),
                    reach=post_data.get('reach', 0),
                    impressions=post_data.get('impressions', 0),
                    engagement_rate=post_data.get('engagement_rate', 0.0),
                    click_through_rate=post_data.get('click_through_rate', 0.0)
                )
                
                db.add(post_analytics_record)
        
        db.commit()
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'Analytics synced successfully'})
        
        return {
            'social_account_id': social_account_id,
            'platform': social_account.platform,
            'account_metrics': account_metrics,
            'posts_analyzed': len(post_analytics),
            'synced_at': datetime.now()
        }
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'progress': 0, 'status': f'Analytics sync failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task
def sync_all_analytics():
    """Sync analytics for all active social accounts"""
    
    try:
        db = SessionLocal()
        
        # Get all active social accounts
        social_accounts = db.query(SocialAccount).filter(
            SocialAccount.is_active == True
        ).all()
        
        synced_count = 0
        failed_count = 0
        
        for account in social_accounts:
            try:
                # Trigger individual sync
                sync_platform_analytics.delay(account.id)
                synced_count += 1
                
            except Exception as e:
                print(f"Failed to sync analytics for account {account.id}: {e}")
                failed_count += 1
        
        return {
            'total_accounts': len(social_accounts),
            'synced_count': synced_count,
            'failed_count': failed_count,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        print(f"Error in sync_all_analytics: {e}")
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def generate_analytics_report(self, user_id: int, period_days: int = 30):
    """Generate comprehensive analytics report for a user"""
    
    try:
        db = SessionLocal()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Update task progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Collecting analytics data...'})
        
        # Get user's social accounts
        social_accounts = db.query(SocialAccount).filter(
            SocialAccount.user_id == user_id,
            SocialAccount.is_active == True
        ).all()
        
        report_data = {
            'user_id': user_id,
            'period_days': period_days,
            'start_date': start_date,
            'end_date': end_date,
            'platforms': {},
            'summary': {
                'total_followers': 0,
                'total_posts': 0,
                'total_engagement': 0,
                'growth_rate': 0.0
            }
        }
        
        # Process each platform
        for i, account in enumerate(social_accounts):
            progress = int(20 + (i / len(social_accounts)) * 60)
            self.update_state(
                state='PROGRESS',
                meta={'progress': progress, 'status': f'Processing {account.platform} analytics...'}
            )
            
            # Get analytics data for this platform
            analytics_data = db.query(Analytics).filter(
                Analytics.social_account_id == account.id,
                Analytics.date >= start_date
            ).order_by(Analytics.date.asc()).all()
            
            if analytics_data:
                first_record = analytics_data[0]
                last_record = analytics_data[-1]
                
                platform_data = {
                    'account_name': account.account_name,
                    'current_followers': last_record.followers_count,
                    'followers_growth': last_record.followers_count - first_record.followers_count,
                    'current_posts': last_record.posts_count,
                    'posts_growth': last_record.posts_count - first_record.posts_count,
                    'engagement_growth': last_record.engagement_growth,
                    'analytics_timeline': [
                        {
                            'date': record.date,
                            'followers': record.followers_count,
                            'posts': record.posts_count,
                            'engagement_growth': record.engagement_growth
                        }
                        for record in analytics_data
                    ]
                }
                
                # Get top performing posts
                posts = db.query(Post, PostAnalytics).join(
                    PostAnalytics, Post.id == PostAnalytics.post_id
                ).filter(
                    Post.social_account_id == account.id,
                    Post.posted_at >= start_date
                ).order_by(PostAnalytics.engagement_rate.desc()).limit(5).all()
                
                platform_data['top_posts'] = [
                    {
                        'title': post.title,
                        'posted_at': post.posted_at,
                        'likes': analytics.likes,
                        'comments': analytics.comments,
                        'engagement_rate': analytics.engagement_rate
                    }
                    for post, analytics in posts
                ]
                
                report_data['platforms'][account.platform] = platform_data
                
                # Update summary
                report_data['summary']['total_followers'] += last_record.followers_count
                report_data['summary']['total_posts'] += last_record.posts_count
        
        # Calculate overall growth rate
        if report_data['summary']['total_followers'] > 0:
            total_growth = sum(
                data.get('followers_growth', 0) 
                for data in report_data['platforms'].values()
            )
            report_data['summary']['growth_rate'] = (
                total_growth / report_data['summary']['total_followers'] * 100
            )
        
        self.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'Report generated successfully'})
        
        return report_data
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'progress': 0, 'status': f'Report generation failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


@celery_app.task
def generate_daily_report():
    """Generate daily analytics reports for all users"""
    
    try:
        db = SessionLocal()
        
        # Get all users with active social accounts
        users_with_accounts = db.query(SocialAccount.user_id).filter(
            SocialAccount.is_active == True
        ).distinct().all()
        
        reports_generated = 0
        
        for user_tuple in users_with_accounts:
            user_id = user_tuple[0]
            try:
                # Generate report for this user
                generate_analytics_report.delay(user_id, 7)  # 7-day report
                reports_generated += 1
                
            except Exception as e:
                print(f"Failed to generate report for user {user_id}: {e}")
        
        return {
            'reports_generated': reports_generated,
            'total_users': len(users_with_accounts),
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        print(f"Error in generate_daily_report: {e}")
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True)
def analyze_post_performance(self, post_id: int):
    """Analyze performance of a specific post"""
    
    try:
        db = SessionLocal()
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise Exception("Post not found")
        
        # Get latest analytics
        latest_analytics = db.query(PostAnalytics).filter(
            PostAnalytics.post_id == post_id
        ).order_by(PostAnalytics.collected_at.desc()).first()
        
        if not latest_analytics:
            return {'status': 'no_data', 'message': 'No analytics data available'}
        
        # Calculate performance metrics
        engagement_rate = latest_analytics.engagement_rate
        total_interactions = (
            latest_analytics.likes + 
            latest_analytics.comments + 
            latest_analytics.shares + 
            latest_analytics.saves
        )
        
        # Determine performance category
        if engagement_rate >= 5.0:
            performance = "excellent"
        elif engagement_rate >= 3.0:
            performance = "good"
        elif engagement_rate >= 1.0:
            performance = "average"
        else:
            performance = "poor"
        
        # Get comparison data (average of user's other posts)
        user_posts_avg = db.query(
            db.func.avg(PostAnalytics.engagement_rate),
            db.func.avg(PostAnalytics.likes),
            db.func.avg(PostAnalytics.comments)
        ).join(Post).filter(
            Post.user_id == post.user_id,
            Post.id != post_id
        ).first()
        
        comparison = {}
        if user_posts_avg[0]:  # If there are other posts to compare
            comparison = {
                'avg_engagement_rate': float(user_posts_avg[0]),
                'avg_likes': float(user_posts_avg[1]),
                'avg_comments': float(user_posts_avg[2]),
                'performance_vs_average': engagement_rate / float(user_posts_avg[0]) if user_posts_avg[0] > 0 else 1.0
            }
        
        analysis = {
            'post_id': post_id,
            'performance_category': performance,
            'engagement_rate': engagement_rate,
            'total_interactions': total_interactions,
            'metrics': {
                'views': latest_analytics.views,
                'likes': latest_analytics.likes,
                'comments': latest_analytics.comments,
                'shares': latest_analytics.shares,
                'saves': latest_analytics.saves,
                'reach': latest_analytics.reach,
                'impressions': latest_analytics.impressions
            },
            'comparison': comparison,
            'analyzed_at': datetime.now()
        }
        
        return analysis
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': f'Post analysis failed: {str(e)}'}
        )
        raise
    
    finally:
        db.close()


def get_analytics_service(platform: str, social_account):
    """Get the appropriate analytics service for a platform"""
    
    services = {
        'instagram': InstagramService,
        'facebook': FacebookService,
        'twitter': TwitterService,
        'youtube': YouTubeService,
        'tiktok': TikTokService
    }
    
    service_class = services.get(platform)
    if service_class:
        return service_class(social_account)
    
    return None


@celery_app.task
def cleanup_old_analytics():
    """Clean up old analytics data to save storage"""
    
    try:
        db = SessionLocal()
        
        # Keep only last 90 days of daily analytics
        cutoff_date = datetime.now() - timedelta(days=90)
        
        deleted_analytics = db.query(Analytics).filter(
            Analytics.date < cutoff_date,
            Analytics.period_type == 'daily'
        ).delete()
        
        # Keep only last 30 days of post analytics
        post_cutoff_date = datetime.now() - timedelta(days=30)
        
        deleted_post_analytics = db.query(PostAnalytics).filter(
            PostAnalytics.collected_at < post_cutoff_date
        ).delete()
        
        db.commit()
        
        return {
            'deleted_analytics': deleted_analytics,
            'deleted_post_analytics': deleted_post_analytics,
            'cutoff_date': cutoff_date,
            'timestamp': datetime.now()
        }
        
    except Exception as e:
        db.rollback()
        raise
    
    finally:
        db.close()