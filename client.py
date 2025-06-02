import asyncio
from typing import Optional
from contextlib import AsyncExitStack
import json

from LLM.api import TongYiAPI
from LLM.prompt_template import DB_GPT_SYSTEM_PROMPT

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

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.llm = TongYiAPI()

    # methods will go here
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
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

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

        # List available resources
        resources_response = await self.session.list_resources()
        if resources_response and resources_response.resources:
            print("Available resources:", [resource.uri for resource in resources_response.resources])
        else:
            print("No available resources found.")

    async def process_query(self, query: str) -> str:
        """使用通义千问处理数据库相关查询"""
        try:
            # 获取数据库表列表
            tables_response = await self.session.read_resource("mysql://tables")
            if not tables_response or not tables_response.contents:
                return "无法获取数据库表信息"
            
            tables_info = json.loads(tables_response.contents[0].text)
            database_name = tables_info["database"]
            tables = tables_info["tables"]
            
            # 获取所有表的描述信息
            table_definitions = []
            for table in tables:
                desc_response = await self.session.read_resource(f"mysql://table/{table}/describe")
                if desc_response and desc_response.contents:
                    table_desc = json.loads(desc_response.contents[0].text)
                    if table_desc.get("success"):
                        table_definitions.append(table_desc["table_definition"])
            
            # 填充模板
            prompt = DB_GPT_SYSTEM_PROMPT.format(
                database_name=database_name,
                table_definitions="\n".join(table_definitions),
            )
            
            # 调用通义千问API
            llm_response = self.llm.chat(prompt, query, response_format="json_object")
            
            # 解析LLM响应
            response_data = json.loads(llm_response)
            
            # 如果有直接响应，直接返回
            if response_data.get("direct_response"):
                return response_data["direct_response"]
            
            # 如果有SQL查询，执行它
            if response_data.get("sql"):
                # 执行SQL查询
                query_result = await self.session.call_tool("query_data", {
                    "sql": response_data["sql"]
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
        print("\n=== 使用说明 ===")
        print("支持的命令：")
        print("1. schema - 显示数据库结构")
        print("2. sql <SQL语句> - 直接执行SQL查询（如：sql SELECT * FROM users）")
        print("3. 自然语言查询 - 用中文描述你的需求（如：显示所有用户信息）")
        print("4. quit - 退出程序")
        print("\n注意：")
        print("- 使用'sql'命令时会直接执行SQL，不经过LLM处理，sql语句不用加;结尾")
        print("- 自然语言查询会通过LLM处理，返回结果包含SQL和查询结果")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break
                
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
                            "sql": sql
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
                    
                if query.lower() == 'schema':
                    # 直接使用mysql://schema接口获取数据库结构
                    schema_response = await self.session.read_resource("mysql://schema")
                    if not schema_response or not schema_response.contents:
                        print("\n无法获取数据库结构信息")
                        continue
                    
                    schema_info = json.loads(schema_response.contents[0].text)
                    database_name = schema_info["database"]
                    tables_schema = schema_info["tables"]
                    
                    print(f"\n数据库名: {database_name}")
                    print("\n表结构:")
                    
                    # 显示每个表的结构
                    for table_name, columns in tables_schema.items():
                        print(f"\n表名: {table_name}")
                        print("列信息:")
                        for column in columns:
                            print(f"  - {column['name']} ({column['type']})")
                            if column['key'] == 'PRI':
                                print("    主键")
                            if column['null'] == 'NO':
                                print("    非空")
                            if column['default']:
                                print(f"    默认值: {column['default']}")
                            if column['extra']:
                                print(f"    额外信息: {column['extra']}")
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