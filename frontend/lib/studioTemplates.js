// «Быстрый старт по шаблону» в Студии: готовые пресеты для курса, раздела, миссии и шага.
// Клик по карточке заполняет форму, сервер проверяет её как обычно (backend/game/studio.py).
// Тексты — содержание курса на русском, как и встроенные курсы; подписи карточек — на двух языках.
// Каждая задача с кодом проверена эталонным решением: оно печатает ровно expected_output и проходит
// скрытую проверку (tests/studioTemplates.test.js сверяет структуру, решения записаны в reference).

export const localized = (value, language) =>
  value && typeof value === "object" ? value[language] || value.ru || value.en || "" : value || "";

export const COURSE_TEMPLATES = [
  {
    id: "basics",
    label: { ru: "Python с нуля", en: "Python from scratch" },
    hint: { ru: "Вводный курс для новичков", en: "An intro course for beginners" },
    form: {
      title_ru: "Python с нуля: первые программы",
      title_en: "Python from scratch: first programs",
      description_ru:
        "Для кого: ученики, которые ещё не программировали.\n" +
        "Что освоят: переменные, ввод и вывод, условия, циклы.\n" +
        "Как устроен курс: 4 главы по 2–3 миссии; в каждой миссии теория, квиз и задача с кодом.\n" +
        "Итог: своя программа «Калькулятор героя».",
    },
  },
  {
    id: "practice",
    label: { ru: "Практикум", en: "Practice set" },
    hint: { ru: "Задачи на условия и циклы", en: "Tasks on conditions and loops" },
    form: {
      title_ru: "Практикум: условия и циклы",
      title_en: "Practice: conditions and loops",
      description_ru:
        "Для кого: группа, которая уже прошла вводную тему.\n" +
        "Что даёт: задачи с автопроверкой и личными вариантами — ответ соседа не подойдёт.\n" +
        "Формат: короткая теория → задача → подсказки по шагам, если ученик застрял.",
    },
  },
  {
    id: "exam",
    label: { ru: "Подготовка к контрольной", en: "Test preparation" },
    hint: { ru: "Повторение и проверка", en: "Revision and checks" },
    form: {
      title_ru: "Подготовка к контрольной",
      title_en: "Test preparation",
      description_ru:
        "Повторение перед контрольной: квизы на понимание кода и короткие задачи.\n" +
        "Кабинет покажет, кто и на каком шаге застрял, — их стоит разобрать на занятии.",
    },
  },
  {
    id: "project",
    label: { ru: "Мини-проект", en: "Mini project" },
    hint: { ru: "Текстовая игра по шагам", en: "A text game step by step" },
    form: {
      title_ru: "Мини-проект: текстовая игра",
      title_en: "Mini project: a text game",
      description_ru:
        "Проектный курс: ученики шаг за шагом собирают текстовую RPG — герой, инвентарь, бой.\n" +
        "Каждая миссия добавляет в игру одну механику, к концу курса у каждого своя игра.",
    },
  },
];

export const SECTION_TEMPLATES = [
  {
    id: "intro",
    label: { ru: "Знакомство", en: "Getting started" },
    hint: { ru: "Первая глава курса", en: "The first chapter" },
    form: { title_ru: "Глава 1. Знакомство", title_en: "Chapter 1. Getting started" },
  },
  {
    id: "practice",
    label: { ru: "Практикум", en: "Practice" },
    hint: { ru: "Задачи на закрепление", en: "Tasks to practise" },
    form: { title_ru: "Практикум", title_en: "Practice" },
  },
  {
    id: "checkpoint",
    label: { ru: "Контрольная точка", en: "Checkpoint" },
    hint: { ru: "Итог главы", en: "End of a chapter" },
    form: { title_ru: "Контрольная точка", title_en: "Checkpoint" },
  },
];

export const MISSION_TEMPLATES = [
  {
    id: "warmup",
    label: { ru: "Разминка", en: "Warm-up" },
    hint: { ru: "Переменные и вывод · 30 XP", en: "Variables and output · 30 XP" },
    form: { title_ru: "Разминка: переменные и вывод", title_en: "Warm-up: variables and output", xp_reward: 30 },
  },
  {
    id: "conditions",
    label: { ru: "Условия", en: "Conditions" },
    hint: { ru: "if / else · 50 XP", en: "if / else · 50 XP" },
    form: { title_ru: "Условия: если… иначе", title_en: "Conditions: if… else", xp_reward: 50 },
  },
  {
    id: "loops",
    label: { ru: "Циклы", en: "Loops" },
    hint: { ru: "for и while · 60 XP", en: "for and while · 60 XP" },
    form: { title_ru: "Циклы: повторяем действия", title_en: "Loops: repeat actions", xp_reward: 60 },
  },
  {
    id: "boss",
    label: { ru: "Босс-миссия", en: "Boss mission" },
    hint: { ru: "Итоговая задача · 100 XP", en: "Final task · 100 XP" },
    form: { title_ru: "Босс-миссия: итоговая задача", title_en: "Boss mission: final task", xp_reward: 100 },
  },
];

const SPELL_VARIANTS = [
  { vars: { name: "Ари", n: 3, power: 7, total: 21 } },
  { vars: { name: "Мила", n: 4, power: 6, total: 24 } },
  { vars: { name: "Тимур", n: 5, power: 9, total: 45 } },
  { vars: { name: "Зарина", n: 6, power: 8, total: 48 } },
];

// form — поля формы шага в StudioTasks.jsx; reference — эталонное решение для проверки шаблона (не уходит на сервер)
export const STEP_TEMPLATES = [
  {
    id: "theory",
    label: { ru: "Теория", en: "Theory" },
    hint: { ru: "История с примером кода", en: "A story with a code sample" },
    form: {
      task_type: "story",
      title_ru: "Теория: условие if",
      title_en: "Theory: the if statement",
      body_ru:
        "<p>Иногда программа должна выбирать. Для этого есть <code>if</code>:</p>" +
        "<pre><code>hp = 30\nif hp &lt; 50:\n    print(\"Нужно лечение\")\nelse:\n    print(\"Можно в бой\")</code></pre>" +
        "<p>Python проверяет условие после <code>if</code>. Если оно истинно, выполняется блок с отступом, " +
        "иначе — блок после <code>else</code>.</p>",
      body_en:
        "<p>Sometimes a program has to choose. That is what <code>if</code> is for:</p>" +
        "<pre><code>hp = 30\nif hp &lt; 50:\n    print(\"Heal first\")\nelse:\n    print(\"Ready to fight\")</code></pre>" +
        "<p>Python checks the condition after <code>if</code>: the indented block runs when it is true, " +
        "the block after <code>else</code> otherwise.</p>",
      xp_reward: 5,
      estimated_minutes: 3,
    },
  },
  {
    id: "quiz",
    label: { ru: "Квиз", en: "Quiz" },
    hint: { ru: "Проверка понимания кода", en: "Check code understanding" },
    form: {
      task_type: "quiz",
      title_ru: "Квиз: сколько строк выведет цикл?",
      title_en: "Quiz: how many lines does the loop print?",
      body_ru: "<pre><code>for i in range(3):\n    print(i)</code></pre><p>Сколько строк выведет программа?</p>",
      body_en: "<pre><code>for i in range(3):\n    print(i)</code></pre><p>How many lines does the program print?</p>",
      xp_reward: 10,
      estimated_minutes: 2,
      options: ["3", "2", "4", "Ни одной"],
      correct: 0,
    },
  },
  {
    id: "code",
    label: { ru: "Задача с кодом", en: "Code task" },
    hint: { ru: "Автопроверка и подсказки", en: "Auto-check and hints" },
    form: {
      task_type: "code",
      title_ru: "Задача: сумма покупок",
      title_en: "Task: shopping total",
      body_ru:
        "<p>В списке <code>prices</code> лежат цены покупок. Посчитайте их сумму в переменной " +
        "<code>total</code> с помощью цикла <code>for</code>.</p>" +
        "<p>Например, для цен 10, 20 и 5 программа выведет <code>Итого: 35</code>.</p>",
      body_en:
        "<p>The list <code>prices</code> holds the prices of purchases. Add them up in the variable " +
        "<code>total</code> with a <code>for</code> loop.</p><p>For prices 10, 20 and 5 the program prints " +
        "<code>Итого: 35</code>.</p>",
      xp_reward: 20,
      estimated_minutes: 7,
      starter: "prices = [120, 80, 150]\ntotal = 0\n# пройдите по списку и прибавьте каждую цену к total\n\nprint(\"Итого:\", total)\n",
      expected_output: "Итого: 350",
      hidden_check: "assert total == sum(prices), \"Сумма должна быть в переменной total\"",
      hints_ru: "Цикл for перебирает элементы списка: for price in prices:\n\nВнутри цикла увеличивайте total: total += price",
      hints_en: "A for loop goes over the list: for price in prices:\n\nInside the loop add to total: total += price",
      skeleton_ru: "prices = [120, 80, 150]\ntotal = 0\nfor price in prices:\n    total += ...\nprint(\"Итого:\", total)\n",
      skeleton_en: "prices = [120, 80, 150]\ntotal = 0\nfor price in prices:\n    total += ...\nprint(\"Итого:\", total)\n",
      not_yet: ["def", "lambda", "comprehension"],
      variants_json: "",
    },
    reference: "prices = [120, 80, 150]\ntotal = 0\nfor price in prices:\n    total += price\nprint(\"Итого:\", total)\n",
  },
  {
    id: "variants",
    label: { ru: "Личные варианты", en: "Personal variants" },
    hint: { ru: "У каждого свои числа: не списать", en: "Own numbers for each: no copying" },
    form: {
      task_type: "code",
      title_ru: "Задача: сила заклинаний",
      title_en: "Task: spell power",
      body_ru:
        "<p>Маг <strong>{{name}}</strong> знает {{n}} заклинаний, каждое силой {{power}}. Посчитайте общую силу " +
        "в переменной <code>total</code> и выведите имя мага и общую силу через двоеточие.</p>" +
        "<p>Пример формата для другого мага: <code>Лея: 10</code>. У каждого ученика свои числа, поэтому чужой " +
        "ответ не подойдёт.</p>",
      body_en:
        "<p>The mage <strong>{{name}}</strong> knows {{n}} spells of power {{power}} each. Compute the total power " +
        "in <code>total</code> and print the name and the total separated by a colon, e.g. <code>Leia: 10</code>. " +
        "Every learner gets other numbers.</p>",
      xp_reward: 25,
      estimated_minutes: 6,
      starter: "name = \"{{name}}\"\nn = {{n}}\npower = {{power}}\ntotal = 0  # посчитайте общую силу\n\nprint(name + \":\", total)\n",
      expected_output: "{{name}}: {{total}}",
      hidden_check:
        "assert total == n * power, \"Общая сила должна быть в переменной total\"\n" +
        "assert (n, power) == ({{n}}, {{power}}), \"Не меняйте исходные числа\"",
      hints_ru: "Общая сила = число заклинаний × сила одного: n * power\n\nСохраните результат в total, строку print менять не нужно.",
      hints_en: "Total power = number of spells × power of one: n * power\n\nStore it in total; the print line can stay.",
      skeleton_ru: "name = \"{{name}}\"\nn = {{n}}\npower = {{power}}\ntotal = ... * ...\nprint(name + \":\", total)\n",
      skeleton_en: "name = \"{{name}}\"\nn = {{n}}\npower = {{power}}\ntotal = ... * ...\nprint(name + \":\", total)\n",
      not_yet: ["def", "lambda", "comprehension", "import", "class"],
      variants_json: JSON.stringify(SPELL_VARIANTS, null, 2),
    },
    reference: "name = \"{{name}}\"\nn = {{n}}\npower = {{power}}\ntotal = n * power\nprint(name + \":\", total)\n",
  },
];
