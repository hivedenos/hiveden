# Hiveden Shell Module

The Shell module provides interactive shell capabilities for Hiveden, enabling real-time command execution and output streaming for Docker containers, SSH connections, and local system commands.

## Features

- 🐳 **Docker Container Exec**: Execute commands inside Docker containers
- 🔐 **SSH Connections**: Connect to LXC containers or remote hosts via SSH
- 💻 **Local Execution**: Run commands on the local system
- 📦 **Package Management**: Check and install system packages with real-time output
- 🔄 **Real-time Streaming**: WebSocket-based real-time command output
- 🎯 **Session Management**: Create, manage, and close shell sessions

## Architecture

```
hiveden/shell/
├── __init__.py          # Module exports
├── models.py            # Pydantic models for shell sessions
├── manager.py           # Core ShellManager class
└── websocket.py         # WebSocket handler for real-time communication

hiveden/api/routers/
└── shell.py             # FastAPI router with REST and WebSocket endpoints
```

## Use Cases

### 1. Docker Container Shell

Execute commands in a Docker container with real-time output:

```python
# Create a shell session for a Docker container
POST /shell/docker/{container_id}/shell
{
    "user": "root",
    "working_dir": "/app"
}

# Connect to WebSocket for interactive shell
WS /shell/ws/{session_id}

# Send commands
{
    "type": "command",
    "command": "ls -la"
}
```

### 2. Package Installation with Real-time Output

Check if a package is installed and install it if needed:

```python
# Check if package is installed
POST /shell/packages/check
{
    "package_name": "nginx",
    "package_manager": "auto"
}

# Install package with real-time output via WebSocket
WS /shell/ws/packages/install?package_name=nginx&package_manager=auto
```

### 3. SSH Connection to LXC Container

Create an SSH session to an LXC container:

```python
# Create SSH session
POST /shell/lxc/{container_name}/shell
{
    "user": "root",
    "ssh_port": 22,
    "ssh_key_path": "/root/.ssh/id_rsa"
}

# Connect to WebSocket
WS /shell/ws/{session_id}
```

## API Endpoints

### REST Endpoints

#### Create Shell Session
```http
POST /shell/sessions
Content-Type: application/json

{
    "shell_type": "docker|ssh|local",
    "target": "container_id|hostname|localhost",
    "user": "root",
    "working_dir": "/",
    "environment": {"VAR": "value"}
}
```

#### List Sessions
```http
GET /shell/sessions?active_only=true
```

#### Get Session
```http
GET /shell/sessions/{session_id}
```

#### Close Session
```http
DELETE /shell/sessions/{session_id}
```

#### Check Package
```http
POST /shell/packages/check
Content-Type: application/json

{
    "package_name": "nginx",
    "package_manager": "auto"
}
```

### WebSocket Endpoints

#### Interactive Shell Session
```
WS /shell/ws/{session_id}
```

**Client → Server Messages:**
```json
{
    "type": "command",
    "command": "ls -la"
}
```

```json
{
    "type": "ping"
}
```

```json
{
    "type": "close"
}
```

**Server → Client Messages:**
```json
{
    "type": "session_info",
    "data": {
        "session_id": "...",
        "shell_type": "docker",
        "target": "container_id",
        ...
    }
}
```

```json
{
    "type": "output",
    "data": {
        "session_id": "...",
        "output": "total 48\ndrwxr-xr-x...",
        "error": false,
        "exit_code": null,
        "timestamp": "2025-12-02T10:30:00Z"
    }
}
```

```json
{
    "type": "command_completed",
    "command": "ls -la"
}
```

#### Package Installation
```
WS /shell/ws/packages/install?package_name=nginx&package_manager=auto
```

**Server → Client Messages:**
```json
{
    "type": "install_started",
    "package": "nginx",
    "package_manager": "apt"
}
```

```json
{
    "type": "output",
    "data": {
        "session_id": "system",
        "output": "Reading package lists...",
        "error": false,
        "exit_code": null,
        "timestamp": "2025-12-02T10:30:00Z"
    }
}
```

```json
{
    "type": "install_completed",
    "package": "nginx"
}
```

## Usage Examples

### Python Client Example

```python
import asyncio
import websockets
import json

async def docker_shell_example():
    # Create session
    import requests
    response = requests.post(
        "http://localhost:8000/shell/docker/my-container/shell",
        json={"user": "root", "working_dir": "/app"}
    )
    session_id = response.json()["data"]["session_id"]
    
    # Connect to WebSocket
    async with websockets.connect(f"ws://localhost:8000/shell/ws/{session_id}") as ws:
        # Receive session info
        session_info = await ws.recv()
        print(json.loads(session_info))
        
        # Send command
        await ws.send(json.dumps({
            "type": "command",
            "command": "ls -la"
        }))
        
        # Receive output
        while True:
            message = await ws.recv()
            data = json.loads(message)
            
            if data["type"] == "output":
                print(data["data"]["output"], end="")
                
                # Check if command completed
                if data["data"].get("exit_code") is not None:
                    print(f"\nExit code: {data['data']['exit_code']}")
                    break
            
            elif data["type"] == "command_completed":
                break

asyncio.run(docker_shell_example())
```

### JavaScript/TypeScript Client Example

```typescript
// Create session
const response = await fetch('http://localhost:8000/shell/docker/my-container/shell', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user: 'root', working_dir: '/app' })
});
const { data } = await response.json();
const sessionId = data.session_id;

// Connect to WebSocket
const ws = new WebSocket(`ws://localhost:8000/shell/ws/${sessionId}`);

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'output') {
        console.log(message.data.output);
        
        if (message.data.exit_code !== null) {
            console.log(`Exit code: ${message.data.exit_code}`);
        }
    }
};

ws.onopen = () => {
    // Send command
    ws.send(JSON.stringify({
        type: 'command',
        command: 'ls -la'
    }));
};
```

## Frontend Integration

### React Component Example

```tsx
import React, { useState, useEffect, useRef } from 'react';

interface ShellTerminalProps {
    containerId: string;
}

export const ShellTerminal: React.FC<ShellTerminalProps> = ({ containerId }) => {
    const [output, setOutput] = useState<string[]>([]);
    const [input, setInput] = useState('');
    const wsRef = useRef<WebSocket | null>(null);
    const [sessionId, setSessionId] = useState<string | null>(null);

    useEffect(() => {
        // Create session
        fetch(`/shell/docker/${containerId}/shell`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user: 'root', working_dir: '/' })
        })
        .then(res => res.json())
        .then(data => {
            const sid = data.data.session_id;
            setSessionId(sid);
            
            // Connect WebSocket
            const ws = new WebSocket(`ws://localhost:8000/shell/ws/${sid}`);
            
            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                
                if (message.type === 'output') {
                    setOutput(prev => [...prev, message.data.output]);
                }
            };
            
            wsRef.current = ws;
        });

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [containerId]);

    const sendCommand = () => {
        if (wsRef.current && input) {
            wsRef.current.send(JSON.stringify({
                type: 'command',
                command: input
            }));
            setInput('');
        }
    };

    return (
        <div className="terminal">
            <div className="output">
                {output.map((line, i) => (
                    <div key={i}>{line}</div>
                ))}
            </div>
            <div className="input">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendCommand()}
                    placeholder="Enter command..."
                />
                <button onClick={sendCommand}>Send</button>
            </div>
        </div>
    );
};
```

## Security Considerations

1. **Authentication**: The shell module should be protected with proper authentication and authorization
2. **SSH Keys**: Store SSH private keys securely, never in session metadata
3. **Command Validation**: Consider implementing command whitelisting for production use
4. **Session Timeouts**: Implement session timeouts to prevent resource leaks
5. **Rate Limiting**: Add rate limiting to prevent abuse
6. **Audit Logging**: Log all commands executed for security auditing

## Error Handling

The module provides comprehensive error handling:

- **Invalid Session**: Returns 404 if session not found
- **Container Not Running**: Returns 400 if Docker container is not running
- **SSH Connection Failed**: Returns 400 with connection error details
- **Command Execution Failed**: Streams error output with `error: true` flag

## Performance Considerations

- Sessions are kept in memory; consider implementing session persistence for production
- WebSocket connections are maintained per session; monitor connection limits
- Large command outputs are streamed to prevent memory issues
- Consider implementing output buffering for very high-frequency output

## Future Enhancements

- [ ] Session persistence (database storage)
- [ ] Command history per session
- [ ] Tab completion support
- [ ] File upload/download via shell session
- [ ] Multi-user session support with permissions
- [ ] Session recording and playback
- [ ] Integration with terminal emulators (xterm.js)
