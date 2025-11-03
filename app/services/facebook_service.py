from typing import Dict, List
import requests
import os
from datetime import datetime

from app.services.base_service import BaseSocialMediaService
from app.core.config import settings


class FacebookService(BaseSocialMediaService):
    """Facebook API service for posting and analytics"""
    
    def __init__(self, social_account):
        super().__init__(social_account)
        self.base_url = "https://graph.facebook.com/v18.0"
        self.page_id = social_account.platform_data.get('page_id') if social_account.platform_data else None
    
    def post_content(self, file_path: str, caption: str, title: str = None) -> Dict:
        """Post content to Facebook"""
        
        try:
            if not self.page_id:
                raise Exception("Facebook page ID not configured")
            
            file_type = self.get_file_type(file_path)
            
            if file_type == 'image':
                return self._post_image(file_path, caption)
            elif file_type == 'video':
                return self._post_video(file_path, caption)
            else:
                # Post as text with link if it's not media
                return self._post_text(caption)
                
        except Exception as e:
            raise Exception(f"Facebook posting failed: {str(e)}")
    
    def _post_image(self, file_path: str, caption: str) -> Dict:
        """Post image to Facebook"""
        
        try:
            url = f"{self.base_url}/{self.page_id}/photos"
            
            with open(file_path, 'rb') as image_file:
                files = {'source': image_file}
                data = {
                    'message': caption,
                    'access_token': self.access_token
                }
                
                response = requests.post(url, files=files, data=data)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    'post_id': result['id'],
                    'platform': 'facebook',
                    'media_type': 'image',
                    'status': 'published',
                    'published_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            raise Exception(f"Facebook image posting failed: {str(e)}")
    
    def _post_video(self, file_path: str, caption: str) -> Dict:
        """Post video to Facebook"""
        
        try:
            url = f"{self.base_url}/{self.page_id}/videos"
            
            with open(file_path, 'rb') as video_file:
                files = {'source': video_file}
                data = {
                    'description': caption,
                    'access_token': self.access_token
                }
                
                response = requests.post(url, files=files, data=data)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    'post_id': result['id'],
                    'platform': 'facebook',
                    'media_type': 'video',
                    'status': 'published',
                    'published_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            raise Exception(f"Facebook video posting failed: {str(e)}")
    
    def _post_text(self, message: str) -> Dict:
        """Post text-only content to Facebook"""
        
        try:
            url = f"{self.base_url}/{self.page_id}/feed"
            data = {
                'message': message,
                'access_token': self.access_token
            }
            
            response = requests.post(url, data=data)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                'post_id': result['id'],
                'platform': 'facebook',
                'media_type': 'text',
                'status': 'published',
                'published_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Facebook text posting failed: {str(e)}")
    
    def get_account_metrics(self) -> Dict:
        """Get Facebook page metrics"""
        
        try:
            # Get basic page info
            page_url = f"{self.base_url}/{self.page_id}"
            page_params = {
                'fields': 'fan_count,talking_about_count,posts',
                'access_token': self.access_token
            }
            
            page_response = self.make_api_request('GET', page_url, params=page_params)
            page_data = page_response.json()
            
            # Get page insights
            insights_url = f"{self.base_url}/{self.page_id}/insights"
            insights_params = {
                'metric': 'page_fans,page_fan_adds,page_fan_removes,page_impressions,page_engaged_users',
                'period': 'day',
                'access_token': self.access_token
            }
            
            insights_response = self.make_api_request('GET', insights_url, params=insights_params)
            insights_data = insights_response.json()
            
            # Process insights
            metrics = {}
            for insight in insights_data.get('data', []):
                metric_name = insight['name']
                values = insight.get('values', [])
                if values:
                    metrics[metric_name] = values[-1]['value']  # Get latest value
            
            # Calculate followers growth
            fan_adds = metrics.get('page_fan_adds', 0)
            fan_removes = metrics.get('page_fan_removes', 0)
            followers_growth = fan_adds - fan_removes
            
            return {
                'followers_count': page_data.get('fan_count', 0),
                'following_count': 0,  # Facebook pages don't follow others
                'posts_count': len(page_data.get('posts', {}).get('data', [])),
                'followers_growth': followers_growth,
                'talking_about_count': page_data.get('talking_about_count', 0),
                'page_impressions': metrics.get('page_impressions', 0),
                'engaged_users': metrics.get('page_engaged_users', 0),
                'engagement_growth': 0.0  # Calculate based on historical data
            }
            
        except Exception as e:
            raise Exception(f"Failed to get Facebook account metrics: {str(e)}")
    
    def get_posts_analytics(self, limit: int = 50) -> List[Dict]:
        """Get analytics for recent Facebook posts"""
        
        try:
            # Get recent posts
            posts_url = f"{self.base_url}/{self.page_id}/posts"
            posts_params = {
                'fields': 'id,message,created_time,type,permalink_url',
                'limit': limit,
                'access_token': self.access_token
            }
            
            posts_response = self.make_api_request('GET', posts_url, params=posts_params)
            posts_data = posts_response.json()
            
            posts_analytics = []
            
            for post in posts_data.get('data', []):
                post_id = post['id']
                
                # Get insights for this post
                insights_url = f"{self.base_url}/{post_id}/insights"
                insights_params = {
                    'metric': 'post_impressions,post_reach,post_engaged_users,post_clicks,post_reactions_like_total,post_reactions_love_total,post_reactions_wow_total,post_reactions_haha_total,post_reactions_sorry_total,post_reactions_anger_total',
                    'access_token': self.access_token
                }
                
                try:
                    insights_response = self.make_api_request('GET', insights_url, params=insights_params)
                    insights_data = insights_response.json()
                    
                    # Process insights
                    analytics = {'post_id': post_id}
                    for insight in insights_data.get('data', []):
                        metric_name = insight['name']
                        values = insight.get('values', [])
                        if values:
                            analytics[metric_name] = values[0]['value']
                    
                    # Calculate total reactions (likes)
                    total_reactions = (
                        analytics.get('post_reactions_like_total', 0) +
                        analytics.get('post_reactions_love_total', 0) +
                        analytics.get('post_reactions_wow_total', 0) +
                        analytics.get('post_reactions_haha_total', 0) +
                        analytics.get('post_reactions_sorry_total', 0) +
                        analytics.get('post_reactions_anger_total', 0)
                    )
                    
                    # Get comments count
                    comments_url = f"{self.base_url}/{post_id}/comments"
                    comments_params = {'summary': 'true', 'access_token': self.access_token}
                    comments_response = self.make_api_request('GET', comments_url, params=comments_params)
                    comments_data = comments_response.json()
                    comments_count = comments_data.get('summary', {}).get('total_count', 0)
                    
                    # Get shares count
                    shares_url = f"{self.base_url}/{post_id}/sharedposts"
                    shares_params = {'summary': 'true', 'access_token': self.access_token}
                    try:
                        shares_response = self.make_api_request('GET', shares_url, params=shares_params)
                        shares_data = shares_response.json()
                        shares_count = shares_data.get('summary', {}).get('total_count', 0)
                    except:
                        shares_count = 0
                    
                    # Calculate engagement rate
                    impressions = analytics.get('post_impressions', 1)
                    total_engagement = total_reactions + comments_count + shares_count
                    engagement_rate = (total_engagement / impressions) * 100 if impressions > 0 else 0
                    
                    final_analytics = {
                        'post_id': post_id,
                        'likes': total_reactions,
                        'comments': comments_count,
                        'shares': shares_count,
                        'views': impressions,
                        'reach': analytics.get('post_reach', 0),
                        'impressions': impressions,
                        'engaged_users': analytics.get('post_engaged_users', 0),
                        'clicks': analytics.get('post_clicks', 0),
                        'engagement_rate': engagement_rate,
                        'created_time': post.get('created_time'),
                        'post_type': post.get('type', 'status')
                    }
                    
                    posts_analytics.append(final_analytics)
                    
                except Exception as e:
                    # Skip posts that don't have insights
                    continue
            
            return posts_analytics
            
        except Exception as e:
            raise Exception(f"Failed to get Facebook posts analytics: {str(e)}")
    
    def _refresh_token(self) -> bool:
        """Refresh Facebook access token"""
        
        try:
            # Exchange short-lived token for long-lived token
            refresh_url = f"{self.base_url}/oauth/access_token"
            refresh_params = {
                'grant_type': 'fb_exchange_token',
                'client_id': settings.FACEBOOK_APP_ID,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'fb_exchange_token': self.access_token
            }
            
            response = requests.get(refresh_url, params=refresh_params)
            response.raise_for_status()
            
            token_data = response.json()
            new_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 5184000)  # Default 60 days
            
            # Update social account with new token
            self.social_account.access_token = new_token
            self.social_account.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            self.access_token = new_token
            
            return True
            
        except Exception as e:
            print(f"Facebook token refresh failed: {e}")
            return False
    
    def validate_file_for_platform(self, file_path: str) -> bool:
        """Validate file for Facebook posting"""
        
        file_type = self.get_file_type(file_path)
        file_size = os.path.getsize(file_path)
        
        if file_type == 'image':
            # Facebook image requirements
            max_size = 4 * 1024 * 1024  # 4MB
            supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            
        elif file_type == 'video':
            # Facebook video requirements
            max_size = 4 * 1024 * 1024 * 1024  # 4GB
            supported_formats = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.f4v', '.mkv']
            
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
        """Get optimal posting times for Facebook"""
        
        # Based on general Facebook engagement patterns
        return ["09:00", "13:00", "15:00", "19:00", "21:00"]
    
    def schedule_post(self, message: str, scheduled_time: datetime, media_path: str = None) -> Dict:
        """Schedule a Facebook post"""
        
        try:
            url = f"{self.base_url}/{self.page_id}/feed"
            
            # Convert datetime to Unix timestamp
            scheduled_publish_time = int(scheduled_time.timestamp())
            
            data = {
                'message': message,
                'published': 'false',  # Don't publish immediately
                'scheduled_publish_time': scheduled_publish_time,
                'access_token': self.access_token
            }
            
            if media_path and os.path.exists(media_path):
                file_type = self.get_file_type(media_path)
                
                if file_type == 'image':
                    # For images, use photos endpoint
                    url = f"{self.base_url}/{self.page_id}/photos"
                    with open(media_path, 'rb') as media_file:
                        files = {'source': media_file}
                        response = requests.post(url, files=files, data=data)
                        
                elif file_type == 'video':
                    # For videos, use videos endpoint
                    url = f"{self.base_url}/{self.page_id}/videos"
                    data['description'] = data.pop('message')  # Videos use description instead of message
                    with open(media_path, 'rb') as media_file:
                        files = {'source': media_file}
                        response = requests.post(url, files=files, data=data)
                else:
                    # Text only
                    response = requests.post(url, data=data)
            else:
                # Text only
                response = requests.post(url, data=data)
            
            response.raise_for_status()
            result = response.json()
            
            return {
                'post_id': result['id'],
                'platform': 'facebook',
                'status': 'scheduled',
                'scheduled_time': scheduled_time.isoformat(),
                'published_at': None
            }
            
        except Exception as e:
            raise Exception(f"Facebook post scheduling failed: {str(e)}")
    
    def get_page_insights(self, metrics: List[str], period: str = 'day') -> Dict:
        """Get detailed page insights"""
        
        try:
            url = f"{self.base_url}/{self.page_id}/insights"
            params = {
                'metric': ','.join(metrics),
                'period': period,
                'access_token': self.access_token
            }
            
            response = self.make_api_request('GET', url, params=params)
            data = response.json()
            
            insights = {}
            for insight in data.get('data', []):
                metric_name = insight['name']
                values = insight.get('values', [])
                insights[metric_name] = values
            
            return insights
            
        except Exception as e:
            raise Exception(f"Failed to get Facebook page insights: {str(e)}")