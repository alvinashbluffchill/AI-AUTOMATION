from typing import Dict, List
import requests
import os
from datetime import datetime

from app.services.base_service import BaseSocialMediaService
from app.core.config import settings


class InstagramService(BaseSocialMediaService):
    """Instagram API service for posting and analytics"""
    
    def __init__(self, social_account):
        super().__init__(social_account)
        self.base_url = "https://graph.facebook.com/v18.0"
        self.instagram_account_id = social_account.platform_data.get('instagram_account_id') if social_account.platform_data else None
    
    def post_content(self, file_path: str, caption: str, title: str = None) -> Dict:
        """Post content to Instagram"""
        
        try:
            if not self.instagram_account_id:
                raise Exception("Instagram account ID not configured")
            
            file_type = self.get_file_type(file_path)
            
            if file_type == 'image':
                return self._post_image(file_path, caption)
            elif file_type == 'video':
                return self._post_video(file_path, caption)
            else:
                raise Exception(f"Unsupported file type: {file_type}")
                
        except Exception as e:
            raise Exception(f"Instagram posting failed: {str(e)}")
    
    def _post_image(self, file_path: str, caption: str) -> Dict:
        """Post image to Instagram"""
        
        # Step 1: Upload image and get media ID
        upload_url = f"{self.base_url}/{self.instagram_account_id}/media"
        
        with open(file_path, 'rb') as image_file:
            files = {'source': image_file}
            data = {
                'caption': caption,
                'access_token': self.access_token
            }
            
            response = requests.post(upload_url, files=files, data=data)
            response.raise_for_status()
            
            media_data = response.json()
            media_id = media_data['id']
        
        # Step 2: Publish the media
        publish_url = f"{self.base_url}/{self.instagram_account_id}/media_publish"
        publish_data = {
            'creation_id': media_id,
            'access_token': self.access_token
        }
        
        publish_response = requests.post(publish_url, data=publish_data)
        publish_response.raise_for_status()
        
        result = publish_response.json()
        
        return {
            'post_id': result['id'],
            'platform': 'instagram',
            'media_type': 'image',
            'status': 'published',
            'published_at': datetime.now().isoformat()
        }
    
    def _post_video(self, file_path: str, caption: str) -> Dict:
        """Post video to Instagram"""
        
        # Step 1: Upload video and get media ID
        upload_url = f"{self.base_url}/{self.instagram_account_id}/media"
        
        with open(file_path, 'rb') as video_file:
            files = {'source': video_file}
            data = {
                'caption': caption,
                'media_type': 'VIDEO',
                'access_token': self.access_token
            }
            
            response = requests.post(upload_url, files=files, data=data)
            response.raise_for_status()
            
            media_data = response.json()
            media_id = media_data['id']
        
        # Step 2: Check upload status (videos need processing time)
        status_url = f"{self.base_url}/{media_id}"
        status_params = {'fields': 'status_code', 'access_token': self.access_token}
        
        # Poll for completion (simplified - in production, use proper async handling)
        import time
        max_attempts = 30
        for _ in range(max_attempts):
            status_response = requests.get(status_url, params=status_params)
            status_data = status_response.json()
            
            if status_data.get('status_code') == 'FINISHED':
                break
            elif status_data.get('status_code') == 'ERROR':
                raise Exception("Video processing failed")
            
            time.sleep(2)
        
        # Step 3: Publish the video
        publish_url = f"{self.base_url}/{self.instagram_account_id}/media_publish"
        publish_data = {
            'creation_id': media_id,
            'access_token': self.access_token
        }
        
        publish_response = requests.post(publish_url, data=publish_data)
        publish_response.raise_for_status()
        
        result = publish_response.json()
        
        return {
            'post_id': result['id'],
            'platform': 'instagram',
            'media_type': 'video',
            'status': 'published',
            'published_at': datetime.now().isoformat()
        }
    
    def get_account_metrics(self) -> Dict:
        """Get Instagram account metrics"""
        
        try:
            url = f"{self.base_url}/{self.instagram_account_id}"
            params = {
                'fields': 'followers_count,follows_count,media_count',
                'access_token': self.access_token
            }
            
            response = self.make_api_request('GET', url, params=params)
            data = response.json()
            
            # Get insights for growth metrics
            insights_url = f"{self.base_url}/{self.instagram_account_id}/insights"
            insights_params = {
                'metric': 'follower_count,profile_views,reach,impressions',
                'period': 'day',
                'access_token': self.access_token
            }
            
            insights_response = self.make_api_request('GET', insights_url, params=insights_params)
            insights_data = insights_response.json()
            
            # Process insights data
            metrics = {}
            for insight in insights_data.get('data', []):
                metric_name = insight['name']
                values = insight.get('values', [])
                if values:
                    metrics[metric_name] = values[-1]['value']  # Get latest value
            
            return {
                'followers_count': data.get('followers_count', 0),
                'following_count': data.get('follows_count', 0),
                'posts_count': data.get('media_count', 0),
                'followers_growth': metrics.get('follower_count', 0),
                'profile_views': metrics.get('profile_views', 0),
                'reach': metrics.get('reach', 0),
                'impressions': metrics.get('impressions', 0),
                'engagement_growth': 0.0  # Calculate based on historical data
            }
            
        except Exception as e:
            raise Exception(f"Failed to get Instagram account metrics: {str(e)}")
    
    def get_posts_analytics(self, limit: int = 50) -> List[Dict]:
        """Get analytics for recent Instagram posts"""
        
        try:
            # Get recent media
            media_url = f"{self.base_url}/{self.instagram_account_id}/media"
            media_params = {
                'fields': 'id,media_type,timestamp,permalink',
                'limit': limit,
                'access_token': self.access_token
            }
            
            media_response = self.make_api_request('GET', media_url, params=media_params)
            media_data = media_response.json()
            
            posts_analytics = []
            
            for media in media_data.get('data', []):
                media_id = media['id']
                
                # Get insights for this media
                insights_url = f"{self.base_url}/{media_id}/insights"
                insights_params = {
                    'metric': 'impressions,reach,likes,comments,saves,shares',
                    'access_token': self.access_token
                }
                
                try:
                    insights_response = self.make_api_request('GET', insights_url, params=insights_params)
                    insights_data = insights_response.json()
                    
                    # Process insights
                    analytics = {'post_id': media_id}
                    for insight in insights_data.get('data', []):
                        metric_name = insight['name']
                        value = insight.get('values', [{}])[0].get('value', 0)
                        analytics[metric_name] = value
                    
                    # Calculate engagement rate
                    likes = analytics.get('likes', 0)
                    comments = analytics.get('comments', 0)
                    shares = analytics.get('shares', 0)
                    impressions = analytics.get('impressions', 1)  # Avoid division by zero
                    
                    analytics['engagement_rate'] = ((likes + comments + shares) / impressions) * 100
                    analytics['media_type'] = media.get('media_type', 'IMAGE')
                    analytics['timestamp'] = media.get('timestamp')
                    
                    posts_analytics.append(analytics)
                    
                except Exception as e:
                    # Skip posts that don't have insights (e.g., too recent)
                    continue
            
            return posts_analytics
            
        except Exception as e:
            raise Exception(f"Failed to get Instagram posts analytics: {str(e)}")
    
    def _refresh_token(self) -> bool:
        """Refresh Instagram access token"""
        
        try:
            # Instagram uses long-lived tokens that need to be refreshed every 60 days
            refresh_url = f"{self.base_url}/oauth/access_token"
            refresh_data = {
                'grant_type': 'fb_exchange_token',
                'client_id': settings.FACEBOOK_APP_ID,
                'client_secret': settings.FACEBOOK_APP_SECRET,
                'fb_exchange_token': self.access_token
            }
            
            response = requests.post(refresh_url, data=refresh_data)
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
            print(f"Instagram token refresh failed: {e}")
            return False
    
    def validate_file_for_platform(self, file_path: str) -> bool:
        """Validate file for Instagram posting"""
        
        file_type = self.get_file_type(file_path)
        file_size = os.path.getsize(file_path)
        
        if file_type == 'image':
            # Instagram image requirements
            max_size = 8 * 1024 * 1024  # 8MB
            supported_formats = ['.jpg', '.jpeg', '.png']
            
        elif file_type == 'video':
            # Instagram video requirements
            max_size = 100 * 1024 * 1024  # 100MB
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
        """Get optimal posting times for Instagram"""
        
        # Based on general Instagram engagement patterns
        return ["08:00", "11:00", "14:00", "17:00", "19:00", "21:00"]