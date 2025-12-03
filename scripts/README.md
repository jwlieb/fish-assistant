# Helper Scripts

Quick setup scripts for Fish Assistant testing.

## Scripts

### `setup-env.sh` - Create .env file
Interactive script to create `.env` file with proper configuration.

```bash
# On laptop (server)
./scripts/setup-env.sh server

# On PocketBeagle (client)
./scripts/setup-env.sh client
```

### `find-ips.sh` - Find IP addresses
Quick helper to find IP addresses needed for configuration.

```bash
./scripts/find-ips.sh
```

### `quick-test.sh` - Quick start
Convenience script to start server or client mode.

```bash
# Start server
./scripts/quick-test.sh server

# Start client
./scripts/quick-test.sh client
```

## Usage Examples

**Complete setup in 30 seconds:**

```bash
# Terminal 1 (Laptop):
./scripts/setup-env.sh server
pip install -e ".[server]"
fish server --port 8000

# Terminal 2 (PocketBeagle):
./scripts/setup-env.sh client
pip install -e ".[client]"
fish client --port 8001
```

**One-liner with environment variables:**

```bash
# Server (laptop):
CLIENT_SERVER_URL=http://192.168.1.50:8001 fish server --port 8000

# Client (PocketBeagle):
STT_SERVER_URL=http://192.168.1.100:8000 TTS_SERVER_URL=http://192.168.1.100:8000 fish client --port 8001
```

