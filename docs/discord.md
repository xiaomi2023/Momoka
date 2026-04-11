# Discord (BETA)

Momoka can run as a Discord Bot, allowing you to communicate with Momoka through Discord.

## Create a Discord Bot

### Step 1: Create a Discord Application

1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Enter a name (e.g., "Momoka Bot") and click **"Create"**

### Step 2: Create a Bot User

1. In the application, navigate to **"Bot"** in the left sidebar
2. Click **"Add Bot"**
3. Click **"Yes, do it!"** to confirm

### Step 3: Obtain Bot Token

1. In the Bot section, find the **"Token"** section
2. Click **"Reset Token"** (or "View Token", if available)
3. Click **"Copy"** to copy your bot token

### Step 4: Enable Privileged Gateway Intents

1. Scroll down to **"Privileged Gateway Intents"**
2. Enable the following options:
   - **Message Content Intent** (required for reading messages)
   - **Server Members Intent** (optional, for member-related features)

### Step 5: Invite the Bot to a Server

1. Go to **"OAuth2"** → **"URL Generator"**
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select bot permissions:
   - **Send Messages**
   - **Read Message History**
   - **Send Messages in Threads** (if using threads)
4. Copy the generated URL and open it in your browser
5. Select a server and authorize the bot

## Configuration

Add Discord configuration to `config.json`:

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

### Configuration Parameters

| Parameter               | Type             | Description                                                                  |
|-------------------------|------------------|------------------------------------------------------------------------------|
| `interface`             | `string`         | Set to `"discord"` to make Momoka run in Discord by default                  |
| `discord.token`         | `string`         | Required. Discord Bot Token obtained from the Developer Portal               |
| `discord.allowed_users` | `list[int]`      | List of allowed user IDs. An empty list `[]` means all users can use the bot |
| `discord.proxy`         | `string \| null` | Optional. Proxy address (e.g., `"http://127.0.0.1:7890"`).                   |

### Obtain Your User ID

1. In Discord, go to **User Settings** → **Advanced**
2. Enable **Developer Mode**
3. Right-click your username and select **"Copy User ID"**

## Running the Bot

### Method 1: Configuration File

Set `"interface": "discord"` in `config.json` and run:

```bash
python main.py
```

### Method 2: Command Line Arguments

Run:

```bash
python main.py --interface discord
```

## Usage

### Starting a Conversation

Send a message to a channel or private chat that includes Momoka to start a conversation.
If you see the following message, the connection is successful:

```
Successfully connected to Discord
Welcome back! This is Momoka~
Developed by Mikoris | For more help, type /help
```
