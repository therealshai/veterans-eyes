# Veteran's Eyes in one container: builds the app, serves app + API on port 8000.
#   docker build -t veterans-eyes .
#   docker run -p 8000:8000 --env-file .env veterans-eyes      # with your key
#   docker run -p 8000:8000 veterans-eyes                      # demo mode, no key
# Then open http://localhost:8000

# 1) Build the frontend
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Python backend + ffmpeg
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY demo/ demo/
COPY --from=web /web/dist frontend/dist
EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
