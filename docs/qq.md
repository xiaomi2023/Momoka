# QQ (BETA)

Momoka can run as a QQ Bot, allowing you to communicate with Momoka through QQ.

## Create a QQ Bot Application

### Step 1: Register on QQ Open Platform

1. Visit the [QQ Open Platform](https://q.qq.com/)
2. Register a developer account (enterprise or individual)
3. Log in to the developer management console

### Step 2: Create an Application and Obtain Credentials

1. In the management console, click **"Create Application"**
2. Enter the application name and description
3. Click **"Create"**
4. In the application management page, find and copy the following information:
   - **App ID**
   - **App Secret**

### Step 3: Configure Bot Capabilities

1. Navigate to the "Bot Configuration" page in the application management console
2. Enable bot capabilities:
   - Enable **"Group Chat"** capability
   - Enable **"Direct Message"** capability
3. Configure message receiving method: Select **WebSocket** mode

### Step 4: Configure Intent Subscriptions

1. Navigate to the "Event Subscription" or "Intent Configuration" page
2. Ensure the following events are subscribed:
   - `GROUP_AT_MESSAGE_CREATE` - Group @messages
   - `C2C_MESSAGE_CREATE` - Direct messages

### Step 5: Configure Domain and Permissions

1. Configure the message domain in the bot management page
2. Ensure the bot has obtained message send/receive permissions
3. If publishing is required, go to "Version Management & Release" to submit for review

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
Successfully connected to Momoka! ๑>ᴗ•๑
Welcome back! This is Momoka~
For more help, type /help
```

### Group Chat Usage

1. Add the bot to a QQ group
2. **@the bot** in the group and send a message

### Direct Message Usage

1. Find the bot in QQ
2. Send a message
