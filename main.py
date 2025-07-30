#!/usr/bin/env python3
"""
Code Retrieval System - FastMCP Server Entry Point

A comprehensive code retrieval system that combines vector search with graph-based 
relationships for intelligent code analysis and search, implemented as an MCP server.
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import settings
from src.mcp.server import CodeRetrievalMCP
from src.utils.logger import app_logger


def main():
    """Main entry point for the MCP server."""
    parser = argparse.ArgumentParser(description="Code Retrieval System - MCP Server")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport")
    parser.add_argument("--http", action="store_true", help="Use HTTP transport")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP/SSE transport")
    parser.add_argument("--host", default="localhost", help="Host for HTTP/SSE transport")
    parser.add_argument("--log-level", default=settings.log_level, help="Log level")
    
    args = parser.parse_args()
    
    app_logger.info(f"Starting Code Retrieval MCP Server")
    
    # Determine transport type
    if args.stdio:
        transport = "stdio"
    elif args.http:
        transport = "http"
    else:
        transport = "sse"  # Default
    
    app_logger.info(f"Transport: {transport}")
    app_logger.info(f"Embedding provider: OpenAI (Milvus compatibility)")
    app_logger.info(f"Supported extensions: {settings.supported_extensions}")
    
    try:
        # Initialize MCP server
        mcp_server = CodeRetrievalMCP()
        server = mcp_server.get_server()
        
        if args.stdio:
            # Use stdio transport
            app_logger.info("Using stdio transport")
            asyncio.run(server.run(transport="stdio"))
        elif args.http:
            # Use HTTP transport
            app_logger.info(f"Using HTTP transport on {args.host}:{args.port}")
            asyncio.run(server.run(transport="http", host=args.host, port=args.port))
        else:
            # Use SSE transport (default)
            app_logger.info(f"Using SSE transport on {args.host}:{args.port}")
            app_logger.info("SSE transport not directly supported, using HTTP transport")
            asyncio.run(server.run(transport="http", host=args.host, port=args.port))
            
    except KeyboardInterrupt:
        app_logger.info("Shutting down...")
    except Exception as e:
        app_logger.error(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()