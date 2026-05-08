# 🏥 AI for Medical Outcomes

> **UCF Senior Design Project · Group 2 · December 2025**  
> Sponsor: Professor Laura Brittain

---

## Overview

**AI for Medical Outcomes** is an agentic AI application designed to assist physicians in diagnosing and predicting outcomes for patients. The system uses a **LangGraph ReAct agentic chatbot** to reason over patient data and clinical context, enabling physicians to ask natural-language questions and receive evidence-grounded diagnostic support.

The backend is built with **FastAPI**, ML inference is served through **AWS SageMaker**, and the application is containerized with **Docker** and deployed serverlessly on **AWS Lambda**.

---

## Key Features

- 🤖 **ReAct Agentic Reasoning** — LangGraph-powered agent that iteratively reasons, retrieves context, and generates clinical responses
- 🧠 **ML Inference Pipeline** — AWS SageMaker handles model hosting and inference for outcome prediction
- ⚡ **Serverless Deployment** — Docker container deployed on AWS Lambda for scalable, cost-efficient hosting
- 🔌 **REST API** — FastAPI backend exposes clean endpoints for frontend and third-party integration
- 🏥 **Clinical Use Case** — Focused on bariatric surgery outcomes, supporting pre-operative risk assessment and post-operative monitoring

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Frontend / Client                  │
└─────────────────────────┬────────────────────────────┘
                          │ HTTP
┌─────────────────────────▼────────────────────────────┐
│              FastAPI Backend (REST API)               │
│           Containerized via Docker on Lambda          │
└──────────┬───────────────────────────┬───────────────┘
           │                           │
┌──────────▼──────────┐   ┌────────────▼──────────────┐
│  LangGraph ReAct    │   │    AWS SageMaker           │
│  Agentic Chatbot    │   │    Inference Pipeline      │
│  (Reasoning Loop)   │   │    (ML Model Hosting)      │
└─────────────────────┘   └───────────────────────────┘
```

The agent follows a **Reason → Act → Observe** loop:
1. **Reason** — interprets the physician's query and patient context
2. **Act** — calls the appropriate tool (SageMaker inference, knowledge retrieval, etc.)
3. **Observe** — processes the result and iterates until a confident answer is formed

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agentic Framework | LangGraph (ReAct pattern) |
| Backend API | FastAPI (Python) |
| ML Inference | AWS SageMaker |
| Containerization | Docker |
| Serverless Compute | AWS Lambda |
| Language | Python 3.11 |

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker
- AWS CLI configured with appropriate IAM permissions
- AWS SageMaker endpoint deployed (see `/infra` for setup)

### Local Development

```bash
# Clone the repository
git clone https://github.com/<your-username>/ai-for-bariatric-outcomes.git
cd ai-for-bariatric-outcomes

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server
uvicorn app.main:app --reload
```

### Docker

```bash
# Build the container
docker build -t ai-bariatric .

# Run locally
docker run -p 8000:8000 ai-bariatric
```

API docs available at `http://localhost:8000/docs` (Swagger UI).

---

## Project Structure

```
.
├── app/
│   ├── main.py          # FastAPI entry point
│   ├── agent/           # LangGraph ReAct agent logic
│   ├── tools/           # Agent tools (SageMaker calls, retrieval)
│   └── schemas/         # Pydantic request/response models
├── infra/               # AWS infrastructure setup (SageMaker, Lambda)
├── notebooks/           # Exploratory analysis and model training
├── Dockerfile
├── requirements.txt
└── README.md
```

---

**Faculty Sponsor:** Professor Laura Brittain, University of Central Florida

---

## Acknowledgments

Built as part of the **UCF Senior Design capstone** (COP 4935)

---

*University of Central Florida · Department of Computer Science*
