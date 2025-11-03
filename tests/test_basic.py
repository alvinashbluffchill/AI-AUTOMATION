"""Basic tests for the social media automation platform"""

def test_imports():
    """Test that core modules can be imported"""
    try:
        from app.main import app
        from app.core.config import settings
        from app.models.models import User, Post, SocialAccount
        from app.services.base_service import BaseSocialMediaService
        assert True
    except ImportError as e:
        assert False, f"Import failed: {e}"

def test_config_loading():
    """Test configuration loading"""
    from app.core.config import settings
    
    assert settings.SECRET_KEY is not None
    assert settings.ALGORITHM == "HS256"
    assert settings.UPLOAD_DIR == "uploads"
    assert settings.MAX_FILE_SIZE > 0

def test_file_type_detection():
    """Test file type detection utility"""
    from app.services.base_service import BaseSocialMediaService
    from unittest.mock import Mock
    
    service = BaseSocialMediaService(Mock())
    
    assert service.get_file_type("test.jpg") == "image"
    assert service.get_file_type("test.jpeg") == "image"
    assert service.get_file_type("test.png") == "image"
    assert service.get_file_type("test.mp4") == "video"
    assert service.get_file_type("test.mov") == "video"
    assert service.get_file_type("test.avi") == "video"
    assert service.get_file_type("test.txt") == "unknown"

def test_engagement_calculation():
    """Test engagement rate calculation"""
    from app.services.base_service import BaseSocialMediaService
    from unittest.mock import Mock
    
    service = BaseSocialMediaService(Mock())
    
    # Normal case
    rate = service.calculate_engagement_rate(100, 50, 25, 1000)
    expected = ((100 + 50 + 25) / 1000) * 100
    assert rate == expected
    
    # Zero followers edge case
    rate = service.calculate_engagement_rate(100, 50, 25, 0)
    assert rate == 0.0

def test_caption_formatting():
    """Test caption formatting with hashtags"""
    from app.services.base_service import BaseSocialMediaService
    from unittest.mock import Mock
    
    service = BaseSocialMediaService(Mock())
    
    caption = "Great post!"
    hashtags = ["awesome", "#cool", "trending"]
    formatted = service.format_caption(caption, hashtags)
    
    assert "Great post!" in formatted
    assert "#awesome" in formatted
    assert "#cool" in formatted
    assert "#trending" in formatted

if __name__ == "__main__":
    test_imports()
    test_config_loading()
    test_file_type_detection()
    test_engagement_calculation()
    test_caption_formatting()
    print("All basic tests passed!")