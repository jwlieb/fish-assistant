#!/bin/bash
# Quick script to find IP addresses for setup

echo "🔍 Finding IP addresses for Fish Assistant setup"
echo ""

echo "📱 Laptop/Server IP (use this for CLIENT_SERVER_URL on PocketBeagle):"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "   " $2}' | head -1
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    hostname -I | awk '{print "   " $1}'
else
    echo "   (Run: ifconfig | grep 'inet ' | grep -v 127.0.0.1)"
fi

echo ""
echo "📡 PocketBeagle IP (use this for CLIENT_SERVER_URL on laptop):"
echo "   (Run on PocketBeagle: hostname -I)"
echo "   Or SSH and check: ssh pocketbeagle 'hostname -I'"
echo ""

echo "💡 Quick commands:"
echo ""
echo "   # On laptop (server):"
echo "   ./scripts/setup-env.sh server"
echo "   fish server --port 8000"
echo ""
echo "   # On PocketBeagle (client):"
echo "   ./scripts/setup-env.sh client"
echo "   fish client --port 8001"

