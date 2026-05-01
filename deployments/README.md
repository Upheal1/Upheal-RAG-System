# UpHeal Deployment Configurations

## Overview

This directory contains deployment configurations for various hosting providers.

## Free Options (Recommended)

### Option 1: Render (Free Tier)

**Best for: Graduation project demo**

```bash
# Set these in Render dashboard:
UPHEAL_CHROMA_PATH=local
UPHEAL_CHROMA_COLLECTION=clinical_knowledge
# Use OpenAI free tier or local Ollama for LLM
OPENAI_API_KEY=sk-...  # or leave empty for demo
```

**Steps:**
1. Create Web Service on Render
2. Connect GitHub repo
3. Set Build Command: `pip install -r requirements.txt`
4. Set Start Command: `python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000`
5. Add environment variables
6. Deploy

**Note:** Free tier sleeps after 15min of inactivity.

### Option 2: Fly.io (Free Tier)

```bash
fly launch
fly deploy
```

## Paid Options

### Railway ($5-20/mo)

See `railway.json` for configuration.

### Railway + Ollama (Self-hosted LLM)

See `docker-compose.yml` for full stack.

## Environment Variables

See [`.env.example`](./.env.example) for all variables.

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  Flutter    │────▶│  Gateway    │
│  Mobile App │     │  (FastAPI)  │
└─────────────┘     └──────┬──────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
         ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  ChromaDB   │  │  LLM API    │  │  Firebase   │
│  (Vectors)  │  │  (OpenAI)   │  │  (Auth)     │
└─────────────┘  └─────────────┘  └─────────────┘
```