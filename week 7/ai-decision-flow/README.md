<h1 align="center">🔷 AI Decision Flow</h1>

<p align="center">
  A visual interactive workflow editor and orchestrator powered by React Flow and Inngest.<br/>
  Create, execute, and monitor AI agent decision chains in real-time.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Language-TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white"/>
  <img src="https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Framework-Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white"/>
  <img src="https://img.shields.io/badge/Queue-Inngest-000000?style=for-the-badge&logo=inngest&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge"/>
</p>

---

## 📌 Overview

This project implements the **AI Decision Flow** editor, enabling users to orchestrate complex sequences of LLM agents and system components. It utilizes a **Vite React** frontend configured with `@xyflow/react` for visual canvas mapping, communicating with a robust **FastAPI** backend that delegates durable step execution via **Inngest**.

---

## ⚙️ How It Works

| Step | Stage | Description |
|------|-------|-------------|
| 1 | **Workflow Design** | User designs decision chains with nodes using **React Flow** editor. |
| 2 | **Event Trigger** | Workflows are triggered by events dispatched to the **Inngest** dev server. |
| 3 | **Step Execution** | The backend FastAPI service runs steps asynchronously, interacting with **OpenAI** APIs. |
| 4 | **State Monitoring** | Real-time statuses and execution logs are tracked inside the **Inngest dashboard**. |

---

## 📁 Project Structure

```
ai-decision-flow/
│
├── backend/               # FastAPI service
│   ├── app/
│   │   ├── core/          # App config & client wrappers
│   │   │   ├── clients.py # Inngest and OpenAI clients
│   │   │   └── config.py  # Pydantic settings loading
│   │   └── main.py        # FastAPI routes & Inngest serve mount
│   ├── .env.example
│   ├── .gitignore
│   └── requirements.txt
│
├── frontend/              # Vite React app
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.css      # Core styles & Tailwind imports
│   │   └── main.tsx
│   ├── .env.example
│   ├── .gitignore
│   ├── package.json
│   └── tailwind.config.js
│
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- **Node.js** v18+
- **Python** v3.10+
- **Inngest CLI** (runnable via npx)

### Setup Steps

#### Step 1: Install Dependencies
Install dependencies for both frontend and backend services:
```bash
# Install backend dependencies
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..

# Install frontend dependencies
cd frontend
npm install
cd ..
```

#### Step 2: Configure Environment Variables
Create `.env` files in both directories:
```bash
# Backend Env Setup
cp backend/.env.example backend/.env
# (Update backend/.env with your OpenAI API Key)

# Frontend Env Setup
cp frontend/.env.example frontend/.env
```

#### Step 3: Run Services
Start the backend API, the Inngest Dev Server, and the frontend server:
```bash
# Start Backend (Terminal 1)
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Start Inngest Dev Server (Terminal 2)
npx inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest

# Start Frontend (Terminal 3)
cd frontend
npm run dev
```

---

## 🛠️ Tech Stack

| Technology | Role |
|------------|------|
| **FastAPI** | High-performance Python backend framework |
| **Inngest** | Event-driven queue and orchestration engine |
| **React + Vite** | Modern frontend framework and build tool |
| **React Flow** | Flowchart library for nodes and edge-based UI mapping |
| **Tailwind CSS** | Utility-first CSS styling for component views |
| **OpenAI SDK** | API client for LLM processing inside workflows |

---

## 📄 License

This project is released under the [MIT License](LICENSE) — free to use, modify, and distribute.

---

<p align="center">
  Built with 🧠 AI &amp; ⚙️ Inngest &nbsp;·&nbsp; FlyRank AI Internship
</p>
