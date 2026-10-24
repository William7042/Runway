"""Connect over MCP stdio and exercise read-only Runway tools.

Run from the repo root: .venv/bin/python -m demo.mcp_smoke
Does not call approval, receipt attachment, reset, or payment tools.
"""
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def decode(result):
    if result.is_error:
        raise RuntimeError('MCP tool returned an error')
    texts = [c.text for c in result.content if c.type == 'text']
    data = json.loads('\n'.join(texts))
    if isinstance(data, dict) and data.get('error'):
        raise RuntimeError('Runway tool failed; verify approval queue availability')
    return data


async def main():
    params = StdioServerParameters(
        command=str(ROOT / '.venv/bin/python'),
        args=[str(ROOT / 'mcp_server/server.py')],
        cwd=str(ROOT),
        env={'APPROVAL_QUEUE_URL': 'http://127.0.0.1:8000', 'DRY_RUN': '1', 'RUNWAY_MODE': 'stub'},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print('Connected:', info.server_info.name)
            tools = await session.list_tools()
            print('Tools available:', len(tools.tools))
            health = decode(await session.call_tool('health', {}))
            print('Queue health:', json.dumps(health))
            pending = decode(await session.call_tool('list_proposals', {'status': 'pending'}))
            print('Pending proposals:', len(pending))
            specialists = decode(await session.call_tool('list_specialists', {}))
            print('Specialist registry:', type(specialists).__name__, 'received')
            balances = decode(await session.call_tool('get_balances', {}))
            print('Wallet snapshot:', type(balances).__name__, 'received')
            resources = await session.list_resources()
            print('Resources available:', len(resources.resources))
            prompts = await session.list_prompts()
            print('Prompts available:', len(prompts.prompts))
            print('PASS: MCP connection and read-only calls; no approval or funds moved')


if __name__ == '__main__':
    asyncio.run(main())
