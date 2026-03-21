FROM python:3.11-slim

WORKDIR /app

# Install dependencies (reuses the existing FastAPI backend requirements)
COPY src/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole repo (scaffolding; you can narrow later)
COPY . .

# Ensure Python can import `services.*`
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

