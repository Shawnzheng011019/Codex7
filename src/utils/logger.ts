import winston from 'winston';
import { Logger, LogLevel } from '../types/index.js';

export function createLogger(level: LogLevel = 'warn'): Logger {
  const winstonLogger = winston.createLogger({
    level,
    format: winston.format.combine(
      winston.format.timestamp(),
      winston.format.colorize(),
      winston.format.printf(({ timestamp, level, message, ...meta }) => {
        let result = `${timestamp} [${level}]: ${message}`;
        if (Object.keys(meta).length > 0) {
          result += ` ${JSON.stringify(meta)}`;
        }
        return result;
      })
    ),
    transports: [
      // Use stderr for console output to avoid polluting stdout JSON-RPC messages
      new winston.transports.Console({ 
        stderrLevels: ['error', 'warn', 'info', 'debug'],
        consoleWarnLevels: [],
        handleExceptions: true,
        handleRejections: true,
        silent: false
      }),
      new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
      new winston.transports.File({ filename: 'logs/combined.log' }),
    ],
    exitOnError: false,
  });

  return {
    error: (message: string, error?: any) => {
      winstonLogger.error(message, error);
    },
    warn: (message: string, data?: any) => {
      winstonLogger.warn(message, data);
    },
    info: (message: string, data?: any) => {
      winstonLogger.info(message, data);
    },
    debug: (message: string, data?: any) => {
      winstonLogger.debug(message, data);
    },
  };
}

export const logger = createLogger(); 