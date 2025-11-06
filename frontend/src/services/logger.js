// logger.js (or wherever you manage your frontend logging)

// Function to get a formatted timestamp
const getTimestamp = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
};

// Create a simple logger object using console.log
const logger = {
  info: (message, ...args) => {
    // Only log info messages if the level is appropriate (you could add a global level setting)
    console.info(`${getTimestamp()} [INFO] ${message}`, ...args);
  },
  error: (message, ...args) => {
    console.error(`${getTimestamp()} [ERROR] ${message}`, ...args);
  },
  warn: (message, ...args) => {
    console.warn(`${getTimestamp()} [WARN] ${message}`, ...args);
  },
  debug: (message, ...args) => {
    // Debug messages might be conditionally logged in a real app based on environment
    console.debug(`${getTimestamp()} [DEBUG] ${message}`, ...args);
  },
  // You can add more methods as needed (e.g., verbose, silly)
};

export default logger;
