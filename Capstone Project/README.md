<h1 align="center">🔷 Usage Metering & Billing Engine</h1>

<p align="center">
  A high-performance backend infrastructure for usage metering and billing orchestration.<br/>
  Enables real-time API event tracking, dynamic quota checks, and automated billing workflows.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python%203.11-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Database-PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/Cache-Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>
</p>

---

## 📌 Overview

This project implements a backend service to track usage metering and handle billing operations for APIs. The engine records client actions, uses **Redis** to verify quotas instantly, and calculates costs. The project is fully containerized, allowing for local execution of the FastAPI server, PostgreSQL, and Redis databases.

---

## ⚙️ How It Works

| Step | Stage | Description |
|------|-------|-------------|
| 1 | **Environment Setup** | Configure local database credentials, cache settings, and external key mappings using `.env`. |
| 2 | **Services Startup** | Build and spin up the backend application, PostgreSQL database, and Redis cache via **Docker Compose**. |
| 3 | **Connectivity Health Check** | Access the `/health` endpoint to trigger automated database connection checks and cache pings. |

---

## 📁 Project Structure

```
Capstone Project/
├── docker-compose.yml             # Local multi-service infrastructure orchestrator
├── README.md                      # Setup and deployment documentation
└── backend/                       # Python API source root
    ├── Dockerfile                 # Container build instructions
    ├── requirements.txt           # Python application dependencies
    ├── .env.example               # Config template containing required environment keys
    ├── .env                       # Active application configuration (not committed)
    └── app/                       # FastAPI application module
        ├── main.py                # Server startup and router registrations
        ├── api/                   # API endpoint controllers
        │   ├── __init__.py
        │   └── routes.py          # /health check implementation
        ├── core/                  # Core configurations
        │   ├── __init__.py
        │   └── config.py          # Pydantic Settings schema
        ├── db/                    # Relational session configuration
        │   ├── __init__.py
        │   └── session.py         # SQLAlchemy Engine & session helper
        ├── models/                # Database models folder (empty for Phase 2)
        │   └── __init__.py
        └── services/              # Business logic routines (empty for Phase 3/4)
            └── __init__.py
```

> **Note:** The local `.env` configuration file is ignored by Git to prevent secrets leakage. Create it manually by copying `.env.example`.

---

## 🚀 Getting Started

### Prerequisites
- **Docker** and **Docker Compose** installed on your machine.
- Optional: **Python 3.11+** installed locally for non-container debugging.

#### Step 1: Initialize Environment Configuration
Copy the template `.env.example` file to create your active `.env` file:
```bash
cp backend/.env.example backend/.env
```

#### Step 2: Spin Up Infrastructure and Application
Start all services (FastAPI, Postgres, and Redis) in detached mode using Docker Compose:
```bash
docker compose up --build -d
```

#### Step 3: Verify API Health Status
Check the status of the running server and verify connection states for both Postgres and Redis:
```bash
curl http://localhost:8000/health
```

Expected healthy response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

---

## 🎨 Configuration Options

| Option | Description | Status |
|--------|-------------|--------|
| `DATABASE_URL` | Relational database connection string | ✅ Active |
| `REDIS_URL` | Redis in-memory cache connection string | ✅ Active |
| `STRIPE_API_KEY` | Secret stripe key for billing checkouts | 💬 Placeholder |
| `STRIPE_WEBHOOK_SECRET` | Secret key to verify Stripe webhook signatures | 💬 Placeholder |
| `ENVIRONMENT` | Target environment designation (e.g. development, production) | ✅ Active |
| `PROJECT_NAME` | Name displayed on FastAPI Swagger document header | ✅ Active |

---

## 🛠️ Tech Stack

| Technology | Role |
|------------|------|
| **FastAPI** | High-performance Python web framework for API routing and request handling. |
| **PostgreSQL** | Relational SQL database for persisting customers, invoices, subscriptions, and events. |
| **Redis** | High-speed cache for counting and enforcing monthly quotas in real-time. |
| **SQLAlchemy** | Modern SQL toolkit and Object-Relational Mapper (ORM) for data operations. |
| **Docker Compose** | Multi-container orchestration tool to replicate production setup locally. |

---

## 📄 License

This project is released under the [MIT License](LICENSE) — free to use, modify, and distribute.

---

<p align="center">
  Built with 🐍 Python &nbsp;·&nbsp; Usage Metering & Billing Engine Capstone
</p>
