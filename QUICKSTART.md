# Quick Start Guide

## Prerequisites Check

```bash
# Check Python version (needs 3.10+)
python --version

# Check if FFmpeg is installed (required for STT)
ffmpeg -version
```

## Server Setup (Laptop) - 2 Minutes

**Option 1: Use setup script (easiest):**
```bash
./scripts/setup-env.sh server
# Enter your PocketBeagle IP when prompted
pip install -e ".[server]"
fish server --port 8000
```

**Option 2: Manual setup:**
1. **Find IPs:**
   ```bash
   ./scripts/find-ips.sh
   ```

2. **Create .env file:**
   ```bash
   ./scripts/setup-env.sh server
   # Or manually create .env with:
   # CLIENT_SERVER_URL=http://<pocketbeagle-ip>:8001
   ```

3. **Install and start:**
   ```bash
   pip install -e ".[server]"
   fish server --port 8000
   ```

## Client Setup (PocketBeagle) - 2 Minutes

**Option 1: Use setup script (easiest):**
```bash
./scripts/setup-env.sh client
# Enter your laptop IP when prompted
pip install -e ".[client]"
fish client --port 8001
```

**Option 2: Manual setup:**
1. **Find laptop IP** (from server setup above)

2. **Create .env file:**
   ```bash
   ./scripts/setup-env.sh client
   # Or manually create .env with server URLs
   ```

3. **Install and start:**
   ```bash
   pip install -e ".[client]"
   fish client --port 8001
   ```

## Test It

1. **Start server** (laptop):
   ```bash
   fish server --port 8000 --client-url http://<pocketbeagle-ip>:8001
   ```

2. **Start client** (PocketBeagle):
   ```bash
   fish client --port 8001
   ```

3. **Speak into laptop microphone** - fish should respond!

## Quick Troubleshooting

**Can't connect?**
```bash
# Test connectivity
ping <target-ip>

# Test server health
curl http://<laptop-ip>:8000/health
curl http://<pocketbeagle-ip>:8001/health
```

**Server not starting?**
- Check port: `lsof -i :8000`
- Check FFmpeg: `ffmpeg -version`

**Client not starting?**
- Check server is running: `curl http://<laptop-ip>:8000/health`
- Check network: `ping <laptop-ip>`

**Audio not playing?**
- Test speaker: `speaker-test -t sine -f 1000` (Linux)
- Check audio devices: `fish audio:list`

## One-Liner Commands

**Server (with client URL):**
```bash
CLIENT_SERVER_URL=http://<pocketbeagle-ip>:8001 fish server --port 8000
```

**Client (with server URLs):**
```bash
STT_SERVER_URL=http://<laptop-ip>:8000 TTS_SERVER_URL=http://<laptop-ip>:8000 fish client --port 8001
```

