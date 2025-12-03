#!/bin/bash
# Quick test script for Fish Assistant
# Usage: ./scripts/quick-test.sh [server|client]

set -e

MODE=${1:-server}

if [ "$MODE" = "server" ]; then
    echo "🐟 Starting Fish Assistant Server Mode"
    echo ""
    echo "📋 Quick Setup:"
    echo "1. Find your PocketBeagle IP:"
    echo "   ssh pocketbeagle 'hostname -I'"
    echo ""
    echo "2. Set CLIENT_SERVER_URL:"
    echo "   export CLIENT_SERVER_URL=http://<pocketbeagle-ip>:8001"
    echo ""
    echo "3. Or use --client-url flag:"
    echo "   fish server --port 8000 --client-url http://<pocketbeagle-ip>:8001"
    echo ""
    
    if [ -z "$CLIENT_SERVER_URL" ]; then
        echo "⚠️  CLIENT_SERVER_URL not set. Starting without client push."
        echo "   Set it to enable audio push to PocketBeagle."
        echo ""
    fi
    
    fish server --port 8000 ${CLIENT_SERVER_URL:+--client-url $CLIENT_SERVER_URL}
    
elif [ "$MODE" = "client" ]; then
    echo "🐟 Starting Fish Assistant Client Mode"
    echo ""
    echo "📋 Quick Setup:"
    echo "1. Find your laptop IP:"
    echo "   ifconfig | grep 'inet ' | grep -v 127.0.0.1"
    echo ""
    echo "2. Set server URLs:"
    echo "   export STT_SERVER_URL=http://<laptop-ip>:8000"
    echo "   export TTS_SERVER_URL=http://<laptop-ip>:8000"
    echo ""
    
    if [ -z "$STT_SERVER_URL" ] || [ -z "$TTS_SERVER_URL" ]; then
        echo "⚠️  Server URLs not set. Using defaults:"
        echo "   STT_SERVER_URL=${STT_SERVER_URL:-http://localhost:8000}"
        echo "   TTS_SERVER_URL=${TTS_SERVER_URL:-http://localhost:8000}"
        echo ""
    fi
    
    fish client --port 8001
    
else
    echo "Usage: $0 [server|client]"
    echo ""
    echo "Examples:"
    echo "  $0 server                    # Start server mode"
    echo "  $0 client                    # Start client mode"
    echo "  CLIENT_SERVER_URL=http://192.168.1.50:8001 $0 server"
    echo "  STT_SERVER_URL=http://192.168.1.100:8000 TTS_SERVER_URL=http://192.168.1.100:8000 $0 client"
    exit 1
fi

