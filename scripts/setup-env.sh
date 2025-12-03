#!/bin/bash
# Quick setup script to create .env files for testing
# Usage: ./scripts/setup-env.sh [server|client]

set -e

MODE=${1:-server}

if [ "$MODE" = "server" ]; then
    echo "🐟 Creating .env file for SERVER mode (laptop)"
    echo ""
    echo "Enter your PocketBeagle IP address (e.g., 192.168.1.50):"
    read -r CLIENT_IP
    
    if [ -z "$CLIENT_IP" ]; then
        echo "⚠️  No IP provided. Creating .env without CLIENT_SERVER_URL"
        CLIENT_URL=""
    else
        CLIENT_URL="http://${CLIENT_IP}:8001"
    fi
    
    cat > .env << EOF
# Server Mode Configuration
DEPLOYMENT_MODE=server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
CLIENT_SERVER_URL=${CLIENT_URL}

# STT/TTS run locally on server
STT_MODE=local
STT_MODEL_SIZE=tiny
TTS_MODE=local

# Billy Bass disabled on server (motors are on client)
BILLY_BASS_ENABLED=false
EOF
    
    echo "✅ Created .env file for server mode"
    if [ -n "$CLIENT_URL" ]; then
        echo "   CLIENT_SERVER_URL=${CLIENT_URL}"
    fi
    
elif [ "$MODE" = "client" ]; then
    echo "🐟 Creating .env file for CLIENT mode (PocketBeagle)"
    echo ""
    echo "Enter your laptop/server IP address (e.g., 192.168.1.100):"
    read -r SERVER_IP
    
    if [ -z "$SERVER_IP" ]; then
        echo "⚠️  No IP provided. Using localhost (for testing only)"
        SERVER_IP="localhost"
    fi
    
    cat > .env << EOF
# Client Mode Configuration
DEPLOYMENT_MODE=client

# Connect to server for STT/TTS
STT_MODE=remote
STT_SERVER_URL=http://${SERVER_IP}:8000
STT_TIMEOUT=30.0

TTS_MODE=remote
TTS_SERVER_URL=http://${SERVER_IP}:8000
TTS_TIMEOUT=30.0

# Billy Bass enabled on client (motors are here)
BILLY_BASS_ENABLED=true
EOF
    
    echo "✅ Created .env file for client mode"
    echo "   STT_SERVER_URL=http://${SERVER_IP}:8000"
    echo "   TTS_SERVER_URL=http://${SERVER_IP}:8000"
    
else
    echo "Usage: $0 [server|client]"
    exit 1
fi

echo ""
echo "📝 To start:"
if [ "$MODE" = "server" ]; then
    echo "   fish server --port 8000"
else
    echo "   fish client --port 8001"
fi

