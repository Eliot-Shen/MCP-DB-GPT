import json
import uuid
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from typing import Optional, List
from contextlib import AsyncExitStack

from LLM.api import TongYiAPI
from LLM.few_shot_example import FEW_SHOT_EXAMPLES

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
load_dotenv()  # load environment variables from .env

banner = r"""
    __  _____________        ____  ____        __________  ______
   /  |/  / ____/ __ \      / __ \/ __ )      / ____/ __ \/_  __/
  / /|_/ / /   / /_/ /_____/ / / / __  |_____/ / __/ /_/ / / /   
 / /  / / /___/ ____/_____/ /_/ / /_/ /_____/ /_/ / ____/ / /    
/_/  /_/\____/_/         /_____/_____/      \____/_/     /_/    

"""
def print_banner():
    print('#'*65)
    print(banner)
    print('#'*65)

def print_help():
    """Print help message"""
    print("\n=== 使用说明 ===")
    print("支持的命令：")
    print("1. schema 表名1 表名2 - 显示数据库结构，可指定表名，默认返回所有表结构")
    print("2. sql <SQL语句> - 直接执行SQL查询（如：sql SELECT * FROM users）")
    print("3. log [数量] - 显示该会话最近的查询日志，可指定数量（默认5条）")
    print("4. 自然语言查询 - 用中文描述你的需求（如：显示所有用户信息）")
    print("5. quit - 退出程序")
    print("6. help - 显示帮助信息")
    print("7. new chat - 重置会话")
    print("\n注意：")
    print("- 使用'sql'命令时会直接执行SQL，不经过LLM处理，sql语句不用加;结尾")
    print("- 自然语言查询会通过LLM处理，返回结果包含SQL和查询结果")

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.llm = TongYiAPI()
        self.session_id = str(uuid.uuid4())
        self.use_few_shot = True
        self.conversation_history = FEW_SHOT_EXAMPLES if self.use_few_shot else []

    async def set_session_id(self, session_id: str):
        self.session_id = session_id

    # methods will go here
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        # try:
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        print(f"Session_id: {self.session_id}")

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

        # List available resources
        resources_response = await self.session.list_resources()
        if resources_response and resources_response.resources:
            print("Available resources:", [resource.uri for resource in resources_response.resources])
        else:
            print("Available resources templates: ['logs']")
        
        prompts = await self.session.list_prompts()
        if prompts and prompts.prompts:
            print("Available prompts:", [prompt.name for prompt in prompts.prompts])
        else:
            print("No available prompts found.")
        # except Exception as e:
        #     import traceback
        #     traceback.print_exc()
        #     print(f"Error: {str(e)}")
        #     raise

    async def get_query_logs(self, limit: int = 5) -> str:
        """获取查询日志"""
        try:
            # logs_response = await self.session.call_tool("get_query_logs", {"limit": limit})
            logs_response = await self.session.read_resource(f"logs://{self.session_id}/{limit}")
            
            if not logs_response or not logs_response.contents:
                return "无法获取查询日志"
            
            logs_info = json.loads(logs_response.contents[0].text)
            if not logs_info.get("success"):
                return f"获取日志失败: {logs_info.get('error', '未知错误')}"
            
            logs = logs_info.get("logs", [])
            total_queries = logs_info.get("total_queries", 0)
            
            if not logs:
                return "没有查询日志记录"
            
            result = []
            result.append(f"\n最近的{len(logs)}条查询日志:")
            for log in logs:
                result.append(f"\n时间: {log['timestamp']}")
                result.append(f"操作: {log['operation']}")
                result.append(f"状态: {'成功' if log['success'] else '失败'}")
                if not log['success'] and log.get('error'):
                    result.append(f"错误信息: {log['error']}")
                result.append("-" * 40)
            
            return "\n".join(result)
        except Exception as e:
            return f"获取查询日志时出错: {str(e)}"
    
    async def get_schema(self, table_names: Optional[List[str]] = None) -> str:
        """获取数据库结构信息"""
        try:
            params = {}
            params["session_id"] = self.session_id
            if table_names:
                params["table_names"] = table_names

            schema_response = await self.session.call_tool("get_schema", params)
            if not schema_response or not schema_response.content:
                return "无法获取数据库结构信息"
            
            schema_info = json.loads(schema_response.content[0].text)
            if not schema_info.get("success"):
                return f"获取数据库结构失败: {schema_info.get('error', '未知错误')}"
            
            database_name = schema_info["database"]
            tables_schema = schema_info["tables"]
            
            result = []
            result.append(f"数据库名: {database_name}")
            result.append("\n---表结构---")
            
            # 显示每个表的结构
            for table_name, columns in tables_schema.items():
                result.append(f"\n表名: {table_name}")
                result.append("列信息:")
                for column in columns:
                    result.append(f"  - {column['name']} ({column['type']})")
                    if column['key'] == 'PRI':
                        result.append("    主键")
                    if column['null'] == 'NO':
                        result.append("    非空")
                    if column['default']:
                        result.append(f"    默认值: {column['default']}")
                    if column['extra']:
                        result.append(f"    额外信息: {column['extra']}")
            
            return "\n".join(result)
        except Exception as e:
            return f"获取数据库结构时出错: {str(e)}"

    async def process_query(self, query: str) -> str:
        """使用通义千问处理数据库相关查询"""
        try:
            prompt = await self.session.get_prompt("generate_db_gpt_prompt")
            prompt = prompt.messages[0].content.text
            llm_response = self.llm.chat(system_prompt=prompt, content=query, response_format="json_object", conversation_history=self.conversation_history)
            response_data = json.loads(llm_response)

            self.conversation_history.append({
                "role": "user",
                "content": query
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": str(response_data)
            })

            # 如果有直接响应，直接返回
            if response_data.get("direct_response"):
                return response_data["direct_response"]
            
            # 如果有SQL查询，执行它
            if response_data.get("sql"):
                # 执行SQL查询
                query_result = await self.session.call_tool("query_data", {
                    "sql": response_data["sql"],
                    "session_id": self.session_id
                })
                # print(query_result)
                # 构建最终响应
                final_response = {
                    "thoughts": response_data["thoughts"],
                    "sql": response_data["sql"],
                    "display_type": response_data.get("display_type", "Table"),
                    "results": json.loads(query_result.content[0].text) if query_result.content[0].text else None
                }
                
                return json.dumps(final_response, ensure_ascii=False, indent=2)
            
            return "无法处理查询，LLM响应中没有SQL语句或直接响应"

        except Exception as e:
            return f"处理查询时出错: {str(e)}"

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print_help()

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                if query.lower() == 'help':
                    print_help()
                    continue

                if query.lower() == 'new chat':
                    self.conversation_history = FEW_SHOT_EXAMPLES if self.use_few_shot else []
                    await self.set_session_id(str(uuid.uuid4()))
                    print("\n会话已重置")
                    continue
                
                # 处理直接SQL查询命令
                if query.lower().startswith('sql '):
                    # 提取SQL语句
                    sql = query[4:].strip()
                    if not sql:
                        print("\n请在sql命令后提供有效的SQL语句")
                        continue
                    
                    try:
                        # 直接调用query_data工具执行SQL
                        query_result = await self.session.call_tool("query_data", {
                            "sql": sql,
                            "session_id": self.session_id
                        })
                        
                        if query_result and query_result.content:
                            result_data = json.loads(query_result.content[0].text)
                            print(f"\n执行的SQL: {sql}")
                            
                            if result_data.get("success"):
                                print("\n查询结果:")
                                print(json.dumps(result_data["results"], indent=2, ensure_ascii=False))
                                print(f"\n共 {result_data.get('rowCount', 0)} 条记录")
                            else:
                                print(f"\n查询失败: {result_data.get('error', '未知错误')}")
                        else:
                            print("\n查询未返回结果")
                    except Exception as e:
                        print(f"\n执行SQL查询时出错: {str(e)}")
                    continue
                    
                # 处理schema命令
                if query.lower().startswith('schema'):
                    # 解析表名参数 - 支持简单空格分隔格式
                    parts = query.split()
                    table_names = None
                    if len(parts) > 1:
                        # 直接取第一个空格后的所有部分作为表名列表
                        table_names = parts[1:]
                    response = await self.get_schema(table_names)
                    print(f"\n{response}")
                    continue
                
                # 处理log命令
                if query.lower().startswith('log'):
                    limit = 5
                    parts = query.split()
                    if len(parts) > 1:
                        try:
                            limit = int(parts[1])
                        except ValueError:
                            print("\n请输入有效的日志数量")
                            continue
                    
                    response = await self.get_query_logs(limit)
                    print(f"\n{response}")
                    continue

                # 处理SQL或自然语言查询
                response = await self.process_query(query)
                
                # 尝试解析返回的JSON
                try:
                    # 如果是JSON格式，解析并格式化显示
                    response_data = json.loads(response)
                    
                    # 如果有直接响应，显示它
                    if response_data.get("direct_response"):
                        print(f"\n{response_data['direct_response']}")
                    # 如果有SQL查询结果，显示SQL和结果
                    elif response_data.get("sql"):
                        print(f"\n执行的SQL: {response_data['sql']}")
                        if response_data.get("results"):
                            print("\n查询结果:")
                            print(json.dumps(response_data["results"], indent=2, ensure_ascii=False))
                        else:
                            print("\n查询未返回结果")
                except json.JSONDecodeError:
                    # 如果不是JSON格式，直接显示
                    print(f"\n{response}")

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    print_banner()
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())