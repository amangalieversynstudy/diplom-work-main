// Проверка словарей: у каждого ключа есть перевод на оба языка.
//
//   node scripts/check-i18n.js
//
// Словари лежат в frontend/dictionaries/ как ES-модули без "type": "module",
// поэтому Node не может подключить их напрямую: копируем во временную папку с
// расширением .mjs и импортируем оттуда. Код выхода 1, если наборы ключей разные.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const DIR = path.join(__dirname, "..", "frontend", "dictionaries");

function keys(obj, prefix = "") {
  return Object.entries(obj).flatMap(([key, value]) =>
    value && typeof value === "object" && !Array.isArray(value)
      ? keys(value, `${prefix}${key}.`)
      : [`${prefix}${key}`]
  );
}

async function load(name) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "i18n-"));
  const target = path.join(tmp, `${name}.mjs`);
  fs.copyFileSync(path.join(DIR, `${name}.js`), target);
  const mod = await import(pathToFileURL(target).href);
  return mod[name] ?? mod.default;
}

(async () => {
  const [ru, en] = [await load("ru"), await load("en")];
  const ruKeys = new Set(keys(ru));
  const enKeys = new Set(keys(en));
  const onlyRu = [...ruKeys].filter((key) => !enKeys.has(key));
  const onlyEn = [...enKeys].filter((key) => !ruKeys.has(key));

  console.log(`ru: ${ruKeys.size} ключей, en: ${enKeys.size} ключей`);
  if (onlyRu.length) console.error("Нет в en.js:\n  " + onlyRu.join("\n  "));
  if (onlyEn.length) console.error("Нет в ru.js:\n  " + onlyEn.join("\n  "));
  process.exit(onlyRu.length || onlyEn.length ? 1 : 0);
})();
