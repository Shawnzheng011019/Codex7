import winston from 'winston';
import { Logger, LogLevel } from '../types/index.js';

export function createLogger(level: LogLevel = 'info'): Logger {
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
      new winston.transports.Console(),
      new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
      new winston.transports.File({ filename: 'logs/combined.log' }),
    ],
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