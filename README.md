<div align="center">
  <img src="image/logo.png" alt="Momoka Logo" width="400">
  <h1>Momoka v0.2</h1>
  <p>"ふふ、待ってたよ~"</p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License"></a>
  </p>
</div>

---

<div align="center">

[English](README_EN.md) | **中文**

</div>

---

**Momoka** 是一个本地运行的 Agent 助手。编写代码、整理文档、浏览网页……一切只需一行需求。

## 🎉 2026.3 更新
- 🔌 全面接入 Skill 生态
- 🌐 新增网页点击、滑动、表单填写等操作、更稳定的浏览器指纹
- 📁 新增 Excel/Word 文档阅读和编辑操作支持
- 💬 更友好的交互界面
- 🛠️ 架构升级

## ✨ Features

#### 连接至ChatGPT、Gemini、Claude、Deepseek、GLM、Kimi等支持Openai SDK的任意AI模型，并在终端中运行Momoka。

<div align="center">
  <img src="image/1.gif" width="400">
</div>

- #### 运用丰富的内置工具，Momoka可以自动完成项目构建、调试和迭代的全流程。

<div align="center">
  <img src="image/2.gif" width="400">
</div>

- #### 通过经过优化的网页解析和浏览器指纹，Momoka可以在复杂的网页环境中提高任务成功率及降低Token消耗。

## 🚀 快速开始

### 加载

```bash
git clone https://github.com/xiaomi2023/Momoka
```

### 安装依赖

```bash
pip install openai rebrowser-playwright openpyxl python-docx rich
python -m rebrowser_playwright install chromium
```

### 运行

```bash
python main.py
```

### 配置

运行后，在控制台输入以下命令以配置模型API的Base Url和API Key，以及Momoka的工作目录：
```bash
/set base_url https://api.XXX.com
/set api_key sk-***
/set work_dir "C:\\Users\\..."
```
输入 **/model** 选择模型，并发送测试信息确保一切就绪。  
可以通过 **/help** 命令获取帮助，或 **/set** 命令获取更多参数信息。

## 🔧 Skill
**Skill** 是一种模块化、可复用的指令与工具包，可以拓展模型的能力或让模型掌握更多知识。  
通过在\skill目录中添加包含 **SKILL.md** 和资源文件（可选）的Skill文件夹来配置Skill。Skill可以通过Agent动态加载，也可通过命令 **/[Skill name]** 手动加载Skill。  
更多信息，请参考[这里](https://platform.claude.com/docs/zh-CN/agents-and-tools/agent-skills/)。

## 📄 License
This repository is licensed under the [Apache License 2.0](LICENSE).
