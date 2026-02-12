#!/bin/bash

# Deployment Script for Web Health Monitor Dashboard
# This script is used by GitHub Actions or can be run manually.

# Configuration
HOST=${1}
USER=${2}
REPO_URL="https://github.com/qaisamro/web-health-monitor.git"

if [[ -z "$HOST" || -z "$USER" ]]; then
    echo "❌ Error: Missing arguments."
    echo "Usage: ./deploy.sh [host] [user]"
    exit 1
fi

REMOTE_PATH="/home/$USER/web-health-monitor-dashboard"

echo "🚀 Starting deployment to $HOST as $USER..."

ssh -o StrictHostKeyChecking=no $USER@$HOST << EOF
    if [ ! -d "$REMOTE_PATH" ]; then
        echo "📁 Cloning repository..."
        git clone "$REPO_URL" "$REMOTE_PATH"
    fi

    cd "$REMOTE_PATH"
    echo "🔄 Fetching and resetting to latest main..."
    git fetch origin main
    git reset --hard origin/main

    echo "🏗️ Building and restarting containers..."
    docker-compose up --build -d

    echo "🧹 Cleaning up old images..."
    docker system prune -f

    echo "✅ Deployment successful!"
EOF
