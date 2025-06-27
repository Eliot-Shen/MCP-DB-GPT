# app.py
import uuid
import json
import asyncio
import streamlit as st
from typing import List, Optional

from client import MCPClient


st.set_page_config(page_title="MCP-DB-GPT Chat GUI", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 添加会话状态的历史记录 ✅
if "agent_conversation_history" not in st.session_state:
    st.session_state.agent_conversation_history = []

async def create_client(server_script_path: str, session_id: str) -> MCPClient:
    """
    创建并连接 MCPClient，设置 session_id。
    """
    client = MCPClient()
    await client.set_session_id(session_id)
    await client.connect_to_server(server_script_path)
    return client

def reset_page_data():
    """
    清空上次的分页数据，避免渲染旧结果
    """
    st.session_state.last_results = []
    st.session_state.result_page = 0

# ---------- 同步封装函数（与之前相同思路） ----------

def get_schema_sync(server_script_path: str, table_names: Optional[List[str]]) -> str:
    """
    临时启动 MCPClient，连接服务器，获取 schema，然后关闭。
    """
    async def inner():
        client = await create_client(server_script_path, st.session_state.session_id)
        try:
            res = await client.get_schema(table_names)
        finally:
            try:
                await client.exit_stack.aclose()
            except:
                pass
        return res

    return asyncio.run(inner())

def get_logs_sync(server_script_path: str, limit: int) -> str:
    """
    临时启动 MCPClient，连接服务器，获取日志，然后关闭。
    """
    async def inner():
        client = await create_client(server_script_path, st.session_state.session_id)
        try:
            res = await client.get_query_logs(limit)
        finally:
            try:
                await client.exit_stack.aclose()
            except:
                pass
        return res

    return asyncio.run(inner())

def sql_query_sync(server_script_path: str, sql: str) -> dict:
    """
    临时启动 MCPClient，连接服务器，执行直接 SQL 查询，然后关闭。
    返回一个 dict：{"success": True, "results": [...], "rowCount": n} 或 {"success": False, "error": "..."}
    """
    async def inner():
        client = await create_client(server_script_path, st.session_state.session_id)
        try:
            query_result = await client.session.call_tool("query_data", {
                "sql": sql,
                "session_id": client.session_id
            })
            if query_result and query_result.content:
                data = json.loads(query_result.content[0].text)
                return data
            else:
                return {"success": False, "error": "未从服务器返回结果"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                await client.exit_stack.aclose()
            except:
                pass

    return asyncio.run(inner())

def nlp_query_sync(server_script_path: str, user_query: str, agent_conversation_history: List[dict], use_few_shot: bool):
    """
    临时启动 MCPClient，连接服务器，执行自然语言查询，然后关闭。
    history: 历史对话列表（每项为 {"role": "user"/"assistant", "content": "..."}）
    use_few_shot: 是否要在最前面插入 few-shot 示例
    返回 (raw_response_str, updated_history)
    """
    async def inner(existing_history):
        client = await create_client(server_script_path, st.session_state.session_id)
        try:
            if use_few_shot:
                # 如果你有 FEW_SHOT_EXAMPLES，需要自行导入并赋值：
                from LLM.few_shot_example import FEW_SHOT_EXAMPLES
                client.conversation_history = FEW_SHOT_EXAMPLES.copy()
            else:
                client.conversation_history = []
            # 将已有历史（只要其中是 "user" 和 "assistant" 的对话）放进去
            if existing_history:  # 确保 existing_history 不是 None
                client.conversation_history.extend(existing_history)
            res = await client.process_query(user_query)
            new_conversation = client.conversation_history[-2:]
            # print("existing_history:", existing_history)
            existing_history.extend(new_conversation)
            new_hist = existing_history
        finally:
            try:
                await client.exit_stack.aclose()
            except:
                pass
        return res, new_hist

    raw_resp, updated_history = asyncio.run(inner(agent_conversation_history))
    return raw_resp, updated_history


# ---------- Streamlit 前端开始 ----------

# 帮助文本
HELP_TEXT = """
**使用说明**  
- `schema 表名1 表名2`：获取数据库结构（可指定表名，默认返回所有表结构）。  
- `sql <SQL语句>`：直接执行 SQL 查询（例如 `sql SELECT * FROM users`）。  
- `log [数量]`：显示最近的查询日志（默认 5 条，可以 `log 10`）。  
- 自然语言查询（中文），如“显示所有用户信息”（会由 LLM 生成 SQL 并返回结果）。  
- `new chat`：重置会话历史（仅影响自然语言对话，不会清除 few-shot 示例本身）。  
- `help`：显示使用帮助。   
"""

# 侧边栏：填写服务器脚本路径
with st.sidebar:
    st.header("MCP 服务器路径")
    st.text("请填写 mcp_server.py 或 mcp_server.js 的相对/绝对路径：")
    st.session_state.server_path = st.text_input(
        "Server 脚本 (.py/.js)", st.session_state.get("server_path", "")
    )
    st.markdown("---")
    st.header("命令参考")
    st.markdown(HELP_TEXT)

# 如果没有填写 server_path，就提示并停止
if not st.session_state.get("server_path", "").strip():
    st.warning("请在左侧栏填写 MCP 服务器脚本路径，然后再开始对话。")
    st.stop()

# 初始化会话历史：一个列表，元素为 {"role": "user"/"assistant", "content": "..."}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 用来存储最近一次查询返回的所有行，用于分页展示（List[dict]）
if "last_results" not in st.session_state:
    st.session_state.last_results = []

# 当前分页页码（从0开始计数）
if "result_page" not in st.session_state:
    st.session_state.result_page = 0

# 几条一页
PAGE_SIZE = 10

# 控制是否带 few-shot 示例进 chat_history
if "use_few_shot" not in st.session_state:
    st.session_state.use_few_shot = True

st.title("MCP-DB-GPT Chat GUI")

# 先把已有的对话（如果有）全部渲染出来
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        # 检查是否是日志或schema结果
        if msg.get("is_code", False):
            st.chat_message("assistant").code(msg["content"])
        else:
            st.chat_message("assistant").write(msg["content"])

# 显示一个聊天输入框
if prompt := st.chat_input("请输入命令或自然语言查询..."):
    # 记录用户发送的一条消息
    # agent_conversation_history.append({"role": "user", "content": prompt})
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # # 每次新查询前，把上次分页数据清空
    # st.session_state.last_results = []
    # st.session_state.result_page = 0

    # 准备一个空的聊天气泡用于“正在思考...”
    thinking = st.chat_message("assistant")
    # thinking.write("正在处理，请稍候...")

    # 根据用户输入进行判断
    lower_q = prompt.strip().lower()

    # “help” 命令：直接输出帮助文本
    if lower_q == "help":
        reset_page_data()
        thinking.write(HELP_TEXT)
        st.session_state.chat_history.append({"role": "assistant", "content": HELP_TEXT})

    # “new chat”：只清空历史（保留 few-shot 示例的意图）
    elif lower_q == "new chat":
        reset_page_data()
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.session_state.agent_conversation_history = []
        thinking.write("已重置会话历史。")
        st.session_state.chat_history.append({"role": "assistant", "content": "已重置会话历史。"})

    # “schema” 命令
    elif lower_q.startswith("schema"):
        reset_page_data()

        parts = prompt.strip().split()
        tables = parts[1:] if len(parts) > 1 else None
        try:
            schema_res = get_schema_sync(st.session_state.server_path, tables)
            # thinking.write(f"```text\n{schema_res}\n```")
            # thinking.code(schema_res)
            # 在固定高度的文本区域中显示 schema，可上下滚动查看
            st.text_area("Database Schema", schema_res, height=300)
            st.session_state.chat_history.append({"role": "assistant", "content": schema_res, "is_code": True})
        except Exception as e:
            err = f"获取 schema 时出错：{e}"
            thinking.write(f"```text\n{err}\n```")
            st.session_state.chat_history.append({"role": "assistant", "content": err})

    # “log” 命令
    elif lower_q.startswith("log"):
        reset_page_data()

        parts = prompt.strip().split()
        limit = 5
        if len(parts) > 1:
            try:
                limit = int(parts[1])
            except:
                err = "请在 log 后面输入一个整数作为数量。"
                thinking.write(err)
                st.session_state.chat_history.append({"role": "assistant", "content": err})
        try:
            log_res = get_logs_sync(st.session_state.server_path, limit)
            # thinking.write(f"```text\n{log_res}\n```")
            thinking.code(log_res)
            st.session_state.chat_history.append({"role": "assistant", "content": log_res, "is_code": True})
        except Exception as e:
            err = f"获取日志时出错：{e}"
            thinking.write(f"```text\n{err}\n```")
            st.session_state.chat_history.append({"role": "assistant", "content": err})

    # 直接 SQL
    elif lower_q.startswith("sql "):
        reset_page_data()

        sql = prompt.strip()[4:].strip()
        if not sql:
            err = "请在 sql 命令后提供有效的 SQL 语句。"
            thinking.write(err)
            st.session_state.chat_history.append({"role": "assistant", "content": err})
        else:
            try:
                res = sql_query_sync(st.session_state.server_path, sql)
                if res.get("success"):
                    # 如果返回了结果列表，就保存到 session_state 以便分页展示
                    all_rows = res.get("results", [])
                    st.session_state.last_results = all_rows.copy()
                    st.session_state.result_page = 0

                    # 构建一个简单的文本反馈（说明总条数），实际结果会在下方分页控件里展示
                    summary = f"执行的 SQL: `{sql}`\n共 {res.get('rowCount', len(all_rows))} 条记录，支持分页查看。"
                    thinking.write(summary)
                    st.session_state.chat_history.append({"role": "assistant", "content": summary})

                    # # 渲染分页
                    # render_pagination()
                else:
                    err = f"查询失败：{res.get('error', '未知错误')}"
                    thinking.write(err)
                    st.session_state.chat_history.append({"role": "assistant", "content": err})
            except Exception as e:
                err = f"执行 SQL 时出错：{e}"
                thinking.write(err)
                st.session_state.chat_history.append({"role": "assistant", "content": err})

    # 其他情况，当作自然语言查询交给 LLM
    else:
        try:
            # 将已有对话历史（只保留 role/content）传给 nlp_query_sync
            raw_response, updated_history = nlp_query_sync(
                st.session_state.server_path,
                prompt,
                st.session_state.agent_conversation_history,
                st.session_state.use_few_shot
            )
            # 更新历史
            st.session_state.agent_conversation_history = updated_history
            # print(updated_history)
            # st.session_state.chat_history.extend(updated_history[-2:])

            # 尝试把 raw_response 当作 JSON 解析
            try:
                resp_data = json.loads(raw_response)
                # 如果 LLM 直接给了 direct_response
                if resp_data.get("direct_response"):
                    reset_page_data()

                    content = resp_data["direct_response"]
                    thinking.write(content)
                    st.session_state.chat_history.append({"role": "assistant", "content": content})
                    st.session_state.agent_conversation_history.append({"role": "assistant", "content": content})

                # 如果 LLM 返回了 SQL + results
                elif resp_data.get("sql"):
                    sql_text = resp_data["sql"]
                    buf = f"执行的 SQL: `{sql_text}`\n"

                    res  = resp_data.get("results", [])
                    if res.get("success"):
                        all_rows = res.get("results", [])
                        if all_rows:
                            st.session_state.last_results = all_rows.copy()
                            st.session_state.result_page = 0
                            buf += f"共 {len(all_rows)} 条记录，支持分页查看。"
                            # # 渲染分页
                            # render_pagination()
                        else:
                            buf += "查询未返回结果。"
                            st.session_state.last_results = []
                    else:
                        buf += f"查询失败：{res.get('error', '未知错误')}"
                        
                    thinking.write(buf)
                    st.session_state.chat_history.append({"role": "assistant", "content": buf})
                    st.session_state.agent_conversation_history.append({"role": "assistant", "content": buf})

                else:
                    # 如果返回格式不符合预期，就原样输出
                    thinking.write(raw_response)
                    st.session_state.chat_history.append({"role": "assistant", "content": raw_response})
                    st.session_state.agent_conversation_history.append({"role": "assistant", "content": raw_response})
            except json.JSONDecodeError:
                thinking.write(raw_response)
                st.session_state.chat_history.append({"role": "assistant", "content": raw_response})
        except Exception as e:
            err = f"自然语言查询时出错：{e}"
            thinking.write(err)
            st.session_state.chat_history.append({"role": "assistant", "content": err})

# ---------- 分页展示区域 ----------

def render_pagination():
    """
    当 st.session_state.last_results 不为空时，渲染分页控件和当前页的数据表。
    """
    results = st.session_state.get("last_results", [])
    if not results:
        return

    total = len(results)
    total_pages = (total - 1) // PAGE_SIZE + 1

    # 保证 page_index 在合法范围
    if st.session_state.result_page < 0:
        st.session_state.result_page = 0
    if st.session_state.result_page >= total_pages:
        st.session_state.result_page = total_pages - 1

    start = st.session_state.result_page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_data = results[start:end]

    # 显示分页导航
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 1, 4])
    with nav_col1:
        if st.button("上一页", key="prev_page"):
            if st.session_state.result_page > 0:
                st.session_state.result_page -= 1
    with nav_col2:
        if st.button("下一页", key="next_page"):
            if st.session_state.result_page < total_pages - 1:
                st.session_state.result_page += 1
    with nav_col3:
        st.write(f"第 {st.session_state.result_page + 1}/{total_pages} 页")
    # 第四列留白，或者放其他摘要

    # 显示当前页的表格
    import pandas as pd

    # 如果 page_data 元素是 dict，就直接做 DataFrame；否则按原样显示文本
    if isinstance(page_data, list) and page_data and isinstance(page_data[0], dict):
        df = pd.DataFrame(page_data)
        st.dataframe(df)
    else:
        # 如果不是 list of dict，就把列表元素原样打印
        st.write(page_data)

# 在主界面最后调用渲染函数
render_pagination()
