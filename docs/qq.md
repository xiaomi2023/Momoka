# QQ (BETA)

Momoka can run as a QQ Bot, allowing you to communicate with Momoka through QQ.

## Create a QQ Bot Application

### Step 1: Register on QQ Open Platform

1. Visit the [QQ Open Platform](https://q.qq.com/)
2Log in to the Open Platform Official Website

### Step 2: Create an Bot and Obtain Credentials

Create a Bot, then find and copy **App ID** and **App Secret**

## Configuration

Add QQ configuration to `config.json`:

```json
{
  "interface": "qq",
  "qq": {
    "app_id": "your_app_id",
    "app_secret": "your_app_secret"
  }
}
```

### Configuration Parameters

| Parameter           | Type       | Description                                           |
|---------------------|------------|-------------------------------------------------------|
| `interface`         | `string`   | Set to `"qq"` to make Momoka run as QQ Bot by default |
| `qq.app_id`         | `string`   | Your QQ Open Platform application App ID              |
| `qq.app_secret`     | `string`   | Your QQ Open Platform application App Secret          |
| `qq.sandbox`        | `bool`     | Whether to use sandbox environment, default `false` (optional) |

## Running the Bot

### Method 1: Configuration File

Set `"interface": "qq"` in `config.json` and run:

```bash
python main.py
```

### Method 2: Command Line Arguments

Run:

```bash
python main.py --interface qq
```

## Usage

### Starting a Conversation

Please add the bot to a QQ group, or find the bot in QQ and send a message to start a conversation.
If you see the following message, the connection is successful:

```
Successfully connected to QQ
Welcome back! This is Momoka~
Developed by Mikoris | For more help, type /help
```

### Group Chat Usage

1. Add the bot to a QQ group
2. **@the bot** in the group and send a message

### Direct Message Usage

1. Find the bot in QQ
2. Send a message
