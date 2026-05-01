# Quick Start

### Deployment

#### Download Release (Recommended)
Get the latest Momoka version [here](https://github.com/xiaomi2023/Momoka/releases).

or

#### Clone Repository

```bash
git clone https://github.com/xiaomi2023/Momoka
```

### Install Dependencies

```bash
pip install -r requirements.txt
python -m rebrowser_playwright install chromium
```

### Run

```bash
python main.py
```

### Configuration

1. After running, enter the following commands to configure the model API's Base URL and API Key:
```bash
/set base_url https://api.XXX.com
/set api_key sk-***
```

2. Enter **/model** to select a model.

3. (Optional) Enter the command:
```bash
/set work_dir C:\\Users\\...
```
to configure the working directory for Momoka.

All configurations may require a restart to take effect. (If there are any exceptions during configuration, you can configure the related fields in config.json.)  
Send a test message to ensure everything is ready, then start using it!
