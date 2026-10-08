import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = os.environ.get("MCP_PORT", "8000")
    url = f"http://{host}:{port}/mcp"

    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            results = await session.initialize()
            print("================MCP connected.=============")
            print("Server:")
            print(results.serverInfo)
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"tool name:{tool.name}")

            response = await session.call_tool("start_fdtd", {})
            print("================Call start_fdtd=============")
            print(response)
            if response.content:
                print("============response.content=============")
                print(response.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())