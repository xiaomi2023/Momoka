# Lark (BETA)

Momoka can run as a Lark Bot, allowing you to communicate with Momoka through Lark.

## Create a Lark Application

### Step 1: Create an Application

1. Visit the [Lark Open Platform](https://open.larksuite.com/) or [Feishu Open Platform](https://open.feishu.cn/)
2. Enter the developer backend
3. Click **"Create Enterprise Custom Application"**
4. Enter the application name and description
5. Click **"Create"**

### Step 2: Obtain Application Credentials

1. In the application management console, navigate to **"Credentials & Basic Information"**
2. Find and copy the following information:
   - **App ID**
   - **App Secret**

### Step 3: Configure Permissions

1. Go to **"Permission Management"**
2. Ensure the following permissions are enabled:
   - `im:message` - Receive and send messages
   - `im:message:send_as_bot` - Send messages as a bot
   - `im:resource` - Obtaining and uploading image or file resources
   - `im:chat:readonly` - Read group chat information (optional)
   - `contact:user.id:readonly` - Read user IDs (optional)

### Step 4: Configure Event Subscriptions

1. Go to **"Event Subscription"**
2. Enable the following event:
   - `Receive Messages im.message.receive_v1`

### Step 5: Publish the Application (if required)

1. Go to **"Version Management & Release"**
2. Create a new version
3. Fill in the update description
4. Submit for review
5. Wait for the review to complete

## Configuration

Add Lark configuration to `config.json`:

```json
{
  "interface": "lark",
  "lark": {
    "app_id": "cli_xxxxxxxxxx",
    "app_secret": "xxxxxxxxxxxxxxxxxxxxxxxx"
  }
}
```

### Configuration Parameters

| Parameter           | Type       | Description                                           |
|---------------------|------------|-------------------------------------------------------|
| `interface`         | `string`   | Set to `"lark"` to make Momoka run in Lark by default |
| `lark.app_id`       | `string`   | Your Lark application App ID                          |
| `lark.app_secret`   | `string`   | Your Lark application App Secret                      |

## Running the Bot

### Method 1: Configuration File

Set `"interface": "lark"` in `config.json` and run:

```bash
python main.py
```

### Method 2: Command Line Arguments

Run:

```bash
python main.py --interface lark
```

## Usage

### Starting a Conversation

Please go to the "Messenger" interface, search for the robot you just created, 
and send a message to start a conversation.  
If you see the following message, the connection is successful:

```
Successfully connected to Lark
Welcome back! This is Momoka~
Developed by Mikoris | For more help, type /help
```
