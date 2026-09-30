/**
 * Универсальный логер, который шумит только в dev.
 * В production молчит, чтобы не засорять консоль пользователю
 * и не утекали внутренние ошибки.
 *
 * Использование:
 *   import logger from "../lib/logger";
 *   logger.log("...");
 *   logger.warn("...");
 *   logger.error("Ошибка сервера:", err);
 *
 * Если позже подключим Sentry — sentry.captureException можно
 * вызвать здесь же, в проде, не меняя места вызова.
 */

const isDev =
  typeof process !== "undefined" &&
  process.env?.NODE_ENV !== "production";

const noop = () => {};

/* eslint-disable no-console -- единственное место, где консоль разрешена: остальной код зовёт logger */
const logger = {
  log: isDev ? console.log.bind(console) : noop,
  info: isDev ? console.info.bind(console) : noop,
  warn: isDev ? console.warn.bind(console) : noop,
  // В проде ошибки можно прокинуть в Sentry/аналог (window.Sentry.captureException), не меняя места вызова.
  error: isDev ? console.error.bind(console) : noop,
};
/* eslint-enable no-console */

export default logger;
