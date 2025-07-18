/**
 * Codex7 - Local Codebase RAG System
 * 
 * An intelligent RAG system for analyzing and searching local codebases.
 * Provides semantic search, code analysis, and MCP integration for AI IDEs.
 */

import { MCPServer } from './mcp/server.js';
import { logger } from './utils/logger.js';

interface JSONRPCRequest {
  jsonrpc: '2.0';
  id?: string | number;
  method: string;
  params?: any;
}

interface JSONRPCResponse {
  jsonrpc: '2.0';
  id: string | number;
  result?: any;
  error?: {
    code: number;
    message: string;
    data?: any;
  };
}

let isClientConnected = true;
let mcpServer: MCPServer | null = null;

async function main() {
  try {
    // Ensure all console output goes to stderr to avoid contaminating stdout JSON-RPC
    console.log = (...args) => process.stderr.write(args.join(' ') + '\n');
    console.error = (...args) => process.stderr.write(args.join(' ') + '\n');
    console.warn = (...args) => process.stderr.write(args.join(' ') + '\n');
    console.info = (...args) => process.stderr.write(args.join(' ') + '\n');
    
    logger.info('Starting Codex7 Local Codebase RAG System...');
    
    // Initialize the MCP server
    mcpServer = new MCPServer();
    
    // Start listening for MCP requests via stdin/stdout
    let buffer = '';
    
    process.stdin.on('data', async (data) => {
      if (!isClientConnected) return;
      
      try {
        buffer += data.toString();
        
        // Process all complete JSON objects in the buffer
        while (buffer.length > 0) {
          const trimmed = buffer.trimStart();
          if (trimmed.length === 0) {
            buffer = '';
            break;
          }
          
          let request: JSONRPCRequest | null = null;
          let parseError: Error | null = null;
          
          // Try to parse JSON objects from the buffer
          try {
            // Find the first complete JSON object by looking for balanced braces
            let braceCount = 0;
            let inString = false;
            let escaped = false;
            let jsonEnd = -1;
            
            for (let i = 0; i < trimmed.length; i++) {
              const char = trimmed[i];
              
              if (inString) {
                if (escaped) {
                  escaped = false;
                } else if (char === '\\') {
                  escaped = true;
                } else if (char === '"') {
                  inString = false;
                }
              } else {
                if (char === '"') {
                  inString = true;
                } else if (char === '{') {
                  braceCount++;
                } else if (char === '}') {
                  braceCount--;
                  if (braceCount === 0) {
                    jsonEnd = i + 1;
                    break;
                  }
                }
              }
            }
            
            if (jsonEnd === -1) {
              // Incomplete JSON, wait for more data
              break;
            }
            
            const jsonString = trimmed.substring(0, jsonEnd).trim();
            if (jsonString) {
              request = JSON.parse(jsonString);
              buffer = trimmed.substring(jsonEnd);
            }
          } catch (err) {
            parseError = err instanceof Error ? err : new Error(String(err));
          }
          
          if (parseError) {
            if (!isClientConnected) return;
            const errorResponse: JSONRPCResponse = {
              jsonrpc: '2.0',
              id: 0,
              error: {
                code: -32700,
                message: 'Parse error',
                data: parseError.message
              }
            };
            process.stdout.write(JSON.stringify(errorResponse) + '\n');
            buffer = ''; // Clear buffer on parse error
            return;
          }
          
          if (!request) {
            break; // No more complete JSON objects
          }

          // Validate JSON-RPC format
          if (request.jsonrpc !== '2.0') {
            if (!isClientConnected) return;
            const errorResponse: JSONRPCResponse = {
              jsonrpc: '2.0',
              id: request.id !== undefined && request.id !== null ? request.id : 0,
              error: {
                code: -32600,
                message: 'Invalid Request',
                data: 'JSON-RPC version must be 2.0'
              }
            };
            process.stdout.write(JSON.stringify(errorResponse) + '\n');
            continue;
          }

          // Validate required fields
          if (!request.method || typeof request.method !== 'string') {
            if (!isClientConnected) return;
            const errorResponse: JSONRPCResponse = {
              jsonrpc: '2.0',
              id: request.id !== undefined && request.id !== null ? request.id : 0,
              error: {
                code: -32600,
                message: 'Invalid Request',
                data: 'Method field is required and must be a string'
              }
            };
            process.stdout.write(JSON.stringify(errorResponse) + '\n');
            continue;
          }

          // Forward the entire JSON-RPC request to the MCP server so it can
          // construct a proper JSON-RPC response. The server already returns
          // a correctly formatted JSON-RPC envelope, so we can write it
          // directly to stdout without additional wrapping.
          if (!mcpServer) {
            throw new Error('MCP server not initialized');
          }

          const mcpResponse = await mcpServer.handleRequest(request);

          if (!isClientConnected || mcpResponse === undefined) continue;

          // Ensure response is clean before sending
          const cleanedResponse = JSON.parse(JSON.stringify(mcpResponse));

          // Write the server's response (already JSON-RPC formatted)
          process.stdout.write(JSON.stringify(cleanedResponse) + '\n');
        }
        
      } catch (error) {
        if (!isClientConnected) return;
        
        logger.error('Error processing MCP request:', error);
        
        const errorResponse: JSONRPCResponse = {
          jsonrpc: '2.0',
          id: 0,
          error: {
            code: -32603,
            message: 'Internal error',
            data: error instanceof Error ? error.message : String(error)
          }
        };
        
        process.stdout.write(JSON.stringify(errorResponse) + '\n');
        buffer = ''; // Clear buffer on error
      }
    });
    
    // Handle client disconnection events
    process.stdin.on('end', () => {
      logger.info('Client disconnected (stdin end)');
      isClientConnected = false;
      gracefulShutdown();
    });
    
    process.stdin.on('close', () => {
      logger.info('Client connection closed (stdin close)');
      isClientConnected = false;
      gracefulShutdown();
    });
    
    process.stdin.on('error', (error) => {
      logger.error('Client connection error:', error);
      isClientConnected = false;
      gracefulShutdown();
    });
    
    // Handle process termination signals
    process.on('SIGINT', () => {
      logger.info('Received SIGINT, shutting down gracefully...');
      isClientConnected = false;
      gracefulShutdown();
    });
    
    process.on('SIGTERM', () => {
      logger.info('Received SIGTERM, shutting down gracefully...');
      isClientConnected = false;
      gracefulShutdown();
    });
    
    // Handle uncaught exceptions
    process.on('uncaughtException', (error) => {
      logger.error('Uncaught exception:', error);
      isClientConnected = false;
      gracefulShutdown();
    });
    
    // Handle unhandled promise rejections
    process.on('unhandledRejection', (reason) => {
      logger.error('Unhandled rejection at promise:', reason);
      isClientConnected = false;
      gracefulShutdown();
    });
    
    logger.info('Codex7 Local Codebase RAG System is ready and listening for MCP requests');
    
    // Keep the process alive and check connection status
    process.stdin.setEncoding('utf8');
    process.stdin.resume();
    
    // Periodically check if client is still connected
    const connectionChecker = setInterval(() => {
      if (!isClientConnected) {
        clearInterval(connectionChecker);
        return;
      }
      
      // Send a heartbeat ping if no activity for extended periods
      // This helps detect broken connections early
      logger.debug('Connection check: Client still connected');
    }, 30000); // Check every 30 seconds
    
  } catch (error) {
    logger.error('Failed to start Codex7 Local Codebase RAG System:', error);
    process.exit(1);
  }
}

async function gracefulShutdown() {
  logger.info('Initiating graceful shutdown...');
  
  try {
    // Cleanup MCP server resources
    if (mcpServer) {
      await mcpServer.cleanup();
    }
  } catch (error) {
    logger.error('Error during cleanup:', error);
  }
  
  // Give some time for cleanup
  setTimeout(() => {
    logger.info('Codex7 Local Codebase RAG System shutdown complete');
    process.exit(0);
  }, 1000);
}

// Start the application
main().catch((error) => {
  logger.error('Unhandled error in main:', error);
  process.exit(1);
}); 