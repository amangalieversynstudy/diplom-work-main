// Проверка словарей:
//   1. у каждого ключа есть перевод на оба языка;
//   2. каждый ключ, который код просит у словаря (t("..."), unit(t, lang, "...")), в словаре есть.
//
//   node scripts/check-i18n.js
//
// Вторая проверка нужна потому, что первая её не заменяет: если ключа нет сразу в обоих словарях,
// наборы ключей совпадают, а на экране вместо текста стоит сырой «analytics.units.days».
//
// Словари лежат в frontend/dictionaries/ как ES-модули без "type": "module",
// поэтому Node не может подключить их напрямую: копируем во временную папку с
// расширением .mjs и импортируем оттуда. Код выхода 1, если что-то не сошлось.
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const FRONTEND = path.join(__dirname, "..", "frontend");
const DIR = path.join(FRONTEND, "dictionaries");
const SOURCE_DIRS = ["pages", "components", "lib"];
const PLURAL_FORMS = ["one", "few", "many"];

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

function has(dictionary, dotted) {
  let node = dictionary;
  for (const part of dotted.split(".")) {
    if (node == null || typeof node !== "object" || !(part in node)) return false;
    node = node[part];
  }
  return true;
}

function sourceFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name === "node_modules" || entry.name === ".next") return [];
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(full);
    return /\.(jsx?|tsx?)$/.test(entry.name) ? [full] : [];
  });
}

// Что просит код: точные ключи, начала составных ключей (`profile.classes.${id}`) и слова с числом.
function requestedKeys() {
  const exact = [];
  const prefixes = [];
  const units = [];
  for (const dir of SOURCE_DIRS) {
    for (const file of sourceFiles(path.join(FRONTEND, dir))) {
      const source = fs.readFileSync(file, "utf8");
      const where = path.relative(FRONTEND, file);
      for (const m of source.matchAll(/(?<![\w.$])t\(\s*(["'])([^"'\n$]+?)\1/g)) exact.push([where, m[2]]);
      for (const m of source.matchAll(/(?<![\w.$])t\(\s*`([^`$\n]*)\$\{/g)) {
        const prefix = m[1].replace(/\.$/, "");
        if (prefix) prefixes.push([where, prefix]);
      }
      for (const m of source.matchAll(/\bunit\(\s*t\s*,\s*\w+\s*,\s*(["'])(\w+)\1/g)) units.push([where, m[2]]);
    }
  }
  return { exact, prefixes, units };
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

  const { exact, prefixes, units } = requestedKeys();
  const unknown = [];
  for (const [language, dictionary] of [["ru", ru], ["en", en]]) {
    for (const [where, key] of exact) if (!has(dictionary, key)) unknown.push(`${language}: ${key}  (${where})`);
    for (const [where, prefix] of prefixes) if (!has(dictionary, prefix)) unknown.push(`${language}: ${prefix}.*  (${where})`);
    for (const [where, name] of units)
      for (const form of PLURAL_FORMS)
        if (!has(dictionary, `units.${name}_${form}`)) unknown.push(`${language}: units.${name}_${form}  (${where})`);
  }
  console.log(`Ключей, которые просит код: ${exact.length + prefixes.length + units.length}`);
  if (unknown.length) console.error("Код просит ключи, которых нет в словаре:\n  " + unknown.join("\n  "));

  process.exit(onlyRu.length || onlyEn.length || unknown.length ? 1 : 0);
})();
