#!/usr/bin/env python3
"""
Test script for Context7 MCP integration.

Usage:
    python scripts/test_context7.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.mcp.config import MCPServerConfig
from core.mcp.client import MCPClient
from core.mcp.manager import MCPClientManager
from tools.mcp_ops import MCPToolFactory
from tools.base import ToolRegistry


async def test_context7_connection():
    """Test basic connection to Context7."""
    print("=" * 60)
    print("Testing Context7 MCP Connection")
    print("=" * 60)
    
    config = MCPServerConfig(
        name="context7",
        transport="http",
        url="https://mcp.context7.com/mcp",
        request_timeout=60,
    )
    
    client = MCPClient(config)
    
    try:
        print("\n1. Connecting to Context7...")
        await client.connect()
        print(f"   ✅ Connected! Server: {client._server_info.server_info.name}")
        
        print("\n2. Listing available tools...")
        tools = await client.list_tools()
        print(f"   ✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"      - {tool.name}: {tool.description[:50]}...")
        
        print("\n3. Testing tool call (resolve-library-id)...")
        result = await client.call_tool("resolve-library-id", {
            "libraryName": "react"
        })
        if not result.is_error:
            print(f"   ✅ Success! Result preview:")
            text = result.get_text()[:300]
            print(f"      {text}...")
        else:
            print(f"   ❌ Error: {result.get_text()}")
        
        print("\n4. Testing documentation fetch...")
        result = await client.call_tool("get-library-docs", {
            "context7CompatibleLibraryID": "/facebook/react",
            "topic": "hooks",
        })
        if not result.is_error:
            print(f"   ✅ Success! Got {len(result.get_text())} chars of documentation")
            print(f"      Preview: {result.get_text()[:200]}...")
        else:
            print(f"   ❌ Error: {result.get_text()}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()
        print("\n   Disconnected.")


async def test_tool_registry_integration():
    """Test MCP tools in ToolRegistry."""
    print("\n" + "=" * 60)
    print("Testing ToolRegistry Integration")
    print("=" * 60)
    
    manager = MCPClientManager()
    manager.load_from_config()
    
    try:
        print("\n1. Connecting to MCP servers...")
        results = await manager.connect_all()
        for name, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {name}")
        
        if not any(results.values()):
            print("   No servers connected, skipping registry test")
            return
        
        print("\n2. Creating ToolRegistry with MCP tools...")
        registry = ToolRegistry()
        registry.register_defaults()
        count = await registry.register_mcp_tools(manager)
        print(f"   ✅ Registered {count} MCP tools")
        
        print("\n3. Listing all MCP tools in registry...")
        mcp_tools = registry.get_mcp_tools()
        for tool in mcp_tools:
            print(f"   - {tool.name}")
        
        print("\n4. Getting OpenAI schemas...")
        schemas = registry.get_schemas()
        mcp_schemas = [s for s in schemas if s["function"]["name"].startswith("mcp_")]
        print(f"   ✅ {len(mcp_schemas)} MCP tool schemas ready for OpenAI")
        
    finally:
        await manager.disconnect_all()


async def main():
    """Run all tests."""
    await test_context7_connection()
    await test_tool_registry_integration()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
