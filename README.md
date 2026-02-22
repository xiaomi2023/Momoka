<div align="center">
<img width="590" height="305" alt="MOMOKA_LOGO" src="https://github.com/user-attachments/assets/b52e6799-790a-40a5-9d9e-065a4202ffb5" />
</div>

<div align="center">
  <h3>"from Demand to Delivery"</h3>
</div>

---

## 介绍
Momoka v0.1是一个LLM驱动的电脑操作助理，目前支持编辑文件、操作终端、浏览器交互等操作，只需要一行需求，就可以自动执行各种操作以完成任务。  

**Example: 使用Momoka与浏览器交互并生成图表**
```bash
请输入你的需求: 分别查找最新的北京、上海、广州的人均GDP并将数据制作成图表
[LOG] 开始
[BOT REPORT] 为了完成需求，我将：1. 搜索北京、上海、广州的最新人均GDP数据；2. 将数据整理并制作成图表。首先，我将打开浏览器搜索数据。
...
[LOG] 浏览器打开：https://www.baidu.com/s?wd=上海2024年人均GDP
[LOG] 浏览器读取页面内容
[LOG] 浏览器页面搜索：'2024年北京市人均GDP'
[LOG] 浏览器点击：[1]
...
[BOT REPORT] 已收集到数据：北京22.82万元/人，上海21.71万元/人，广州16.42万元/人。我将制作图表。首先，在工作目录中创建一个CSV文件存储数据，然后用Python生成图表。
...
[LOG] Bot开始编辑文件：C:\Users\...\plot_gdp.py
[LOG] 终端输入：python plot_gdp.py
[LOG] 终端输出：图表已保存为 gdp_chart.png 和 gdp_chart.pdf
[BOT] 已完成任务。
```
<img width="480" height="360" alt="gdp_chart" src="https://github.com/user-attachments/assets/d3369f8c-51f1-4616-abfb-54630e154234" />  


## 部署
### 1、加载仓库
```bash
git clone https://github.com/xiaomi2023/Momoka/
```

### 2、在config.json配置LLM的API和工作目录
```json
{
  "api_key": "sk-XXX",
  "base_url": "https://api.XXX.com",
  "model": "...",
  "work_dir": "C:\\Users\\...",
  ...
}
```

### 3、运行Momoka
```bash
python main.py
```


## 配置
| 参数名 | 类型 | 描述 |
|------|------|:----:|
| api_key | string | 调用LLM的API Key |
| base_url | string | 调用LLM的base_url |
| model | string | 调用LLM的模型名 |
| work_dir | string | Momoka工作的默认目录，编辑此目录之外的文件需要经过用户同意 |
| encoding | string | Momoka处理文件时的编码 |
| summary | bool | 在Momoka完成工作后生成工作总结 |
| dialogue | bool | 在Momoka完成工作后与Bot对话 |
| fold | bool | 折叠Bot上下文中重复的文本，对于不支持缓存输入的模型建议开启以节省Token |


## License
This repository is licensed under the [Apache-2.0 License](LICENSE).
