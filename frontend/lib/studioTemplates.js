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
    hint: { ru: "Название и описание вводного курса; главы и миссии — ниже, по своим шаблонам", en: "Title and description of an intro course; add chapters and missions below" },
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
    hint: { ru: "Название и описание практикума; задачи — шаблоны шагов «Код» и «Личные варианты»", en: "Title and description of a practice set; tasks come from the code step templates" },
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
    hint: { ru: "Название и описание; квизы и задачи — по шаблонам шагов", en: "Title and description; quizzes and tasks come from the step templates" },
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
    hint: { ru: "Название и описание проекта; миссии с механиками добавьте ниже", en: "Title and description of the project; add a mission per game mechanic below" },
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
      // простой текст (lib/story.js): учителю не нужен HTML, чтобы поправить шаблон
      body_ru:
        "## Выбор в программе\nИногда программа должна выбирать. Для этого есть `if`:\n\n" +
        "```\nhp = 30\nif hp < 50:\n    print(\"Нужно лечение\")\nelse:\n    print(\"Можно в бой\")\n```\n\n" +
        "Python проверяет условие после `if`. Если оно истинно, выполняется блок с отступом, иначе — блок после `else`.\n\n" +
        "Важно: после условия ставится двоеточие, а блок внутри сдвигается на 4 пробела.",
      body_en:
        "## Choosing in a program\nSometimes a program has to choose. That is what `if` is for:\n\n" +
        "```\nhp = 30\nif hp < 50:\n    print(\"Heal first\")\nelse:\n    print(\"Ready to fight\")\n```\n\n" +
        "Python checks the condition after `if`: the indented block runs when it is true, the block after `else` otherwise.\n\n" +
        "Note: the condition ends with a colon and the block inside is indented by 4 spaces.",
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
      body_ru: "```\nfor i in range(3):\n    print(i)\n```\n\nСколько строк выведет программа?",
      body_en: "```\nfor i in range(3):\n    print(i)\n```\n\nHow many lines does the program print?",
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
        "## Задание\nВ списке `prices` лежат цены покупок. Посчитайте их сумму в переменной `total` " +
        "с помощью цикла `for`.\n\nНапример, для цен 10, 20 и 5 программа выведет `Итого: 35`.",
      body_en:
        "## Task\nThe list `prices` holds the prices of purchases. Add them up in the variable `total` " +
        "with a `for` loop.\n\nFor prices 10, 20 and 5 the program prints `Итого: 35`.",
      xp_reward: 20,
      estimated_minutes: 7,
      starter: "prices = [120, 80, 150]\ntotal = 0\n# пройдите по списку и прибавьте каждую цену к total\n\nprint(\"Итого:\", total)\n",
      expected_output: "Итого: 350",
      // сравнение со значением: сервер сверяет его сам, песочница ожидаемого числа не видит (hidden_checks.py)
      hidden_check: "assert total == 350, \"Сумма должна быть в переменной total\"",
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
        "Маг **{{name}}** знает {{n}} заклинаний, каждое силой {{power}}. Посчитайте общую силу в переменной " +
        "`total` и выведите имя мага и общую силу через двоеточие.\n\nПример формата для другого мага: `Лея: 10`. " +
        "У каждого ученика свои числа, поэтому чужой ответ не подойдёт.",
      body_en:
        "The mage **{{name}}** knows {{n}} spells of power {{power}} each. Compute the total power in `total` and " +
        "print the name and the total separated by a colon, e.g. `Leia: 10`.\n\nEvery learner gets other numbers.",
      xp_reward: 25,
      estimated_minutes: 6,
      starter: "name = \"{{name}}\"\nn = {{n}}\npower = {{power}}\ntotal = 0  # посчитайте общую силу\n\nprint(name + \":\", total)\n",
      expected_output: "{{name}}: {{total}}",
      hidden_check:
        "assert total == {{total}}, \"Общая сила должна быть в переменной total\"\n" +
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
