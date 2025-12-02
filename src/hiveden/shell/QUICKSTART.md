# Shell Module - Quick Reference

## 📁 File Structure

```
hiveden/
├── src/hiveden/
│   ├── shell/                      # Shell module (NEW)
│   │   ├── __init__.py            # Module exports
│   │   ├── models.py              # Pydantic models
│   │   ├── manager.py             # Core ShellManager
│   │   ├── websocket.py           # WebSocket handler
│   │   ├── example.py             # Demo script
│   │   ├── README.md              # Module documentation
│   │   ├── INTEGRATION.md         # Frontend integration guide
│   │   └── SUMMARY.md             # Implementation summary
│   │
│   └── api/
│       ├── routers/
│       │   └── shell.py           # Shell API router (NEW)
│       └── server.py              # Updated with shell router
│
├── tests/
│   └── test_shell.py              # Shell module tests (NEW)
│
└── pyproject.toml                 # Updated dependencies

```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -e .
```

### 2. Start Server
```bash
uvicorn hiveden.api.server:app --reload --port 8000
```

### 3. Test API
```bash
# Create a local shell session
curl -X POST http://localhost:8000/shell/sessions \
  -H "Content-Type: application/json" \
  -d '{"shell_type": "local", "target": "localhost"}'

# List sessions
curl http://localhost:8000/shell/sessions
```

## 📡 API Endpoints

### REST
- `POST /shell/sessions` - Create session
- `GET /shell/sessions` - List sessions
- `GET /shell/sessions/{id}` - Get session
- `DELETE /shell/sessions/{id}` - Close session
- `POST /shell/docker/{id}/shell` - Docker shell
- `POST /shell/lxc/{name}/shell` - LXC shell
- `POST /shell/packages/check` - Check package

### WebSocket
- `WS /shell/ws/{session_id}` - Interactive shell
- `WS /shell/ws/packages/install` - Package install

## 💡 Usage Examples

### Docker Shell
```python
# Create session
POST /shell/docker/my-container/shell
{"user": "root", "working_dir": "/app"}

# Connect WebSocket
WS /shell/ws/{session_id}

# Send command
{"type": "command", "command": "ls -la"}
```

### Package Installation
```python
# Check package
POST /shell/packages/check
{"package_name": "nginx"}

# Install with progress
WS /shell/ws/packages/install?package_name=nginx
```

### SSH to LXC
```python
# Create SSH session
POST /shell/lxc/my-lxc/shell
{"ssh_key_path": "/root/.ssh/id_rsa"}

# Execute commands via WebSocket
WS /shell/ws/{session_id}
```

## 🎯 Use Cases Covered

✅ **Docker Container Shell**
- Execute commands in containers
- Real-time output streaming

✅ **Package Management**
- Check package installation
- Install with real-time progress

✅ **LXC SSH Connection**
- SSH to LXC containers
- Key-based authentication

## 🔧 Run Examples

```bash
# List active sessions
python src/hiveden/shell/example.py list

# Docker shell demo
python src/hiveden/shell/example.py docker --container my-container

# Local shell demo
python src/hiveden/shell/example.py local

# Package installation
python src/hiveden/shell/example.py package --package nginx
```

## 🧪 Run Tests

```bash
pytest tests/test_shell.py -v
```

## 📚 Documentation

- **README.md** - Full module documentation
- **INTEGRATION.md** - Frontend integration guide
- **SUMMARY.md** - Implementation details

## 🔐 Security Notes

⚠️ Before production:
1. Add authentication
2. Implement authorization
3. Add audit logging
4. Implement rate limiting
5. Secure SSH key storage

## 🎨 Frontend Integration

See `INTEGRATION.md` for:
- React/TypeScript examples
- Terminal component
- Service layer
- Best practices

## 📊 Architecture

```
Frontend (React/Next.js)
    ↓ WebSocket/REST
FastAPI Router (/shell/*)
    ↓
ShellManager
    ↓
┌───────┬────────┬────────┐
Docker  │  SSH   │ Local  │
Exec    │ Client │ Shell  │
└───────┴────────┴────────┘
```

## 🔄 Message Flow

```
Client → {"type": "command", "command": "ls"}
Server → {"type": "output", "data": {...}}
Server → {"type": "output", "data": {...}}
Server → {"type": "command_completed"}
```

## 📦 Dependencies Added

- `paramiko` - SSH client
- `websockets` - WebSocket support

## ✨ Features

- Real-time command execution
- Streaming output
- Session management
- Package management
- Docker/SSH/Local support
- WebSocket communication
- Comprehensive error handling

---

**Status**: ✅ Fully Implemented and Ready for Integration
