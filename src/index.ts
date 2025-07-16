import { WebServer } from './server/app.js';
import { logger } from './utils/logger.js';

async function main() {
  try {
    logger.info('Starting Codex7 RAG System...');
    
    const server = new WebServer();
    await server.start();
    
    // Graceful shutdown
    process.on('SIGINT', async () => {
      logger.info('Received SIGINT, shutting down gracefully...');
      await server.stop();
      process.exit(0);
    });
    
    process.on('SIGTERM', async () => {
      logger.info('Received SIGTERM, shutting down gracefully...');
      await server.stop();
      process.exit(0);
    });
    
  } catch (error) {
    logger.error('Failed to start Codex7 RAG System:', error);
    process.exit(1);
  }
}

main().catch(error => {
  logger.error('Unhandled error:', error);
  process.exit(1);
}); 