FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend-builder /app/frontend/dist frontend/dist
COPY data/ data/

EXPOSE 8003
CMD ["python3", "-c", "import sys; sys.path.insert(0,'/app/backend'); import uvicorn; from main import app; uvicorn.run(app, host='0.0.0.0', port=8003)"]
