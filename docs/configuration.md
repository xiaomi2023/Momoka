# Configuration

Parameters can be configured through the configuration file (`config.json`) to customize Momoka's functionality and behavior.

You can also specify a custom config file at startup:

```bash
python main.py --config my_config.json
```

---

## Static Configuration (`config.json`)

### Core Parameters

| Parameter   | Type           | Required | Description                                                                                       |
|-------------|----------------|----------|---------------------------------------------------------------------------------------------------|
| `api_key`   | `string`       | Yes      | LLM API key for authentication                                                                    |
| `base_url`  | `string`       | Yes      | API base URL endpoint (e.g., `https://api.openai.com/v1`)                                         |
| `model`     | `string`       | Yes      | Model name to use (e.g., `gpt-4o`, `claude-3-opus`, etc.)                                         |
| `work_dir`  | `string`       | No       | Default working directory path                                                                    |
| `encoding`  | `string`       | No       | File encoding (default: `"utf-8"`)                                                                |
| `mute_log`  | `list[string]` | No       | List of roles to mute in logs (e.g., `["SHELL", "BROWSER"]`)                                      |
| `interface` | `string`       | No       | Interface type: `"cli"`, `"lark"`, `"discord"`, `"qq"`, `"telegram"`, `"slack"`. Default: `"cli"` |

### Example

```json
{
  "api_key": "sk-XXX",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o",
  "work_dir": "C:\\Users\\YourName\\Projects",
  "encoding": "utf-8",
  "mute_log": ["SHELL", "BROWSER"],
  "interface": "cli"
}
```

---

### Bot Platform Configurations

Depending on the `interface` type, different platform-specific configurations are needed.

#### Lark / Feishu Bot

| Parameter         | Type     | Required | Description                          |
|-------------------|----------|----------|--------------------------------------|
| `interface`       | `string` | Yes      | Set to `"lark"`                      |
| `lark.app_id`     | `string` | Yes      | Lark application App ID              |
| `lark.app_secret` | `string` | Yes      | Lark application App Secret          |

```json
{
  "interface": "lark",
  "lark": {
    "app_id": "cli_xxxxxxxxxx",
    "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

#### Discord Bot

| Parameter               | Type             | Required | Description                                                                  |
|-------------------------|------------------|----------|------------------------------------------------------------------------------|
| `interface`             | `string`         | Yes      | Set to `"discord"`                                                           |
| `discord.token`         | `string`         | Yes      | Discord Bot Token obtained from the Developer Portal                         |
| `discord.allowed_users` | `list[int]`      | No       | List of allowed user IDs. An empty list `[]` means all users can use the bot |
| `discord.proxy`         | `string\|null`   | No       | Optional proxy address (e.g., `"http://127.0.0.1:7890"`)                     |

```json
{
  "interface": "discord",
  "discord": {
    "token": "YOUR_BOT_TOKEN_HERE",
    "allowed_users": [123456789012345678],
    "proxy": null
  }
}
```

#### QQ Bot

| Parameter         | Type       | Required | Description                                            |
|-------------------|------------|----------|--------------------------------------------------------|
| `interface`       | `string`   | Yes      | Set to `"qq"`                                          |
| `qq.app_id`       | `string`   | Yes      | QQ Open Platform application App ID                    |
| `qq.app_secret`   | `string`   | Yes      | QQ Open Platform application App Secret                |
| `qq.sandbox`      | `bool`     | No       | Whether to use sandbox environment, default `false`    |

```json
{
  "interface": "qq",
  "qq": {
    "app_id": "your_app_id",
    "app_secret": "your_app_secret",
    "sandbox": false
  }
}
```

---

### MCP Servers Configuration

MCP (Model Context Protocol) server configurations are placed under the `mcp_servers` key. Each server is identified by a unique name.

For detailed MCP configuration instructions, see [MCP Server](mcp_server.md).

```json
{
  "mcp_servers": {
    "github": {
      "name": "github",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your_token"
      },
      "description": "GitHub MCP Server",
      "enabled": true,
      "prefix": "github"
    }
  }
}
```

| Parameter     | Type             | Required       | Description                                                         |
|---------------|------------------|----------------|---------------------------------------------------------------------|
| `name`        | `string`         | Yes            | Server identifier name                                              |
| `transport`   | `string`         | Yes            | Transport protocol: `stdio`, `sse`, or `http`                       |
| `command`     | `string`         | Yes (stdio)    | Command to start the server process (e.g., `npx`, `python`, `node`) |
| `args`        | `list[string]`   | Yes (stdio)    | Command-line arguments for starting the server                      |
| `url`         | `string`         | Yes (sse/http) | Server URL (must start with `http://` or `https://`)                |
| `env`         | `dict[str,str]`  | No             | Environment variables to pass to the server process                 |
| `description` | `string`         | No             | Server description for documentation purposes                       |
| `enabled`     | `bool`           | No             | Whether to enable this server (default: `true`)                     |
| `prefix`      | `string`         | No             | Tool name prefix to avoid naming conflicts (default: server name)   |

> **Note**: The `mcp_servers` field is optional and can be omitted entirely if MCP is not used.
