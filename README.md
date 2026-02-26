<div align="center">
<img width="590" height="305" alt="MOMOKA_LOGO" src="https://github.com/user-attachments/assets/b52e6799-790a-40a5-9d9e-065a4202ffb5" />
</div>

<div align="center">
  <h3>"from Demand to Delivery"</h3>
</div>

<div align="center">
  <a href="#chinese">中文</a> | <a href="#english">English</a>
</div>

---

<h2 id="chinese">🇨🇳 中文</h2>

<!-- TOC -->
  * [介绍](#介绍)
  * [Example](#example)
  * [部署](#部署)
    * [1、加载仓库](#1加载仓库)
    * [2、配置环境](#2配置环境)
    * [3、在config.json配置LLM的API和工作目录](#3在configjson配置llm的api和工作目录)
    * [4、运行Momoka](#4运行momoka)
  * [配置](#配置)
  * [License](#license)
<!-- TOC -->

### 介绍
Momoka是一个LLM驱动的电脑操作助理，支持：
* **阅读、编辑您电脑的文件**
* **使用终端运行各种命令**
* **读取网页并与之交互**

而这一切都仅仅只需要一段指令，所有操作就均会由Momoka自动完成。

### Example

* 使用Momoka与浏览器交互并生成图表
```bash
请输入你的需求: 分别查找最新的北京、上海、广州的人均GDP并将数据制作成图表
[LOG] 开始
[BOT REPORT] 为了完成需求，我将：1. 搜索北京、上海、广州的最新人均GDP数据；2. 将数据整理并制作成图表。首先，我将打开浏览器搜索数据。
...
[LOG] 浏览器打开：https://www.baidu.com/s?wd=上海2024年人均GDP
[LOG] 浏览器读取页面内容
...
[BOT REPORT] 已收集到数据：北京22.82万元/人，上海21.71万元/人，广州16.42万元/人。我将制作图表。首先，在工作目录中创建一个CSV文件存储数据，然后用Python生成图表。
...
[LOG] Bot开始编辑文件：C:\Users\...\plot_gdp.py
[LOG] 终端输入：python plot_gdp.py
[LOG] 终端输出：图表已保存为 gdp_chart.png 和 gdp_chart.pdf
[BOT] 已完成任务。
```
<img width="480" height="360" alt="gdp_chart" src="https://github.com/user-attachments/assets/d3369f8c-51f1-4616-abfb-54630e154234" />

### 部署

#### 1、加载仓库
```bash
git clone https://github.com/xiaomi2023/Momoka/
```

#### 2、配置环境
```bash
pip install openai playwright
playwright install chromium
```

#### 3、在config.json配置LLM的API和工作目录
```json
{
  "api_key": "sk-XXX",
  "base_url": "https://api.XXX.com",
  "model": "...",
  "work_dir": "C:\\Users\\...",
  ...
}
```

#### 4、运行Momoka
```bash
python main.py
```

### 配置

| 参数名       | 类型           |                   描述                    |
|-----------|--------------|:---------------------------------------:|
| api_key   | string       |              调用LLM的API Key              |
| base_url  | string       |             调用LLM的base_url              |
| model     | string       |                调用LLM的模型名                |
| work_dir  | string       |    Momoka工作的默认目录，编辑此目录之外的文件需要经过用户同意     |
| encoding  | string       |             Momoka处理文件时的编码              |
| summary   | bool         |           在Momoka完成工作后生成工作总结            |
| dialogue  | bool         |           在Momoka完成工作后与Bot对话            |
| fold      | bool         | 折叠Bot上下文中重复的文本，对于不支持缓存输入的模型建议开启以节省Token |
| mute_log  | list[string] |    省略部分控制台日志输出，如"['CMD', 'BROWSER']"    |
| user_call | string       |            Bot对用户的称呼，默认为null            |

### License

This repository is licensed under the [Apache-2.0 License](LICENSE).

---

<h2 id="english">🇬🇧 English</h2>

<!-- TOC-EN -->
  * [Introduction](#introduction)
  * [Example](#example-en)
  * [Deployment](#deployment)
    * [1. Clone the Repository](#1-clone-the-repository)
    * [2. Set Up the Environment](#2-set-up-the-environment)
    * [3. Configure the LLM API and Working Directory in config.json](#3-configure-the-llm-api-and-working-directory-in-configjson)
    * [4. Run Momoka](#4-run-momoka)
  * [Configuration](#configuration)
  * [License](#license-en)
<!-- TOC-EN -->

### Introduction

Momoka is an LLM-powered computer operation assistant that supports:
* **Reading and editing files on your computer**
* **Running various commands via the terminal**
* **Reading web pages and interacting with them**

All of this requires only a single instruction — every action is then carried out automatically by Momoka.

### Example <span id="example-en"></span>

* Using Momoka to interact with a browser and generate charts

```bash
Please enter your request: Search for the latest per capita GDP of Beijing, Shanghai, and Guangzhou and create a chart from the data
[LOG] Starting
[BOT REPORT] To fulfill the request, I will: 1. Search for the latest per capita GDP data for Beijing, Shanghai, and Guangzhou; 2. Organize the data and create a chart. First, I will open the browser to search for the data.
...
[LOG] Browser opened: https://www.baidu.com/s?wd=Shanghai+2024+per+capita+GDP
[LOG] Browser reading page content
...
[BOT REPORT] Data collected: Beijing 228,200 CNY/person, Shanghai 217,100 CNY/person, Guangzhou 164,200 CNY/person. I will now create a chart. First, I will create a CSV file in the working directory to store the data, then use Python to generate the chart.
...
[LOG] Bot started editing file: C:\Users\...\plot_gdp.py
[LOG] Terminal input: python plot_gdp.py
[LOG] Terminal output: Chart saved as gdp_chart.png and gdp_chart.pdf
[BOT] Task completed.
```

<img width="480" height="360" alt="gdp_chart" src="https://github.com/user-attachments/assets/d3369f8c-51f1-4616-abfb-54630e154234" />

### Deployment

#### 1. Clone the Repository
```bash
git clone https://github.com/xiaomi2023/Momoka/
```

#### 2. Set Up the Environment
```bash
pip install openai playwright
playwright install chromium
```

#### 3. Configure the LLM API and Working Directory in config.json
```json
{
  "api_key": "sk-XXX",
  "base_url": "https://api.XXX.com",
  "model": "...",
  "work_dir": "C:\\Users\\...",
  ...
}
```

#### 4. Run Momoka
```bash
python main.py
```

### Configuration

| Parameter  | Type         | Description |
|------------|--------------|:-----------:|
| api_key    | string       | API Key for calling the LLM |
| base_url   | string       | base_url for calling the LLM |
| model      | string       | Model name for the LLM |
| work_dir   | string       | Default working directory for Momoka. User approval is required to edit files outside this directory |
| encoding   | string       | Encoding used by Momoka when processing files |
| summary    | bool         | Generate a work summary after Momoka completes a task |
| dialogue   | bool         | Enable conversation with the bot after Momoka completes a task |
| fold       | bool         | Collapse repeated text in the bot's context. Recommended for models that do not support cached inputs, to save tokens |
| mute_log   | list[string] | Suppress certain console log outputs, e.g. `["CMD", "BROWSER"]` |
| user_call  | string       | How the bot addresses the user. Defaults to null |

### License <span id="license-en"></span>

This repository is licensed under the [Apache-2.0 License](LICENSE).