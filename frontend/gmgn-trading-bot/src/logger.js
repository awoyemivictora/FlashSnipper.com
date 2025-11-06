import { createLogger, transports, format } from 'winston';
import path from 'path';

// Create a logger instance
const logger = createLogger({
  level: 'info',
  format: format.combine(
    format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    format.printf(({ timestamp, level, message }) => `${timestamp} [${level.toUpperCase()}] ${message}`)
  ),
  transports: [
    new transports.Console(),
    new transports.File({ filename: path.join(process.cwd(), 'bot.log'), level: 'info' }),
    new transports.File({ filename: path.join(process.cwd(), 'bot-error.log'), level: 'error' })
  ]
});

export default logger;
