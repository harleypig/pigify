# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend with frontend static files
FROM python:3.11-slim AS backend-builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: Production image
FROM python:3.11-slim
WORKDIR /app

# Copy Python dependencies
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy backend application
COPY backend/ ./backend/

# Copy frontend static files
COPY --from=frontend-builder /app/frontend/dist ./static

# Set PYTHONPATH to include the project root
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

