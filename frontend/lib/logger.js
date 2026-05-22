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

const logger = {
  log: isDev ? console.log.bind(console) : noop,
  info: isDev ? console.info.bind(console) : noop,
  warn: isDev ? console.warn.bind(console) : noop,
  error: isDev
    ? console.error.bind(console)
    : (...args) => {
        // В проде ошибки можно прокинуть в Sentry/аналог:
        // if (typeof window !== "undefined" && window.Sentry) {
        //   window.Sentry.captureException(args[args.length - 1]);
        // }
      },
};

export default logger;
