## Headless Mode (BETA)

Headless Mode provides the ability to interact with Momoka programmatically,
enabling integration with backend services, batch processing tasks, container deployments, and other scenarios.

## Quick Start

### 1. Stdio Mode (Standard Input/Output)

The simplest headless mode, communicating via stdin/stdout using JSON Lines:

```bash
python main.py --headless stdio
```

**Example (pipe mode):**

```bash
echo '{"type":"message","content":"Hello, please help me write a Python function"}' | python main.py --headless stdio
```

**Example (multi-turn conversation):**

```bash
cat <<EOF | python main.py --headless stdio
{"type":"message","content":"Hello"}
{"type":"message","content":"Please help me write a Fibonacci function"}
{"type":"command","command":"usage"}
{"type":"command","command":"end"}
EOF
```

### 2. File Mode (File Read/Write)

Asynchronous communication via file read/write:

```bash
python main.py --headless file --input input.txt --output output.txt
```

**Usage:**

```bash
# Terminal 1: Start Momoka
python main.py --headless file --input input.txt --output output.txt

# Terminal 2: Write input
echo '{"type":"message","content":"Hello"}' >> input.txt

# Terminal 2: View output
tail -f output.txt
```

## Communication Protocol

### Input Format (JSON Lines)

One JSON object per line, supporting the following types:

#### User Message

```json
{"type": "message", "content": "Hello, please help me write a function"}
```

#### Command

```json
{"type": "command", "command": "end"}
```

**Supported Commands:**

| Command  | Description                    |
|----------|--------------------------------|
| `end`    | End session                    |
| `usage`  | Display token usage statistics |
| `config` | Display current configuration  |

### Output Format (JSON Lines)

One JSON object per line, containing the following types:

| Type            | Description        | Example                                                                                           |
|-----------------|--------------------|---------------------------------------------------------------------------------------------------|
| `session_start` | Session started    | `{"type": "session_start", "mode": "headless"}`                                                   |
| `log`           | Log message        | `{"type": "log", "role": "BOT", "content": "Okay, let me help you..."}`                           |
| `error`         | Error message      | `{"type": "error", "content": "Error description"}`                                               |
| `task_finish`   | Task completed     | `{"type": "task_finish"}`                                                                         |
| `usage`         | Usage statistics   | `{"type": "usage", "input_tokens": 1234, "output_tokens": 5678, "rounds": 5, "time": "2min 30s"}` |
| `config`        | Configuration info | `{"type": "config", "config": {"model": "gpt-4o", "base_url": "https://...", "api_key": "***"}}`  |
| `session_end`   | Session ended      | `{"type": "session_end"}`                                                                         |

## Examples

### Python

```python
import subprocess
import json

# Start Momoka process
proc = subprocess.Popen(
    ['python', 'main.py', '--headless', 'stdio'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding='utf-8'
)

# Send messages
messages = [
    {"type": "message", "content": "Hello"},
    {"type": "message", "content": "Please help me write a Python function"},
    {"type": "command", "command": "usage"},
    {"type": "command", "command": "end"},
]

input_data = '\n'.join(json.dumps(msg) for msg in messages)
stdout, stderr = proc.communicate(input=input_data, timeout=60)

# Parse output
for line in stdout.strip().split('\n'):
    data = json.loads(line)
    if data['type'] == 'log':
        print(f"[{data['role']}] {data['content']}")
    elif data['type'] == 'usage':
        print(f"Usage: {data['input_tokens']} input / {data['output_tokens']} output")
```

### Node.js

```javascript
const { spawn } = require('child_process');

const momoka = spawn('python', ['main.py', '--headless', 'stdio']);

momoka.stdout.on('data', (data) => {
  const lines = data.toString().split('\n').filter(l => l.trim());
  for (const line of lines) {
    const msg = JSON.parse(line);
    if (msg.type === 'log') {
      console.log(`[${msg.role}] ${msg.content}`);
    }
  }
});

// Send messages
const messages = [
  { type: 'message', content: 'Hello' },
  { type: 'command', command: 'end' }
];

messages.forEach(msg => {
  momoka.stdin.write(JSON.stringify(msg) + '\n');
});

momoka.stdin.end();
```

### Bash

```bash
#!/bin/bash

# Multi-turn conversation script
INPUT='{"type":"message","content":"Hello"}
{"type":"message","content":"Please explain what recursion is"}
{"type":"command","command":"usage"}
{"type":"command","command":"end"}'

echo "$INPUT" | python main.py --headless stdio | while read -r line; do
  type=$(echo "$line" | jq -r '.type')
  
  case "$type" in
    log)
      role=$(echo "$line" | jq -r '.role')
      content=$(echo "$line" | jq -r '.content')
      echo "[$role] $content"
      ;;
    usage)
      echo "Usage Statistics:"
      echo "$line" | jq -r '"  Input: \(.input_tokens) tokens"'
      echo "$line" | jq -r '"  Output: \(.output_tokens) tokens"'
      echo "$line" | jq -r '"  Rounds: \(.rounds)"'
      echo "$line" | jq -r '"  Time: \(.time)"'
      ;;
    error)
      echo "Error: $(echo "$line" | jq -r '.content')" >&2
      ;;
  esac
done
```

## Advanced Usage

### Integration with Logging System

Headless mode still writes to log files (`logs/log.txt` and `logs/chat_history_log.txt`), facilitating subsequent auditing and debugging.
