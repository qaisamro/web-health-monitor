FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if any (none needed for now)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port for FastAPI
EXPOSE 8000

# We don't specify CMD here, we will override it in docker-compose.yml
