<div align="center">
  <img src="image/logo.png" alt="Momoka Logo" width="400">
  <h1>Momoka v0.2</h1>
  <p>"ふふ、待ってたよ~"</p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
    <img src="https://img.shields.io/github/last-commit/xiaomi2023/Momoka" alt="Last Commit">
  </p>
</div>

<div align="center">

**English** | [中文](README.md)

</div>

---

**Momoka** is a locally running AI Agent assistant. Communicate with Momoka or send tasks via CLI, Discord, Lark or QQ. Write code, organize documents, browse the web... everything with just a single line of request.

### 🎉 April 2026 Update
- 🔌 Fully integrated with MCP Server ecosystem
- 🧩 Support for custom Momoka Servers
- 🛠️ More secure system configuration monitoring mechanism
- 🤖 Integrated with Discord and Lark

### 🎉 March 2026 Update
<details>
<summary>Update Details</summary>

- 🔌 Fully integrated with Skill ecosystem
- 🌐 Added web page clicking, scrolling, form filling and other operations; more stable browser fingerprint
- 📁 Added support for Excel/Word document reading and editing
- 💬 More user-friendly interactive interface
- 🛠️ Architecture upgrade

</details>

## ✨ Features

#### Connect to any AI model supporting OpenAI SDK such as ChatGPT, Gemini, Claude, Deepseek, GLM, Kimi, and run Momoka in the terminal.

<div align="center">
  <img src="image/1.png" width="600">
</div>

- #### With rich built-in tools, Momoka can automatically complete the full process of project building, debugging and iteration.

<div align="center">
  <img src="image/2.png" width="600">
</div>

<div align="center">
  <img src="image/4.png" width="600">
</div>

- #### Through optimized web page parsing and browser fingerprint, Momoka improves task success rate and reduces context window in complex web environments.

<div align="center">
  <img src="image/3.png" width="600">
</div>

## 🚀 Quick Start

### Clone

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

After running, enter the following commands in the console to configure the Base URL and API Key for the model API:

```bash
/set base_url https://api.XXX.com
/set api_key sk-***
```

Rerun the program, then enter **/model** to select a model.
If there are any exceptions during configuration, you can configure the related fields in config.json.
Send a test message to ensure everything is ready, then you can chat with Momoka or ask Momoka to perform tasks.

## 🧩 Customization & Extensions
- Configure MCP Servers: [MCP Server](https://xiaomi2023.github.io/Momoka/mcp_integration/)
- Configure Skills: [Skill](https://xiaomi2023.github.io/Momoka/skill/)
- Configure Momoka Server: [Momoka Server](https://xiaomi2023.github.io/Momoka/momoka_server/)
- Headless Mode: [Headless Mode](https://xiaomi2023.github.io/Momoka/headless/)

## 🤖 More Platforms
- [Discord](https://xiaomi2023.github.io/Momoka/discord/)
- [Lark](https://xiaomi2023.github.io/Momoka/lark/)
- [QQ](https://xiaomi2023.github.io/Momoka/qq/)

## 📄 More Information
For operation guides, configuration, extensions and more information, please refer to [Momoka Documentation](https://xiaomi2023.github.io/Momoka/).

## License
This repository is licensed under the [Apache License 2.0](LICENSE).
