from typing import Dict, List
import os
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

from app.services.base_service import BaseSocialMediaService
from app.core.config import settings


class YouTubeService(BaseSocialMediaService):
    """YouTube API service for posting and analytics"""
    
    def __init__(self, social_account):
        super().__init__(social_account)
        
        # Initialize YouTube API client
        credentials = Credentials(
            token=social_account.access_token,
            refresh_token=social_account.refresh_token,
            client_id=settings.YOUTUBE_CLIENT_ID,
            client_secret=settings.YOUTUBE_CLIENT_SECRET
        )
        
        self.youtube = build('youtube', 'v3', credentials=credentials)
    
    def post_content(self, file_path: str, caption: str, title: str = None) -> Dict:
        """Upload video to YouTube"""
        
        try:
            file_type = self.get_file_type(file_path)
            
            if file_type != 'video':
                raise Exception("YouTube only supports video uploads")
            
            return self._upload_video(file_path, title or "Untitled Video", caption)
                
        except Exception as e:
            raise Exception(f"YouTube upload failed: {str(e)}")
    
    def _upload_video(self, file_path: str, title: str, description: str) -> Dict:
        """Upload video to YouTube"""
        
        try:
            # Video metadata
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': [],  # Can be extracted from description or passed separately
                    'categoryId': '22'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': 'public',  # Can be 'private', 'unlisted', or 'public'
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Create media upload object
            media = MediaFileUpload(
                file_path,
                chunksize=-1,  # Upload in a single chunk
                resumable=True,
                mimetype='video/*'
            )
            
            # Execute upload
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = insert_request.execute()
            
            return {
                'post_id': response['id'],
                'platform': 'youtube',
                'media_type': 'video',
                'status': 'published',
                'published_at': datetime.now().isoformat(),
                'video_url': f"https://www.youtube.com/watch?v={response['id']}",
                'title': title,
                'description': description
            }
            
        except Exception as e:
            raise Exception(f"YouTube video upload failed: {str(e)}")
    
    def get_account_metrics(self) -> Dict:
        """Get YouTube channel metrics"""
        
        try:
            # Get channel statistics
            channels_response = self.youtube.channels().list(
                part='statistics,snippet',
                mine=True
            ).execute()
            
            if not channels_response['items']:
                raise Exception("No YouTube channel found")
            
            channel = channels_response['items'][0]
            stats = channel['statistics']
            
            return {
                'followers_count': int(stats.get('subscriberCount', 0)),
                'following_count': 0,  # YouTube doesn't have following concept
                'posts_count': int(stats.get('videoCount', 0)),
                'total_views': int(stats.get('viewCount', 0)),
                'followers_growth': 0,  # Calculate from historical data
                'engagement_growth': 0.0,  # Calculate from historical data
                'channel_title': channel['snippet'].get('title', ''),
                'channel_description': channel['snippet'].get('description', '')
            }
            
        except Exception as e:
            raise Exception(f"Failed to get YouTube account metrics: {str(e)}")
    
    def get_posts_analytics(self, limit: int = 50) -> List[Dict]:
        """Get analytics for recent YouTube videos"""
        
        try:
            # Get recent videos
            videos_response = self.youtube.search().list(
                part='id,snippet',
                forMine=True,
                type='video',
                order='date',
                maxResults=min(limit, 50)  # API limit
            ).execute()
            
            video_ids = [item['id']['videoId'] for item in videos_response['items']]
            
            if not video_ids:
                return []
            
            # Get video statistics
            stats_response = self.youtube.videos().list(
                part='statistics,snippet',
                id=','.join(video_ids)
            ).execute()
            
            posts_analytics = []
            
            for video in stats_response['items']:
                stats = video['statistics']
                snippet = video['snippet']
                
                # Calculate engagement rate
                views = int(stats.get('viewCount', 0))
                likes = int(stats.get('likeCount', 0))
                comments = int(stats.get('commentCount', 0))
                
                engagement_rate = ((likes + comments) / views * 100) if views > 0 else 0
                
                analytics = {
                    'post_id': video['id'],
                    'title': snippet.get('title', ''),
                    'views': views,
                    'likes': likes,
                    'comments': comments,
                    'shares': 0,  # YouTube doesn't provide share count via API
                    'saves': 0,   # Not available
                    'reach': views,  # Use views as reach approximation
                    'impressions': views,
                    'engagement_rate': engagement_rate,
                    'published_at': snippet.get('publishedAt'),
                    'duration': snippet.get('duration', ''),
                    'thumbnail_url': snippet.get('thumbnails', {}).get('medium', {}).get('url', '')
                }
                
                posts_analytics.append(analytics)
            
            return posts_analytics
            
        except Exception as e:
            raise Exception(f"Failed to get YouTube posts analytics: {str(e)}")
    
    def _refresh_token(self) -> bool:
        """Refresh YouTube access token"""
        
        try:
            from google.auth.transport.requests import Request
            
            credentials = Credentials(
                token=self.access_token,
                refresh_token=self.social_account.refresh_token,
                client_id=settings.YOUTUBE_CLIENT_ID,
                client_secret=settings.YOUTUBE_CLIENT_SECRET
            )
            
            credentials.refresh(Request())
            
            # Update social account with new token
            self.social_account.access_token = credentials.token
            self.social_account.token_expires_at = credentials.expiry
            self.access_token = credentials.token
            
            return True
            
        except Exception as e:
            print(f"YouTube token refresh failed: {e}")
            return False
    
    def validate_file_for_platform(self, file_path: str) -> bool:
        """Validate file for YouTube upload"""
        
        file_type = self.get_file_type(file_path)
        
        if file_type != 'video':
            return False
        
        file_size = os.path.getsize(file_path)
        
        # YouTube video requirements
        max_size = 256 * 1024 * 1024 * 1024  # 256GB (for verified accounts)
        # For unverified accounts, limit is 15 minutes or 2GB
        basic_max_size = 2 * 1024 * 1024 * 1024  # 2GB
        
        supported_formats = ['.mp4', '.mov', '.avi', '.wmv', '.flv', '.webm', '.mkv']
        
        # Check file size (use basic limit for safety)
        if file_size > basic_max_size:
            return False
        
        # Check file format
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension not in supported_formats:
            return False
        
        return True
    
    def get_optimal_posting_times(self) -> List[str]:
        """Get optimal posting times for YouTube"""
        
        # Based on general YouTube engagement patterns
        return ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00"]
    
    def create_playlist(self, title: str, description: str = "", privacy: str = "public") -> Dict:
        """Create a YouTube playlist"""
        
        try:
            body = {
                'snippet': {
                    'title': title,
                    'description': description
                },
                'status': {
                    'privacyStatus': privacy
                }
            }
            
            response = self.youtube.playlists().insert(
                part='snippet,status',
                body=body
            ).execute()
            
            return {
                'playlist_id': response['id'],
                'title': title,
                'description': description,
                'privacy': privacy,
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"YouTube playlist creation failed: {str(e)}")
    
    def add_video_to_playlist(self, playlist_id: str, video_id: str) -> Dict:
        """Add video to YouTube playlist"""
        
        try:
            body = {
                'snippet': {
                    'playlistId': playlist_id,
                    'resourceId': {
                        'kind': 'youtube#video',
                        'videoId': video_id
                    }
                }
            }
            
            response = self.youtube.playlistItems().insert(
                part='snippet',
                body=body
            ).execute()
            
            return {
                'playlist_item_id': response['id'],
                'playlist_id': playlist_id,
                'video_id': video_id,
                'added_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Adding video to playlist failed: {str(e)}")
    
    def schedule_video(self, file_path: str, title: str, description: str, scheduled_time: datetime) -> Dict:
        """Schedule a video for later publishing"""
        
        try:
            # Upload as private first
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': [],
                    'categoryId': '22'
                },
                'status': {
                    'privacyStatus': 'private',
                    'publishAt': scheduled_time.isoformat() + 'Z'  # YouTube expects ISO format with Z
                }
            }
            
            media = MediaFileUpload(
                file_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/*'
            )
            
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            response = insert_request.execute()
            
            return {
                'post_id': response['id'],
                'platform': 'youtube',
                'status': 'scheduled',
                'scheduled_time': scheduled_time.isoformat(),
                'video_url': f"https://www.youtube.com/watch?v={response['id']}",
                'title': title,
                'description': description
            }
            
        except Exception as e:
            raise Exception(f"YouTube video scheduling failed: {str(e)}")
    
    def get_video_analytics(self, video_id: str) -> Dict:
        """Get detailed analytics for a specific video"""
        
        try:
            # Get video statistics
            video_response = self.youtube.videos().list(
                part='statistics,snippet',
                id=video_id
            ).execute()
            
            if not video_response['items']:
                raise Exception("Video not found")
            
            video = video_response['items'][0]
            stats = video['statistics']
            snippet = video['snippet']
            
            return {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'views': int(stats.get('viewCount', 0)),
                'likes': int(stats.get('likeCount', 0)),
                'comments': int(stats.get('commentCount', 0)),
                'published_at': snippet.get('publishedAt'),
                'duration': snippet.get('duration', ''),
                'tags': snippet.get('tags', []),
                'category_id': snippet.get('categoryId', ''),
                'thumbnail_url': snippet.get('thumbnails', {}).get('high', {}).get('url', '')
            }
            
        except Exception as e:
            raise Exception(f"Failed to get YouTube video analytics: {str(e)}")
    
    def search_videos(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for videos on YouTube"""
        
        try:
            search_response = self.youtube.search().list(
                q=query,
                part='id,snippet',
                type='video',
                maxResults=min(limit, 50)
            ).execute()
            
            results = []
            for item in search_response['items']:
                results.append({
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'description': item['snippet']['description'],
                    'channel_title': item['snippet']['channelTitle'],
                    'published_at': item['snippet']['publishedAt'],
                    'thumbnail_url': item['snippet']['thumbnails']['medium']['url']
                })
            
            return results
            
        except Exception as e:
            raise Exception(f"YouTube video search failed: {str(e)}")