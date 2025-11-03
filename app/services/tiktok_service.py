from typing import Dict, List
import requests
import os
from datetime import datetime

from app.services.base_service import BaseSocialMediaService
from app.core.config import settings


class TikTokService(BaseSocialMediaService):
    """TikTok API service for posting and analytics"""
    
    def __init__(self, social_account):
        super().__init__(social_account)
        self.base_url = "https://open-api.tiktok.com"
        self.client_key = settings.TIKTOK_CLIENT_KEY
    
    def post_content(self, file_path: str, caption: str, title: str = None) -> Dict:
        """Upload video to TikTok"""
        
        try:
            file_type = self.get_file_type(file_path)
            
            if file_type != 'video':
                raise Exception("TikTok only supports video uploads")
            
            return self._upload_video(file_path, caption)
                
        except Exception as e:
            raise Exception(f"TikTok upload failed: {str(e)}")
    
    def _upload_video(self, file_path: str, caption: str) -> Dict:
        """Upload video to TikTok"""
        
        try:
            # Step 1: Initialize video upload
            init_url = f"{self.base_url}/v2/post/publish/video/init/"
            
            init_data = {
                'post_info': {
                    'title': caption,
                    'privacy_level': 'SELF_ONLY',  # Can be 'PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY'
                    'disable_duet': False,
                    'disable_comment': False,
                    'disable_stitch': False,
                    'video_cover_timestamp_ms': 1000
                },
                'source_info': {
                    'source': 'FILE_UPLOAD',
                    'video_size': os.path.getsize(file_path),
                    'chunk_size': 10000000,  # 10MB chunks
                    'total_chunk_count': 1
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            init_response = requests.post(init_url, json=init_data, headers=headers)
            init_response.raise_for_status()
            
            init_result = init_response.json()
            
            if init_result['data']['status'] != 'SUCCESS':
                raise Exception(f"TikTok upload initialization failed: {init_result}")
            
            publish_id = init_result['data']['publish_id']
            upload_url = init_result['data']['upload_url']
            
            # Step 2: Upload video file
            with open(file_path, 'rb') as video_file:
                upload_response = requests.put(
                    upload_url,
                    data=video_file,
                    headers={'Content-Type': 'video/mp4'}
                )
                upload_response.raise_for_status()
            
            # Step 3: Commit the upload
            commit_url = f"{self.base_url}/v2/post/publish/status/fetch/"
            commit_data = {
                'publish_id': publish_id
            }
            
            commit_response = requests.post(commit_url, json=commit_data, headers=headers)
            commit_response.raise_for_status()
            
            commit_result = commit_response.json()
            
            return {
                'post_id': publish_id,
                'platform': 'tiktok',
                'media_type': 'video',
                'status': 'published',
                'published_at': datetime.now().isoformat(),
                'caption': caption,
                'upload_status': commit_result['data']['status']
            }
            
        except Exception as e:
            raise Exception(f"TikTok video upload failed: {str(e)}")
    
    def get_account_metrics(self) -> Dict:
        """Get TikTok account metrics"""
        
        try:
            # Get user info
            user_url = f"{self.base_url}/v2/user/info/"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            user_response = self.make_api_request('GET', user_url, headers=headers)
            user_data = user_response.json()
            
            if user_data['data']['status'] != 'SUCCESS':
                raise Exception("Failed to get TikTok user info")
            
            user_info = user_data['data']['user']
            
            return {
                'followers_count': user_info.get('follower_count', 0),
                'following_count': user_info.get('following_count', 0),
                'posts_count': user_info.get('video_count', 0),
                'likes_count': user_info.get('likes_count', 0),
                'followers_growth': 0,  # Calculate from historical data
                'engagement_growth': 0.0,  # Calculate from historical data
                'username': user_info.get('username', ''),
                'display_name': user_info.get('display_name', ''),
                'bio_description': user_info.get('bio_description', '')
            }
            
        except Exception as e:
            raise Exception(f"Failed to get TikTok account metrics: {str(e)}")
    
    def get_posts_analytics(self, limit: int = 50) -> List[Dict]:
        """Get analytics for recent TikTok videos"""
        
        try:
            # Get video list
            videos_url = f"{self.base_url}/v2/video/list/"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            videos_data = {
                'max_count': min(limit, 20),  # API limit
                'cursor': 0
            }
            
            videos_response = self.make_api_request('POST', videos_url, json=videos_data, headers=headers)
            videos_result = videos_response.json()
            
            if videos_result['data']['status'] != 'SUCCESS':
                raise Exception("Failed to get TikTok videos list")
            
            posts_analytics = []
            
            for video in videos_result['data']['videos']:
                # Calculate engagement rate
                views = video.get('view_count', 0)
                likes = video.get('like_count', 0)
                comments = video.get('comment_count', 0)
                shares = video.get('share_count', 0)
                
                total_engagement = likes + comments + shares
                engagement_rate = (total_engagement / views * 100) if views > 0 else 0
                
                analytics = {
                    'post_id': video.get('id', ''),
                    'title': video.get('title', ''),
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'shares': shares,
                    'saves': 0,  # Not available in TikTok API
                    'reach': views,  # Use views as reach approximation
                    'impressions': views,
                    'engagement_rate': engagement_rate,
                    'duration': video.get('duration', 0),
                    'created_at': video.get('create_time', 0),
                    'video_description': video.get('video_description', ''),
                    'cover_image_url': video.get('cover_image_url', '')
                }
                
                posts_analytics.append(analytics)
            
            return posts_analytics
            
        except Exception as e:
            raise Exception(f"Failed to get TikTok posts analytics: {str(e)}")
    
    def _refresh_token(self) -> bool:
        """Refresh TikTok access token"""
        
        try:
            refresh_url = f"{self.base_url}/v2/oauth/token/"
            
            refresh_data = {
                'client_key': self.client_key,
                'client_secret': settings.TIKTOK_CLIENT_SECRET,
                'grant_type': 'refresh_token',
                'refresh_token': self.social_account.refresh_token
            }
            
            response = requests.post(refresh_url, json=refresh_data)
            response.raise_for_status()
            
            token_data = response.json()
            
            if token_data['data']['status'] != 'SUCCESS':
                raise Exception("Token refresh failed")
            
            new_token = token_data['data']['access_token']
            new_refresh_token = token_data['data']['refresh_token']
            expires_in = token_data['data']['expires_in']
            
            # Update social account with new tokens
            self.social_account.access_token = new_token
            self.social_account.refresh_token = new_refresh_token
            self.social_account.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            self.access_token = new_token
            
            return True
            
        except Exception as e:
            print(f"TikTok token refresh failed: {e}")
            return False
    
    def validate_file_for_platform(self, file_path: str) -> bool:
        """Validate file for TikTok upload"""
        
        file_type = self.get_file_type(file_path)
        
        if file_type != 'video':
            return False
        
        file_size = os.path.getsize(file_path)
        
        # TikTok video requirements
        max_size = 4 * 1024 * 1024 * 1024  # 4GB
        min_duration = 3  # 3 seconds minimum
        max_duration = 180  # 3 minutes maximum (for most accounts)
        
        supported_formats = ['.mp4', '.mov', '.avi']
        
        # Check file size
        if file_size > max_size:
            return False
        
        # Check file format
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in supported_formats:
            return False
        
        # TODO: Check video duration using ffprobe or similar
        # For now, assume duration is valid
        
        return True
    
    def get_optimal_posting_times(self) -> List[str]:
        """Get optimal posting times for TikTok"""
        
        # Based on general TikTok engagement patterns
        return ["06:00", "10:00", "19:00", "20:00", "21:00", "22:00"]
    
    def get_video_info(self, video_id: str) -> Dict:
        """Get detailed information about a specific video"""
        
        try:
            video_url = f"{self.base_url}/v2/video/query/"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            video_data = {
                'video_ids': [video_id]
            }
            
            response = self.make_api_request('POST', video_url, json=video_data, headers=headers)
            result = response.json()
            
            if result['data']['status'] != 'SUCCESS':
                raise Exception("Failed to get video info")
            
            if not result['data']['videos']:
                raise Exception("Video not found")
            
            video = result['data']['videos'][0]
            
            return {
                'video_id': video.get('id', ''),
                'title': video.get('title', ''),
                'description': video.get('video_description', ''),
                'duration': video.get('duration', 0),
                'view_count': video.get('view_count', 0),
                'like_count': video.get('like_count', 0),
                'comment_count': video.get('comment_count', 0),
                'share_count': video.get('share_count', 0),
                'create_time': video.get('create_time', 0),
                'cover_image_url': video.get('cover_image_url', ''),
                'video_url': video.get('embed_link', ''),
                'hashtags': video.get('hashtag_names', [])
            }
            
        except Exception as e:
            raise Exception(f"Failed to get TikTok video info: {str(e)}")
    
    def get_hashtag_suggestions(self, keyword: str) -> List[str]:
        """Get hashtag suggestions for a keyword"""
        
        # TikTok doesn't provide a public hashtag suggestion API
        # This is a placeholder that could be implemented using trending hashtags
        # or third-party services
        
        try:
            # For now, return some common hashtags based on keyword
            common_hashtags = [
                f"#{keyword}",
                "#fyp",
                "#foryou",
                "#viral",
                "#trending",
                "#explore",
                "#discover",
                "#entertainment"
            ]
            
            return common_hashtags[:5]  # Return top 5
            
        except Exception as e:
            raise Exception(f"Failed to get hashtag suggestions: {str(e)}")
    
    def check_upload_status(self, publish_id: str) -> Dict:
        """Check the status of a video upload"""
        
        try:
            status_url = f"{self.base_url}/v2/post/publish/status/fetch/"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            status_data = {
                'publish_id': publish_id
            }
            
            response = self.make_api_request('POST', status_url, json=status_data, headers=headers)
            result = response.json()
            
            return {
                'publish_id': publish_id,
                'status': result['data']['status'],
                'fail_reason': result['data'].get('fail_reason', ''),
                'video_id': result['data'].get('video_id', ''),
                'checked_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to check TikTok upload status: {str(e)}")
    
    def delete_video(self, video_id: str) -> Dict:
        """Delete a video from TikTok"""
        
        try:
            delete_url = f"{self.base_url}/v2/post/publish/video/delete/"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json; charset=UTF-8'
            }
            
            delete_data = {
                'video_id': video_id
            }
            
            response = self.make_api_request('POST', delete_url, json=delete_data, headers=headers)
            result = response.json()
            
            return {
                'video_id': video_id,
                'status': result['data']['status'],
                'deleted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to delete TikTok video: {str(e)}")