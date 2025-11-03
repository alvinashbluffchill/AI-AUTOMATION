from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import requests
from datetime import datetime


class BaseSocialMediaService(ABC):
    """Base class for social media platform services"""
    
    def __init__(self, social_account):
        self.social_account = social_account
        self.access_token = social_account.access_token
        self.platform = social_account.platform
        
    @abstractmethod
    def post_content(self, file_path: str, caption: str, title: str = None) -> Dict:
        """Post content to the platform"""
        pass
    
    @abstractmethod
    def get_account_metrics(self) -> Dict:
        """Get account-level metrics"""
        pass
    
    @abstractmethod
    def get_posts_analytics(self, limit: int = 50) -> List[Dict]:
        """Get analytics for recent posts"""
        pass
    
    def validate_token(self) -> bool:
        """Validate if the access token is still valid"""
        try:
            # This should be implemented by each platform service
            return True
        except Exception:
            return False
    
    def refresh_token_if_needed(self) -> bool:
        """Refresh token if it's expired"""
        try:
            # Check if token needs refresh
            if self.social_account.token_expires_at:
                if datetime.now() >= self.social_account.token_expires_at:
                    return self._refresh_token()
            return True
        except Exception:
            return False
    
    @abstractmethod
    def _refresh_token(self) -> bool:
        """Platform-specific token refresh logic"""
        pass
    
    def make_api_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make authenticated API request with error handling"""
        
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        kwargs['headers'] = headers
        
        try:
            response = requests.request(method, url, **kwargs)
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise Exception(f"Rate limited. Retry after {retry_after} seconds")
            
            # Handle authentication errors
            if response.status_code == 401:
                if self.refresh_token_if_needed():
                    # Retry with new token
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    kwargs['headers'] = headers
                    response = requests.request(method, url, **kwargs)
                else:
                    raise Exception("Authentication failed and token refresh failed")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
    
    def upload_media(self, file_path: str) -> Dict:
        """Upload media file to platform"""
        # This should be implemented by each platform service
        raise NotImplementedError("upload_media must be implemented by platform service")
    
    def format_caption(self, caption: str, hashtags: List[str] = None) -> str:
        """Format caption with hashtags"""
        formatted_caption = caption
        
        if hashtags:
            hashtag_string = " ".join([f"#{tag.strip('#')}" for tag in hashtags])
            formatted_caption = f"{caption}\n\n{hashtag_string}"
        
        return formatted_caption
    
    def get_file_type(self, file_path: str) -> str:
        """Determine file type from file path"""
        import os
        
        extension = os.path.splitext(file_path)[1].lower()
        
        if extension in ['.jpg', '.jpeg', '.png', '.gif']:
            return 'image'
        elif extension in ['.mp4', '.avi', '.mov']:
            return 'video'
        else:
            return 'unknown'
    
    def validate_file_for_platform(self, file_path: str) -> bool:
        """Validate if file is supported by the platform"""
        # This should be implemented by each platform service
        return True
    
    def get_optimal_posting_times(self) -> List[str]:
        """Get optimal posting times for the platform"""
        # Default times - should be customized per platform
        return ["09:00", "12:00", "15:00", "18:00", "21:00"]
    
    def calculate_engagement_rate(self, likes: int, comments: int, shares: int, followers: int) -> float:
        """Calculate engagement rate"""
        if followers == 0:
            return 0.0
        
        total_engagement = likes + comments + shares
        return (total_engagement / followers) * 100
    
    def format_analytics_data(self, raw_data: Dict) -> Dict:
        """Format raw analytics data into standardized format"""
        # This should be implemented by each platform service
        return raw_data