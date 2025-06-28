# 🧠 my-db-gpt: Natural Language to SQL Client with LLM + MCP

一个支持中文自然语言查询 MySQL 数据库的终端客户端，结合通义千问大语言模型与 [MCP 协议](https://modelcontextprotocol.org)，无需编写 SQL，即可完成数据查询、日志追踪、结构查看等任务。

A terminal‑based client for querying MySQL databases using natural language, integrated with the TongYi QianWen LLM and the MCP Protocol, enabling you to query data, view logs, inspect schemas, and perform tasks—all without writing SQL.

---

## ✨ Features

- ✅ Natural‑language-to‑SQL queries, with Chinese language support

- 📜 Query logs with history and traceability

- 🧠 Integrated TongYi QianWen language model

- 🔌 MCP protocol for seamless client‑server interaction

- 🧩 Command‑line interface (CLI) for schema viewing, SQL execution, chat history, and more

---

## 🚀 Quick Start

### 1. Clone the repo into a local folder

```bash
git clone https://github.com/Eliot-Shen/MCP-DB-GPT.git
cd MCP-DB-GPT

```

### 2. Install packages

```bash
uv venv  # 会在项目根目录生成 .venv 虚拟环境
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

uv sync
```

### 3. Modify Environment Variables

Create an .env file and modify the environment variables. Example: .env.example is as follows.

```markdown
# MYSQL Configurations

DB_HOST=localhost  
DB_USER=root
DB_PASSWORD="123456"
DB_NAME="college"
DB_PORT=3306
SENSITIVE_FIELDS="password;salary;pin"

# Model Configurations

model_name = "qwen-plus"
api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key = "xxx"
```

### 4. Run CLI

```bash
python client.py .\mcp_mysql_server\run_server.py
```

### 5. Run UI

```bash
streamlit run app.py
```
