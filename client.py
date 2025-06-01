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
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
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