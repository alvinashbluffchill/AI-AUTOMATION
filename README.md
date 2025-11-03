# Social Media Automation Platform

A comprehensive social media automation platform that allows you to upload, schedule, and manage content across multiple social media platforms with advanced analytics and growth tracking.

## Features

### 🚀 Core Features
- **Multi-Platform Support**: Instagram, Facebook, Twitter, YouTube, TikTok
- **File Upload & Management**: Support for images and videos with automatic processing
- **Automated Scheduling**: Time-based posting with flexible scheduling options
- **Analytics Dashboard**: Comprehensive growth metrics and engagement tracking
- **Line-by-Line Video Management**: Organize and schedule video content efficiently

### 📊 Analytics & Insights
- Real-time follower growth tracking
- Engagement rate analysis
- Post performance metrics
- Cross-platform analytics comparison
- Automated daily/weekly reports

### ⚡ Automation Features
- Background task processing with Celery
- Automatic file compression and optimization
- Thumbnail generation for videos
- Recurring post schedules
- Batch upload and scheduling

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLAlchemy with SQLite/PostgreSQL
- **Task Queue**: Celery with Redis
- **Frontend**: React with Tailwind CSS
- **File Processing**: FFmpeg, Pillow
- **Social Media APIs**: Official platform APIs

## Quick Start

### Prerequisites
- Python 3.11+
- Redis server
- FFmpeg (for video processing)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd social_media_automation
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Start Redis server**
   ```bash
   redis-server
   ```

5. **Run database migrations**
   ```bash
   python -c "from app.core.database import engine; from app.models import models; models.Base.metadata.create_all(bind=engine)"
   ```

6. **Start the application**
   ```bash
   # Terminal 1: FastAPI server
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   
   # Terminal 2: Celery worker
   celery -A app.tasks.celery_app worker --loglevel=info
   
   # Terminal 3: Celery beat scheduler
   celery -A app.tasks.celery_app beat --loglevel=info
   
   # Terminal 4: Flower monitoring (optional)
   celery -A app.tasks.celery_app flower --port=5555
   ```

7. **Access the application**
   - Web Interface: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Flower Monitoring: http://localhost:5555

### Docker Setup (Recommended)

1. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Access the application**
   - Web Interface: http://localhost:8000
   - Flower Monitoring: http://localhost:5555

## Configuration

### Social Media API Setup

#### Instagram/Facebook
1. Create a Facebook Developer account
2. Create a new app and get App ID and App Secret
3. Set up Instagram Basic Display API
4. Get long-lived access token

#### Twitter
1. Create a Twitter Developer account
2. Create a new app and get API keys
3. Generate access tokens

#### YouTube
1. Create a Google Cloud project
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials
4. Get refresh token

#### TikTok
1. Register for TikTok for Developers
2. Create a new app
3. Get client key and secret
4. Implement OAuth flow

### Environment Variables

Key configuration options in `.env`:

```env
# Database
DATABASE_URL=sqlite:///./social_media_automation.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key

# File Upload
UPLOAD_DIR=uploads
MAX_FILE_SIZE=104857600  # 100MB

# Social Media APIs (add your keys)
FACEBOOK_APP_ID=your_app_id
TWITTER_API_KEY=your_api_key
# ... etc
```

## Usage

### 1. Upload Content
- Drag and drop files or browse to select
- Supports images (JPG, PNG, GIF) and videos (MP4, MOV, AVI)
- Automatic file processing and thumbnail generation

### 2. Schedule Posts
- Select uploaded content
- Choose target platforms
- Set posting time and date
- Bulk scheduling available

### 3. Monitor Analytics
- View real-time follower growth
- Track engagement metrics
- Compare performance across platforms
- Export analytics reports

### 4. Manage Content
- View all uploaded and scheduled posts
- Edit post details and scheduling
- Delete or reschedule content
- Monitor posting status

## API Endpoints

### File Upload
- `POST /api/upload/file` - Upload single file
- `POST /api/upload/multiple` - Upload multiple files
- `GET /api/upload/posts` - Get user posts
- `DELETE /api/upload/posts/{id}` - Delete post

### Scheduling
- `POST /api/schedule/create` - Create schedule
- `POST /api/schedule/post` - Schedule single post
- `GET /api/schedule/list` - List schedules
- `PUT /api/schedule/{id}/toggle` - Toggle schedule

### Analytics
- `GET /api/analytics/overview` - Analytics overview
- `GET /api/analytics/platform/{platform}` - Platform analytics
- `GET /api/analytics/posts/{id}` - Post analytics
- `POST /api/analytics/sync/{platform}` - Sync analytics

### Authentication
- `POST /api/auth/register` - Register user
- `POST /api/auth/token` - Login
- `GET /api/auth/me` - Get current user

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │  FastAPI Backend │    │   Celery Tasks  │
│   (React)       │◄──►│   (Python)      │◄──►│   (Background)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   PostgreSQL    │    │      Redis      │
                       │   (Database)    │    │  (Message Queue)│
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  Social Media   │
                       │      APIs       │
                       └─────────────────┘
```

## Development

### Project Structure
```
social_media_automation/
├── app/
│   ├── api/           # API endpoints
│   ├── core/          # Configuration and database
│   ├── models/        # Database models
│   ├── services/      # Social media services
│   ├── tasks/         # Celery background tasks
│   └── main.py        # FastAPI application
├── frontend/          # React frontend
├── uploads/           # File storage
├── logs/              # Application logs
├── requirements.txt   # Python dependencies
├── docker-compose.yml # Docker configuration
└── README.md
```

### Adding New Platforms

1. Create a new service in `app/services/`
2. Inherit from `BaseSocialMediaService`
3. Implement required methods:
   - `post_content()`
   - `get_account_metrics()`
   - `get_posts_analytics()`
   - `_refresh_token()`

4. Add platform to supported platforms list
5. Update frontend platform options

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

## Deployment

### Production Deployment

1. **Set up production environment**
   ```bash
   # Use PostgreSQL instead of SQLite
   DATABASE_URL=postgresql://user:pass@localhost:5432/db
   
   # Use strong secret key
   SECRET_KEY=your-production-secret-key
   
   # Configure social media API keys
   ```

2. **Deploy with Docker**
   ```bash
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Set up reverse proxy (Nginx)**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

### Monitoring

- **Application Logs**: Check `logs/` directory
- **Celery Monitoring**: Use Flower at http://localhost:5555
- **Database Monitoring**: Use PostgreSQL monitoring tools
- **Redis Monitoring**: Use Redis CLI or monitoring tools

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   - Ensure Redis server is running
   - Check REDIS_URL in environment variables

2. **Social Media API Errors**
   - Verify API keys and tokens
   - Check rate limits and quotas
   - Ensure proper OAuth setup

3. **File Upload Issues**
   - Check file size limits
   - Verify upload directory permissions
   - Ensure FFmpeg is installed for video processing

4. **Celery Tasks Not Running**
   - Check Celery worker is running
   - Verify Redis connection
   - Check task logs for errors

### Support

For issues and questions:
1. Check the logs in `logs/` directory
2. Review API documentation at `/docs`
3. Monitor Celery tasks in Flower
4. Check social media platform API status

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Roadmap

- [ ] AI-powered content optimization
- [ ] Advanced scheduling algorithms
- [ ] Multi-user support with teams
- [ ] Mobile app
- [ ] Integration with more platforms (LinkedIn, Pinterest)
- [ ] Advanced analytics with ML insights
- [ ] Content calendar view
- [ ] Automated hashtag suggestions