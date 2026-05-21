// scripts/check-i18n.js
const fs = require('fs');

// Простая функция для получения всех ключей объекта рекурсивно (в виде 'nav.sanctum')
function getKeys(obj, prefix = '') {
  let keys = [];
  for (const key in obj) {
    const newKey = prefix ? `${prefix}.${key}` : key;
    if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
      keys = keys.concat(getKeys(obj[key], newKey));
    } else {
      keys.push(newKey);
    }
  }
  return keys;
}

// Загружаем словари (если используете ES Modules в Node.js, можно через import)
const { en } = require('../lib/dictionaries/en.js'); // Укажите правильный путь
const { ru } = require('../lib/dictionaries/ru.js'); // Укажите правильный путь

const enKeys = new Set(getKeys(en));
const ruKeys = new Set(getKeys(ru));

const missingInRu = [...enKeys].filter(x => !ruKeys.has(x));
const missingInEn = [...ruKeys].filter(x => !enKeys.has(x));

let hasErrors = false;

if (missingInRu.length > 0) {
  console.error('❌ Отсутствуют ключи в RU словаре:', missingInRu);
  hasErrors = true;
}

if (missingInEn.length > 0) {
  console.error('❌ Отсутствуют ключи в EN словаре:', missingInEn);
  hasErrors = true;
}

if (!hasErrors) {
  console.log('✅ Словари полностью синхронизированы!');
} else {
  process.exit(1);
}