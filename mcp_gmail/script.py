# mcp_gmail/script.py
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from server import mcp  # Import your existing MCP instance

os.environ["DANGEROUSLY_OMIT_AUTH"] = "true"

app = FastAPI()

# Health check
@app.get("/health")
async def health_check():
    return JSONResponse({"status": "healthy", "service": "gmail-mcp"})

# Streamable HTTP endpoint
session_manager = StreamableHTTPSessionManager(mcp)
app.add_route("/sse", session_manager.sse, methods=["GET", "POST"])

if __name__ == "__main__":
    uvicorn.run("script:app", host="0.0.0.0", port=3001, reload=True)
