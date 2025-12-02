# Shell Module Integration Guide

This guide provides step-by-step instructions for integrating the Hiveden Shell module into your frontend application.

## Table of Contents

1. [Quick Start](#quick-start)
2. [API Overview](#api-overview)
3. [Frontend Integration](#frontend-integration)
4. [Use Case Examples](#use-case-examples)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Install Dependencies

First, ensure the shell module dependencies are installed:

```bash
cd /home/ermalguni/MEGA/devops/hiveden
pip install -e .
```

### 2. Start the API Server

```bash
uvicorn hiveden.api.server:app --reload --host 0.0.0.0 --port 8000
```

### 3. Test the API

```bash
# List active sessions
curl http://localhost:8000/shell/sessions

# Create a local shell session
curl -X POST http://localhost:8000/shell/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "shell_type": "local",
    "target": "localhost",
    "working_dir": "/tmp"
  }'
```

## API Overview

### Base URL

```
http://localhost:8000/shell
```

### Authentication

Currently, the shell API does not implement authentication. **You should add authentication before deploying to production.**

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sessions` | Create a new shell session |
| GET | `/sessions` | List all sessions |
| GET | `/sessions/{id}` | Get session details |
| DELETE | `/sessions/{id}` | Close a session |
| POST | `/docker/{id}/shell` | Create Docker shell session |
| POST | `/lxc/{name}/shell` | Create LXC shell session |
| POST | `/packages/check` | Check if package is installed |
| WS | `/ws/{session_id}` | WebSocket for command execution |
| WS | `/ws/packages/install` | WebSocket for package installation |

## Frontend Integration

### React/Next.js Integration

#### 1. Create a Shell Service

```typescript
// services/shellService.ts

export interface ShellSession {
  session_id: string;
  shell_type: 'docker' | 'ssh' | 'local';
  target: string;
  user: string;
  working_dir: string;
  active: boolean;
  created_at: string;
}

export interface ShellOutput {
  session_id: string;
  output: string;
  error: boolean;
  exit_code: number | null;
  timestamp: string;
}

export class ShellService {
  private baseUrl: string;
  private wsUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
    this.wsUrl = baseUrl.replace('http://', 'ws://').replace('https://', 'wss://');
  }

  async createDockerSession(containerId: string, options?: {
    user?: string;
    working_dir?: string;
  }): Promise<ShellSession> {
    const response = await fetch(`${this.baseUrl}/shell/docker/${containerId}/shell`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {})
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create session: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  async listSessions(): Promise<ShellSession[]> {
    const response = await fetch(`${this.baseUrl}/shell/sessions`);
    
    if (!response.ok) {
      throw new Error(`Failed to list sessions: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  async closeSession(sessionId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/shell/sessions/${sessionId}`, {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      throw new Error(`Failed to close session: ${response.statusText}`);
    }
  }

  connectToSession(sessionId: string): WebSocket {
    return new WebSocket(`${this.wsUrl}/shell/ws/${sessionId}`);
  }

  connectToPackageInstall(packageName: string, packageManager: string = 'auto'): WebSocket {
    return new WebSocket(
      `${this.wsUrl}/shell/ws/packages/install?package_name=${packageName}&package_manager=${packageManager}`
    );
  }
}
```

#### 2. Create a Terminal Component

```typescript
// components/Terminal.tsx

import React, { useState, useEffect, useRef } from 'react';
import { ShellService, ShellOutput } from '../services/shellService';

interface TerminalProps {
  sessionId: string;
  onClose?: () => void;
}

export const Terminal: React.FC<TerminalProps> = ({ sessionId, onClose }) => {
  const [output, setOutput] = useState<ShellOutput[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  const shellService = new ShellService();

  useEffect(() => {
    // Connect to WebSocket
    const ws = shellService.connectToSession(sessionId);

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'output') {
        setOutput(prev => [...prev, message.data]);
      } else if (message.type === 'error') {
        console.error('Shell error:', message.message);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [sessionId]);

  useEffect(() => {
    // Auto-scroll to bottom
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const sendCommand = () => {
    if (wsRef.current && input && isConnected) {
      wsRef.current.send(JSON.stringify({
        type: 'command',
        command: input
      }));
      setInput('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      sendCommand();
    }
  };

  return (
    <div className="terminal-container">
      <div className="terminal-header">
        <span className={`status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '● Connected' : '○ Disconnected'}
        </span>
        {onClose && (
          <button onClick={onClose} className="close-btn">×</button>
        )}
      </div>

      <div className="terminal-output" ref={outputRef}>
        {output.map((line, i) => (
          <div
            key={i}
            className={`output-line ${line.error ? 'error' : ''}`}
          >
            {line.output}
          </div>
        ))}
      </div>

      <div className="terminal-input">
        <span className="prompt">$</span>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Enter command..."
          disabled={!isConnected}
        />
        <button onClick={sendCommand} disabled={!isConnected}>
          Send
        </button>
      </div>

      <style jsx>{`
        .terminal-container {
          display: flex;
          flex-direction: column;
          height: 500px;
          background: #1e1e1e;
          border-radius: 8px;
          overflow: hidden;
          font-family: 'Courier New', monospace;
        }

        .terminal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          background: #2d2d2d;
          border-bottom: 1px solid #444;
        }

        .status {
          font-size: 12px;
          color: #999;
        }

        .status.connected {
          color: #4caf50;
        }

        .close-btn {
          background: none;
          border: none;
          color: #999;
          font-size: 24px;
          cursor: pointer;
          padding: 0;
          width: 24px;
          height: 24px;
        }

        .close-btn:hover {
          color: #fff;
        }

        .terminal-output {
          flex: 1;
          overflow-y: auto;
          padding: 12px;
          color: #f0f0f0;
          font-size: 14px;
          line-height: 1.5;
        }

        .output-line {
          white-space: pre-wrap;
          word-break: break-all;
        }

        .output-line.error {
          color: #f44336;
        }

        .terminal-input {
          display: flex;
          align-items: center;
          padding: 8px 12px;
          background: #2d2d2d;
          border-top: 1px solid #444;
        }

        .prompt {
          color: #4caf50;
          margin-right: 8px;
        }

        .terminal-input input {
          flex: 1;
          background: transparent;
          border: none;
          color: #f0f0f0;
          font-family: inherit;
          font-size: 14px;
          outline: none;
        }

        .terminal-input button {
          margin-left: 8px;
          padding: 4px 12px;
          background: #4caf50;
          border: none;
          border-radius: 4px;
          color: white;
          cursor: pointer;
          font-size: 12px;
        }

        .terminal-input button:disabled {
          background: #666;
          cursor: not-allowed;
        }

        .terminal-input button:hover:not(:disabled) {
          background: #45a049;
        }
      `}</style>
    </div>
  );
};
```

#### 3. Use the Terminal Component

```typescript
// pages/containers/[id].tsx

import { useState, useEffect } from 'react';
import { Terminal } from '../../components/Terminal';
import { ShellService } from '../../services/shellService';

export default function ContainerDetailPage({ containerId }: { containerId: string }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showTerminal, setShowTerminal] = useState(false);
  const shellService = new ShellService();

  const openShell = async () => {
    try {
      const session = await shellService.createDockerSession(containerId, {
        user: 'root',
        working_dir: '/'
      });
      setSessionId(session.session_id);
      setShowTerminal(true);
    } catch (error) {
      console.error('Failed to create shell session:', error);
    }
  };

  const closeShell = async () => {
    if (sessionId) {
      await shellService.closeSession(sessionId);
      setSessionId(null);
      setShowTerminal(false);
    }
  };

  return (
    <div>
      <h1>Container: {containerId}</h1>
      
      <button onClick={openShell}>Open Shell</button>

      {showTerminal && sessionId && (
        <div style={{ marginTop: '20px' }}>
          <Terminal sessionId={sessionId} onClose={closeShell} />
        </div>
      )}
    </div>
  );
}
```

## Use Case Examples

### Use Case 1: Docker Container Shell

**Scenario**: User wants to execute commands in a running Docker container.

**Implementation**:
1. Create a Docker shell session via POST `/shell/docker/{container_id}/shell`
2. Connect to WebSocket at `/shell/ws/{session_id}`
3. Send commands and display real-time output
4. Close session when done

### Use Case 2: Package Installation

**Scenario**: System needs to install a missing package and show progress to the user.

**Implementation**:
```typescript
async function installPackage(packageName: string) {
  const shellService = new ShellService();
  const ws = shellService.connectToPackageInstall(packageName);

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'output') {
      // Display installation progress
      console.log(message.data.output);
    } else if (message.type === 'install_completed') {
      // Package installed successfully
      console.log('Installation complete!');
    }
  };
}
```

### Use Case 3: LXC Container SSH

**Scenario**: User wants to connect to an LXC container via SSH.

**Implementation**:
1. Create SSH session via POST `/shell/lxc/{container_name}/shell`
2. Provide SSH key path in the request
3. Connect to WebSocket and execute commands

## Best Practices

### 1. Session Management

- Always close sessions when done to free resources
- Implement session timeouts on the frontend
- Handle WebSocket disconnections gracefully

### 2. Error Handling

```typescript
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Show user-friendly error message
  showNotification('Connection error. Please try again.');
};

ws.onclose = (event) => {
  if (!event.wasClean) {
    // Unexpected disconnection
    showNotification('Connection lost. Reconnecting...');
    // Implement reconnection logic
  }
};
```

### 3. Security

- Implement authentication before production use
- Validate user permissions for shell access
- Log all commands for audit purposes
- Consider implementing command whitelisting

### 4. Performance

- Limit output buffer size to prevent memory issues
- Implement output throttling for high-frequency output
- Use virtual scrolling for large output displays

## Troubleshooting

### WebSocket Connection Failed

**Problem**: Cannot connect to WebSocket endpoint.

**Solutions**:
- Verify API server is running
- Check CORS settings in `server.py`
- Ensure WebSocket URL uses correct protocol (ws:// or wss://)

### Session Not Found

**Problem**: Session ID returns 404.

**Solutions**:
- Verify session was created successfully
- Check if session was closed
- Ensure session ID is correct

### Command Output Not Appearing

**Problem**: Commands execute but no output is shown.

**Solutions**:
- Check WebSocket message handler
- Verify output is being added to state
- Check for JavaScript errors in console

### Docker Container Not Running

**Problem**: Cannot create shell session for container.

**Solutions**:
- Verify container is running: `docker ps`
- Check container ID is correct
- Ensure Docker daemon is accessible

## Next Steps

1. Add authentication to shell endpoints
2. Implement session persistence
3. Add command history
4. Integrate with xterm.js for better terminal emulation
5. Add file upload/download capabilities

## Support

For issues or questions, please refer to:
- [Shell Module README](./README.md)
- [API Documentation](http://localhost:8000/docs)
- [GitHub Issues](https://github.com/hiveden/hiveden/issues)
