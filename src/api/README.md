# API Backend

FastAPI REST server connecting Python RAG system to Flutter mobile app.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
python main.py
```

Server runs on `http://localhost:8000`

## Files

- `main.py` - FastAPI application
- `models.py` - Pydantic request/response schemas
- `assessment_engine.py` - Bayesian assessment logic
- `rag_client.py` - RAG system wrapper
- `test_api.py` - Interactive testing tool

## Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `POST /api/assess` - Clinical assessment

## Testing

```bash
# Interactive test (asks questions)
python test_api.py
```

## API Documentation

Visit http://localhost:8000/docs for Swagger UI

## Deployment

For production deployment, use:
- **Render**: Easy deployment (free tier available)
- **Railway**: $5/month, automatic scaling
- **AWS EC2**: More control, requires setup

Remember to:
1. Set proper CORS origins (not `*`)
2. Use environment variables for config
3. Enable HTTPS
4. Add rate limiting
