# Nexus AI: The Liquid Intelligence Orchestrator

![Nexus Banner](docs/assets/banner.png)

## 🏗️ Enterprise Architecture
Nexus AI is built on a high-performance, distributed microservices architecture designed for ultra-low latency and scalable AI reasoning.

![Architecture Diagram](docs/assets/architecture.png)

### Core Pillars:
1. **Liquid Intelligence UI**: A Next.js 14 frontend powered by Framer Motion physics and glassmorphism, delivering a zero-friction user experience.
2. **Neural Grid Backend**: A FastAPI-driven core optimizing VRAM usage for local LLM orchestration.
3. **Semantic Memory Layer**: Integrated Vector database (Qdrant) for long-term neural recall and RAG.
4. **Execution Clusters**: Distributed Celery workers for complex long-running DAG workflows.

---

## 🚀 Advanced Tech Implementations
- **Dynamic VRAM Scaling**: Intelligent model swapping to run high-utility models on consumer-grade hardware (optimized for 4GB VRAM).
- **Interactive DAG Workflows**: Real-time pipeline visualization and execution.
- **Glassmorphism Design System**: A custom CSS theme engine ("Liquid Magenta") providing consistent, fluid aesthetics.

![Tech Stack](docs/assets/tech_stack.png)

---

## 🛠️ Installation & Setup (100% Potential)

### 1. Prerequisites
- **Docker Desktop** (Infrastructure)
- **Python 3.10+** (Backend)
- **Node.js 18+** (Frontend)
- **Ollama** (AI Models)

### 2. Quick Start
```bash
# Clone the repository
git clone https://github.com/[YOUR_USERNAME]/nexus-ai-orchestrator.git
cd nexus-ai-orchestrator

# Initialize Infrastructure
./start.ps1
```

### 3. Manual Initialization
If not using the starter script:
```bash
# Infrastructure
docker-compose up -d

# Backend
python -m venv venv
./venv/Scripts/activate
pip install -r requirements.txt
python -m api.main

# Frontend
cd web
npm install
npm run dev
```

---

## 🔧 Troubleshooting Commands
| Issue | Command |
|-------|---------|
| Model Connectivity | `curl http://localhost:11434/api/tags` |
| Backend Health | `curl http://localhost:8000/health` |
| Database Reset | `docker-compose down -v && docker-compose up -d` |
| Worker Logs | `celery -A api.worker.celery_app inspect ping` |

---

## 🌟 Why Nexus?
Nexus stands at the intersection of **Aesthetics** and **Efficiency**. Unlike generic AI wrappers, Nexus manages its own memory clusters, optimizes for hardware-constrained environments, and provides a truly premium enterprise interface.
