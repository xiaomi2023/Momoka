## Configuration

Parameters can be configured through the configuration file (config.json) to customize Momoka's functionality and behavior.

### Configuration Parameters

| Parameter  | Description                                                |
|------------|------------------------------------------------------------|
| `api_key`  | LLM API key for authentication                             |
| `base_url` | API base URL endpoint                                      |
| `model`    | Model name to use (e.g., gpt-4o)                           |
| `work_dir` | Default working directory path                             |
| `encoding` | File encoding (default: utf-8)                             |
| `fold`     | Fold history file content in output (true/false)           |
| `mute_log` | List of roles to mute in logs (e.g., ["SHELL", "BROWSER"]) |
| `language` | Response language (null for auto-detect)                   |
| `prompt`   | Additional system prompt text                              |
