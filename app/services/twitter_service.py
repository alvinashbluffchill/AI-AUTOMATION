from typing import Dict, List
import tweepy
import os
from datetime import datetime

from app.services.base_service import BaseSocialMediaService
from app.core.config import settings


class TwitterService(BaseSocialMediaService):
    """Twitter API service for posting and analytics"""
    
    def __init__(self, social_account):
        super().__init__(social_account)
        
        # Initialize Tweepy client
        self.client = tweepy.Client(
            bearer_token=settings.TWITTER_API_KEY,
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            access_token=social_account.access_token,
            access_token_secret=social_account.platform_data.get('access_token_secret') if social_account.platform_data else None,
            wait_on_rate_limit=True
        )
        
        # For media upload, we need the v1.1 API
        auth = tweepy.OAuth1UserHandler(
            settings.TWITTER_API_KEY,
            settings.TWITTER_API_SECRET,
            social_account.access_token,
            social_account.platform_data.get('access_token_secret') if social_account.platform_data else None
        )
        self.api_v1 = tweepy.API(auth, wait_on_rate_limit=True)
    
    def post_content(self, file_path: str, caption: str, title: str = None) -> Dict:
        """Post content to Twitter"""
        
        try:
            file_type = self.get_file_type(file_path)
            
            if file_type in ['image', 'video']:
                return self._post_with_media(file_path, caption)
            else:
                return self._post_text_only(caption)
                
        except Exception as e:
            raise Exception(f"Twitter posting failed: {str(e)}")
    
    def _post_with_media(self, file_path: str, caption: str) -> Dict:
        """Post tweet with media"""
        
        try:
            # Upload media using v1.1 API
            media = self.api_v1.media_upload(file_path)
            media_id = media.media_id
            
            # Post tweet with media using v2 API
            response = self.client.create_tweet(
                text=caption,
                media_ids=[media_id]
            )
            
            return {
                'post_id': response.data['id'],
                'platform': 'twitter',
                'media_type': self.get_file_type(file_path),
                'status': 'published',
                'published_at': datetime.now().isoformat(),
                'media_id': media_id
            }
            
        except Exception as e:
            raise Exception(f"Twitter media posting failed: {str(e)}")
    
    def _post_text_only(self, caption: str) -> Dict:
        """Post text-only tweet"""
        
        try:
            response = self.client.create_tweet(text=caption)
            
            return {
                'post_id': response.data['id'],
                'platform': 'twitter',
                'media_type': 'text',
                'status': 'published',
                'published_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Twitter text posting failed: {str(e)}")
    
    def get_account_metrics(self) -> Dict:
        """Get Twitter account metrics"""
        
        try:
            # Get authenticated user info
            user = self.client.get_me(
                user_fields=['public_metrics', 'created_at']
            )
            
            if not user.data:
                raise Exception("Could not retrieve user data")
            
            metrics = user.data.public_metrics
            
            return {
                'followers_count': metrics.get('followers_count', 0),
                'following_count': metrics.get('following_count', 0),
                'posts_count': metrics.get('tweet_count', 0),
                'listed_count': metrics.get('listed_count', 0),
                'like_count': metrics.get('like_count', 0),
                'followers_growth': 0,  # Calculate from historical data
                'engagement_growth': 0.0  # Calculate from historical data
            }
            
        except Exception as e:
            raise Exception(f"Failed to get Twitter account metrics: {str(e)}")
    
    def get_posts_analytics(self, limit: int = 50) -> List[Dict]:
        """Get analytics for recent Twitter posts"""
        
        try:
            # Get user's recent tweets
            user = self.client.get_me()
            user_id = user.data.id
            
            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=min(limit, 100),  # API limit
                tweet_fields=['public_metrics', 'created_at', 'context_annotations'],
                exclude=['retweets', 'replies']
            )
            
            posts_analytics = []
            
            if tweets.data:
                for tweet in tweets.data:
                    metrics = tweet.public_metrics
                    
                    # Calculate engagement rate
                    total_engagement = (
                        metrics.get('like_count', 0) +
                        metrics.get('retweet_count', 0) +
                        metrics.get('reply_count', 0) +
                        metrics.get('quote_count', 0)
                    )
                    
                    impressions = metrics.get('impression_count', 1)  # Avoid division by zero
                    engagement_rate = (total_engagement / impressions) * 100 if impressions > 0 else 0
                    
                    analytics = {
                        'post_id': tweet.id,
                        'likes': metrics.get('like_count', 0),
                        'comments': metrics.get('reply_count', 0),
                        'shares': metrics.get('retweet_count', 0) + metrics.get('quote_count', 0),
                        'views': impressions,
                        'impressions': impressions,
                        'engagement_rate': engagement_rate,
                        'created_at': tweet.created_at.isoformat() if tweet.created_at else None
                    }
                    
                    posts_analytics.append(analytics)
            
            return posts_analytics
            
        except Exception as e:
            raise Exception(f"Failed to get Twitter posts analytics: {str(e)}")
    
    def _refresh_token(self) -> bool:
        """Refresh Twitter access token"""
        
        # Twitter OAuth 1.0a tokens don't expire, but OAuth 2.0 tokens do
        # For now, return True as we're using OAuth 1.0a
        # In production, implement proper OAuth 2.0 token refresh if needed
        return True
    
    def validate_file_for_platform(self, file_path: str) -> bool:
        """Validate file for Twitter posting"""
        
        file_type = self.get_file_type(file_path)
        file_size = os.path.getsize(file_path)
        
        if file_type == 'image':
            # Twitter image requirements
            max_size = 5 * 1024 * 1024  # 5MB
            supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            
        elif file_type == 'video':
            # Twitter video requirements
            max_size = 512 * 1024 * 1024  # 512MB
            supported_formats = ['.mp4', '.mov']
            
        else:
            return False
        
        # Check file size
        if file_size > max_size:
            return False
        
        # Check file format
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in supported_formats:
            return False
        
        return True
    
    def get_optimal_posting_times(self) -> List[str]:
        """Get optimal posting times for Twitter"""
        
        # Based on general Twitter engagement patterns
        return ["09:00", "12:00", "15:00", "18:00", "21:00"]
    
    def post_thread(self, tweets: List[str], media_files: List[str] = None) -> Dict:
        """Post a Twitter thread"""
        
        try:
            thread_ids = []
            reply_to_id = None
            
            for i, tweet_text in enumerate(tweets):
                media_id = None
                
                # Add media to first tweet if provided
                if i == 0 and media_files:
                    media = self.api_v1.media_upload(media_files[0])
                    media_id = media.media_id
                
                # Create tweet
                if media_id:
                    response = self.client.create_tweet(
                        text=tweet_text,
                        media_ids=[media_id],
                        in_reply_to_tweet_id=reply_to_id
                    )
                else:
                    response = self.client.create_tweet(
                        text=tweet_text,
                        in_reply_to_tweet_id=reply_to_id
                    )
                
                tweet_id = response.data['id']
                thread_ids.append(tweet_id)
                reply_to_id = tweet_id  # Next tweet replies to this one
            
            return {
                'thread_ids': thread_ids,
                'main_post_id': thread_ids[0],
                'platform': 'twitter',
                'status': 'published',
                'published_at': datetime.now().isoformat(),
                'thread_length': len(tweets)
            }
            
        except Exception as e:
            raise Exception(f"Twitter thread posting failed: {str(e)}")
    
    def schedule_tweet(self, text: str, scheduled_time: datetime, media_files: List[str] = None) -> Dict:
        """Schedule a tweet for later posting"""
        
        # Note: Twitter API v2 doesn't support scheduling directly
        # This would need to be handled by our own scheduling system
        # For now, we'll return the data needed for our scheduler
        
        return {
            'text': text,
            'scheduled_time': scheduled_time.isoformat(),
            'media_files': media_files,
            'platform': 'twitter',
            'status': 'scheduled'
        }
    
    def get_trending_topics(self, location_id: int = 1) -> List[Dict]:
        """Get trending topics for a location"""
        
        try:
            trends = self.api_v1.get_place_trends(location_id)
            
            trending_topics = []
            for trend in trends[0]['trends'][:10]:  # Top 10 trends
                trending_topics.append({
                    'name': trend['name'],
                    'url': trend['url'],
                    'tweet_volume': trend['tweet_volume']
                })
            
            return trending_topics
            
        except Exception as e:
            raise Exception(f"Failed to get trending topics: {str(e)}")
    
    def search_tweets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for tweets"""
        
        try:
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=min(limit, 100),
                tweet_fields=['public_metrics', 'created_at', 'author_id']
            )
            
            results = []
            if tweets.data:
                for tweet in tweets.data:
                    results.append({
                        'id': tweet.id,
                        'text': tweet.text,
                        'author_id': tweet.author_id,
                        'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                        'metrics': tweet.public_metrics
                    })
            
            return results
            
        except Exception as e:
            raise Exception(f"Tweet search failed: {str(e)}")