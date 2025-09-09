"""MCP Gmail client - Gmail integration for LLMs via Model Context Protocol using Gemini API."""

import json
import sys
import asyncio
import subprocess
import time
from typing import Optional
from contextlib import AsyncExitStack
import requests
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client  
from datetime import timedelta

tools = []  # Global list of tools available from the server
GEMINI_API_KEY = "AIzaSyBiYZTiScAfWZNkq0D_FllfhaF7Kw3GBNs"  # <-- Replace with your actual key
GEMINI_MODEL = "gemini-2.0-flash"

import socket
import time
import subprocess

def wait_for_server(host="127.0.0.1", port=8000, timeout=15):
    """Wait until a TCP port is open or timeout"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"Server {host}:{port} not ready after {timeout} seconds")


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.http_client = None

    async def connect_to_server(self, server_url: str):
        """
        Connect to an MCP server via HTTP streaming.
        """
        self.http_client = await self.exit_stack.enter_async_context(
            streamablehttp_client(server_url)
        )
        recv_stream, send_stream, _ = self.http_client  # ignore the callback

        self.session = await self.exit_stack.enter_async_context(
            ClientSession(
                recv_stream,
                send_stream,
                read_timeout_seconds=timedelta(seconds=30)
            )
        )

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        global tools
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    def gemini_query(self, prompt: str) -> str:
        """
        Call Gemini API to process a query and get a response as a string.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": GEMINI_API_KEY
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        # Safe extraction of text
        try:
            candidate = data.get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            text_output = " ".join([p.get("text", "") for p in parts])
            return text_output.strip()
        except Exception as e:
            return f"Error extracting text from Gemini response: {str(e)}"

    async def process_query(self, query: str) -> str:
        """Process a user query by selecting and invoking the appropriate tool."""
        available_tools = [tool.name for tool in tools]
        print(f"\nProcessing query: {query}")

        instruction = (
            f"User asked: {query}\n"
            f"Available tools: {available_tools}\n\n"
            "IMPORTANT:\n"
            "- Always respond with exactly this format: tool_name → {args}\n"
            "- Do NOT add extra text.\n\n"
            "Schema:\n"
            "1. query_emails expects: { \"query\": { \"<Gmail search string, e.g. 'is:unread' or 'is:read'>\" \"to\": string, \"from\": string, ... } }\n"
            "2. search_emails expects: { \"query\": \"<Gmail search string>\" }\n Examples: {\"query\": \"from:xyz@gmail.com\"}, {\"query\": \"subject:invoice\"}\n"
            "3. get_emails expects: { \"message_ids\": [\"id1\", \"id2\", ...] }\n"
            "4. send_email expects: { \"to\": string, \"subject\": string, \"body\": string, \"cc\": string?, \"bcc\": string? }\n\n"
            "RULE: Always prefer query_emails unless user explicitly asks for raw Gmail search syntax.\n"
            "If no tool matches, answer in plain natural language.\n"
        )


        tool_candidate = self.gemini_query(instruction).strip().strip('"').strip("'")
        print(f"\nGemini output: {tool_candidate}")

        if "{" in tool_candidate and "}" in tool_candidate:
            try:
                tool_name, args = tool_candidate.split("→", 1)
                tool_name = tool_name.strip().strip('"').strip("'")
                print(f"🔧 Tool parsed: {tool_name}")
                print(f"📦 Suggested args: {args.strip()}")
            except ValueError:
                # no "→", just fallback to plain tool name
                tool_name = tool_candidate.strip().strip('"').strip("'")
                args = "{}"
                print(f"🔧 Tool parsed: {tool_name}")
        else:
            tool_name = tool_candidate.strip().strip('"').strip("'")
            args = "{}"
            print(f"🔧 Tool parsed: {tool_name}")

        if tool_name in available_tools:
            try:
                parsed_args = json.loads(args)
            except json.JSONDecodeError:
                print("⚠️ Could not parse args JSON, using empty dict")
                parsed_args = {}

            # Special case for query_emails (expects {"query": {...}})
            if tool_name == "query_emails":
                if isinstance(parsed_args.get("query"), dict):
                # Convert dict → Gmail query string
                # Example: {"is:unread": True, "from": "abc"} → "is:unread from:abc"
                    q_parts = []
                    for k, v in parsed_args["query"].items():
                        if isinstance(v, bool):
                            if v:  # only include if True
                                q_parts.append(k)
                        else:
                            if k == "labelIds":
                                q_parts.append(f"in:{v.lower()}")
                            else:
                                    q_parts.append(f"{k}:{v}")
                    parsed_args["query"] = " ".join(q_parts)

            if tool_name == "get_emails":      
                if isinstance(parsed_args.get("message_ids"), str):
                    parsed_args["message_ids"] = [parsed_args["message_ids"]]

            result = await self.session.call_tool(tool_name, parsed_args)
            return f"Tool {tool_name} output: {result.content}"
        else:
            return tool_candidate

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
    # Step 1: Start the server automatically
    print("Starting Gmail MCP server...")
    server_proc = subprocess.Popen(
        ["python", "-m", "mcp_gmail.server"],
        # stdout=subprocess.PIPE,
        # stderr=subprocess.PIPE
    )
    
    # Wait until server is ready
    wait_for_server("127.0.0.1", 8000,timeout=60)
    print("Server is up, connecting client...")

    server_url = "http://127.0.0.1:8000/mcp"

    client = MCPClient()
    try:
        await client.connect_to_server(server_url)
        await client.chat_loop()
    finally:
        await client.cleanup()
        # Kill the server on exit
        print("\nShutting down Gmail MCP server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()


if __name__ == "__main__":
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nClient exited gracefully.")
