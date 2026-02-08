#!/bin/bash

# Deployment Script for Web Health Monitor Dashboard
# Usage: ./deploy.sh [host] [user]

HOST=${1:-"your-cloud-ip"}
USER=${2:-"your-ssh-user"}
REMOTE_PATH="/home/$USER/web-health-monitor-dashboard"

echo "🚀 Starting deployment to $HOST..."

ssh $USER@$HOST << EOF
    if [ ! -d "$REMOTE_PATH" ]; then
        echo "📁 Cloning repository..."
        git clone https://github.com/your-username/web-health-monitor-dashboard.git "$REMOTE_PATH"
    fi

    cd "$REMOTE_PATH"
    echo "🔄 Pulling latest changes..."
    git pull origin main

    echo "🏗️ Building and restarting containers..."
    docker-compose up --build -d

    echo "🧹 Cleaning up old images..."
    docker system prune -f

    echo "✅ Deployment successful!"
EOF
