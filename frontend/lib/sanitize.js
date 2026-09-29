import DOMPurify from "dompurify";

// Тексты заданий — HTML, который пишет преподаватель. Разметка ограничена тем,
// что нужно для урока: абзацы, списки, код, заголовки, ссылки и таблицы. Скрипты,
// обработчики событий, стили, формы, iframe и картинки (пиксели слежения) не
// проходят, а ссылки открываются только по http(s) и mailto.
export const ALLOWED_TAGS = [
  "p", "br", "hr", "strong", "b", "em", "i", "u", "s", "sub", "sup", "small",
  "code", "pre", "kbd", "samp", "blockquote",
  "h2", "h3", "h4", "ul", "ol", "li", "a",
  "table", "thead", "tbody", "tr", "th", "td",
];
export const ALLOWED_ATTR = ["href", "title", "colspan", "rowspan"];

const CONFIG = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  ALLOW_DATA_ATTR: false,
  ALLOW_ARIA_ATTR: false,
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
};

let hooked = new WeakSet();

function purifierFor(win) {
  const purify = DOMPurify(win);
  if (!hooked.has(purify)) {
    hooked.add(purify);
    // внешняя ссылка не должна получать доступ к странице урока
    purify.addHook("afterSanitizeAttributes", (node) => {
      if (node.tagName === "A" && node.hasAttribute("href")) {
        node.setAttribute("target", "_blank");
        node.setAttribute("rel", "noopener noreferrer");
      }
    });
  }
  return purify;
}

const purifiers = new WeakMap();

/**
 * Безопасный HTML для dangerouslySetInnerHTML. На сервере (нет DOM) возвращает
 * пустую строку: страница урока рисует текст только после загрузки в браузере.
 * `win` нужен тестам (jsdom); в браузере берётся window.
 */
export function sanitizeHtml(html, win = typeof window !== "undefined" ? window : null) {
  if (!html || !win) return "";
  if (!purifiers.has(win)) purifiers.set(win, purifierFor(win));
  return purifiers.get(win).sanitize(String(html), CONFIG);
}
