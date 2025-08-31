# 🤖 AI Agentic Retail Management System

A comprehensive, AI-powered retail management platform built with FastAPI that automates and streamlines retail operations through intelligent agents and modern web technologies.

## 🚀 Features

### Core Modules
- **🔐 Authentication & Authorization** - JWT-based security with role-based permissions
- **📦 Inventory Management** - Real-time stock tracking, automated reordering, transfers
- **👥 Human Resources** - Employee management, attendance tracking, payroll processing
- **🛒 Purchase Management** - Purchase orders, supplier management, goods receipts
- **🚛 Logistics & Shipping** - Shipment tracking, driver/vehicle management, OTP verification
- **📊 Task Management** - Automated task creation, assignment, and tracking
- **💬 AI Chat Integration** - Intelligent conversational AI for system interactions
- **📈 Analytics & Reporting** - Real-time dashboards and comprehensive reports

### AI-Powered Features
- **🤖 Automated Task Generation** - Smart task creation based on system events
- **📋 Intelligent Stock Management** - AI-driven reorder suggestions and stock optimization
- **🎯 Predictive Analytics** - Forecasting and trend analysis
- **🔄 Process Automation** - Workflow automation with custom rules

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL with SQLAlchemy (Async)
- **Cache/Queue:** Redis + Celery
- **Authentication:** JWT with role-based access control
- **Biometrics:** Fingerprint authentication support
- **Containerization:** Docker & Docker Compose
- **API Documentation:** Automatic OpenAPI/Swagger generation

## 🏗️ Architecture
├── app/
│   ├── api/v1/endpoints/     # API route handlers
│   ├── models/               # Database models
│   ├── services/             # Business logic layer
│   ├── schemas/              # Pydantic models
│   ├── core/                 # Configuration & utilities
│   └── auth/                 # Authentication system
├── migrations/               # Database migrations
├── tests/                    # Test suites
└── docker-compose.yml        # Container orchestration


## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)

### Using Docker (Recommended)
```bash
# Clone the repository
git clone https://github.com/Parbaz-Hossain/ai-retail-backend.git
cd ai-retail-backend

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec app alembic upgrade head

# Access the application
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
Local Development
bash# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env

# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start the application
uvicorn app.main:app --reload
📊 API Documentation
Once running, access the interactive API documentation:

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

🔧 Configuration
Key environment variables (see .env.example):
envDATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
🧪 Testing
bash# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/
📱 Mobile Support
The system includes mobile-optimized endpoints for:

Task management dashboard
Employee attendance tracking
Inventory scanning and management
Real-time notifications

🤝 Contributing

Fork the repository
Create your feature branch (git checkout -b feature/amazing-feature)
Commit your changes (git commit -m 'Add amazing feature')
Push to the branch (git push origin feature/amazing-feature)
Open a Pull Request

📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
🆘 Support

📧 Email: support@ai-retail-system.com
📖 Documentation: docs.ai-retail-system.com
🐛 Issues: GitHub Issues


Built with ❤️ by the ESAP AI Retail Team
