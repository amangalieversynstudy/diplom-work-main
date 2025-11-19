import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const LANG_KEY = "ui_language";
const DEFAULT_LANG = "ru";

const dictionaries = {
  en: {
    nav: {
      sanctum: "Sanctum",
      worlds: "Worlds",
      quest: "Quest",
      legends: "Legends",
      character: "Character",
      class: "Class",
    },
    layout: {
      badge: "RPG Academy",
      tagline: "Build your legend",
      login: "Login",
      register: "Join Legion",
      seasonLabel: "Season",
      seasonName: "Obsidian Dawn",
      toggleLabel: "Language",
    },
    hero: {
      cardTitle: "Command Console",
      cardSubtitle: "You stand before the Academy sanctum",
      oath: "Current Oath",
      headlineTemplate: "Forge a legendary {{class}} destined for production.",
      fallbackClass: "Initiate",
      primaryCta: "Continue Adventure",
      secondaryCta: "Switch Class",
      badge: "You stand before the Academy sanctum",
    },
    sheet: {
      title: "Character Sheet",
      spec: "Spec",
      level: "Level",
      nextUnlock: "Next Unlock",
      nextUnlockValue: "Mission Map",
    },
    customizer: {
      title: "Avatar Customization",
      subtitle: "Tune armor, accents, and weapon glow to match your class.",
      archetype: "Archetype",
      palette: "Palette",
      slots: {
        hair: "Hair",
        armor: "Armor",
        accent: "Accent",
        weapon: "Weapon",
      },
      reset: "Reset to default",
    },
    quests: {
      title: "Quest Board",
      subtitle: "Pick your next objective",
      items: [
        {
          title: "Light the Forge",
          desc: "Spin up local docker stack and run first migrations.",
          reward: "+50 XP",
        },
        {
          title: "Scout the Worlds",
          desc: "Visit the world map and preview node coordinates.",
          reward: "+30 XP",
        },
        {
          title: "Master Your Class",
          desc: "Choose specialization and unlock class-specific quests.",
          reward: "Passive buff",
        },
      ],
    },
    codex: {
      title: "Codex Updates",
      subtitle: "Lore entries unlocked by progress",
      entries: [
        { title: "Backend Trials", detail: "Celery + Redis jobs proven in smoke tests." },
        { title: "Frontend Rituals", detail: "RPG UI system + onboarding revamp shipped." },
        { title: "Guild Reputation", detail: "CI/CD with coverage + Codecov tracking." },
      ],
    },
    relics: {
      items: [
        { label: "Artifact", value: "CI Sigil", icon: "sparkles" },
        { label: "Allies", value: "Celery sprites", icon: "flame" },
        { label: "Weather", value: "Stable build", icon: "compass" },
      ],
      battlePlan: {
        title: "Battle Plan",
        subtitle: "Implementation checklist",
        items: ["Deploy redesigned UI kit", "Keep missions synced with backend", "Document 50% milestone"],
      },
      signals: {
        title: "Signals",
        subtitle: "Live telemetry",
        items: [
          {
            icon: "sparkles",
            text: "XP gain boosted for newcomers",
          },
          {
            icon: "swords",
            text: "Mission Gate locked until Intro complete",
          },
        ],
      },
    },
    map: {
      title: "Adventure Map",
      subtitle: "Track routes inspired by CodeCombat realms",
      routes: [
        { name: "Forge Path", detail: "Tutorial islands" },
        { name: "Crystal Archives", detail: "Data puzzles" },
        { name: "Shadow Wilds", detail: "Stealth missions" },
        { name: "Aurora Peaks", detail: "Boss gauntlet" },
      ],
      missions: [
        { id: "forge", name: "Obsidian Forge", tier: "Tier I", progress: 80, x: 18, y: 58 },
        { id: "plaza", name: "Sanctum Plaza", tier: "Tier II", progress: 45, x: 35, y: 32 },
        { id: "archives", name: "Crystal Archives", tier: "Tier III", progress: 25, x: 52, y: 60 },
        { id: "wilds", name: "Shadow Wilds", tier: "Tier IV", progress: 10, x: 70, y: 35 },
        { id: "spire", name: "Aurora Spire", tier: "Tier V", progress: 5, x: 84, y: 62 },
        { id: "citadel", name: "Prime Citadel", tier: "Final", progress: 0, x: 60, y: 18 },
      ],
    },
  },
  ru: {
    nav: {
      sanctum: "Санктум",
      worlds: "Миры",
      quest: "Квест",
      legends: "Легенды",
      character: "Персонаж",
      class: "Класс",
    },
    layout: {
      badge: "Академия RPG",
      tagline: "Построй свою легенду",
      login: "Вход",
      register: "Присоединиться",
      seasonLabel: "Сезон",
      seasonName: "Обсидиановый Рассвет",
      toggleLabel: "Язык",
    },
    hero: {
      cardTitle: "Командный консоль",
      cardSubtitle: "Перед тобой святилище Академии",
      oath: "Текущая клятва",
      headlineTemplate: "Куй легендарного {{class}}, готового к релизу.",
      fallbackClass: "Посвящённый",
      primaryCta: "Продолжить приключение",
      secondaryCta: "Сменить класс",
      badge: "Перед тобой святилище Академии",
    },
    sheet: {
      title: "Лист персонажа",
      spec: "Специализация",
      level: "Уровень",
      nextUnlock: "Следующее открытие",
      nextUnlockValue: "Карта миссий",
    },
    customizer: {
      title: "Кастомизация героя",
      subtitle: "Настрой броню, подсветку и оружие под свой стиль.",
      archetype: "Архетип",
      palette: "Палитра",
      slots: {
        hair: "Волосы",
        armor: "Броня",
        accent: "Акцент",
        weapon: "Оружие",
      },
      reset: "Сбросить",
    },
    quests: {
      title: "Доска заданий",
      subtitle: "Выбери следующую цель",
      items: [
        {
          title: "Разжечь горн",
          desc: "Запусти Docker-стек локально и прогоняй миграции.",
          reward: "+50 XP",
        },
        {
          title: "Разведка миров",
          desc: "Загляни на карту и отметь координаты узлов.",
          reward: "+30 XP",
        },
        {
          title: "Освоить класс",
          desc: "Выбери специализацию и открой уникальные задания.",
          reward: "Пассивный бонус",
        },
      ],
    },
    codex: {
      title: "Хроники",
      subtitle: "Записи, которые ты открыл",
      entries: [
        { title: "Испытания бэкенда", detail: "Задания Celery + Redis прошли дымовые тесты." },
        { title: "Ритуалы фронтенда", detail: "Редизайн RPG интерфейса и онбординг готовы." },
        { title: "Репутация гильдии", detail: "CI/CD с покрытиями и отчётами Codecov." },
      ],
    },
    relics: {
      items: [
        { label: "Артефакт", value: "Печать CI", icon: "sparkles" },
        { label: "Соратники", value: "Духи Celery", icon: "flame" },
        { label: "Погода", value: "Стабильная сборка", icon: "compass" },
      ],
      battlePlan: {
        title: "Боевой план",
        subtitle: "Чеклист внедрения",
        items: ["Задеплоить UI-кит", "Синхронизировать миссии с backend", "Задокументировать прогресс 50%"],
      },
      signals: {
        title: "Сигналы",
        subtitle: "Живые телеметрии",
        items: [
          {
            icon: "sparkles",
            text: "Ускоренный рост XP для новичков",
          },
          {
            icon: "swords",
            text: "Врата миссий закрыты до завершения Интро",
          },
        ],
      },
    },
    map: {
      title: "Карта приключения",
      subtitle: "Отслеживай маршруты как в CodeCombat",
      routes: [
        { name: "Путь горна", detail: "Тренировочные острова" },
        { name: "Хрустальные архивы", detail: "Данные и головоломки" },
        { name: "Теневые чащи", detail: "Стелс-миссии" },
        { name: "Сияющие пики", detail: "Череда боссов" },
      ],
      missions: [
        { id: "forge", name: "Обсидиановый горн", tier: "I уровень", progress: 80, x: 18, y: 58 },
        { id: "plaza", name: "Площадь санктума", tier: "II уровень", progress: 45, x: 35, y: 32 },
        { id: "archives", name: "Хрустальные архивы", tier: "III уровень", progress: 25, x: 52, y: 60 },
        { id: "wilds", name: "Теневые чащи", tier: "IV уровень", progress: 10, x: 70, y: 35 },
        { id: "spire", name: "Сверкающий шпиль", tier: "V уровень", progress: 5, x: 84, y: 62 },
        { id: "citadel", name: "Главный цитадель", tier: "Финал", progress: 0, x: 60, y: 18 },
      ],
    },
  },
};

function getStoredLanguage() {
  if (typeof window === "undefined") return DEFAULT_LANG;
  return localStorage.getItem(LANG_KEY) || DEFAULT_LANG;
}

function persistLanguage(value) {
  if (typeof window === "undefined") return;
  localStorage.setItem(LANG_KEY, value);
}

function translate(dictionary, key) {
  return key
    .split(".")
    .reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : undefined), dictionary);
}

const I18nContext = createContext({
  language: DEFAULT_LANG,
  dict: dictionaries[DEFAULT_LANG],
  t: (key) => translate(dictionaries[DEFAULT_LANG], key) || key,
  setLanguage: () => {},
  toggleLanguage: () => {},
  languages: ["ru", "en"],
});

export function I18nProvider({ children }) {
  const [language, setLanguage] = useState(DEFAULT_LANG);

  useEffect(() => {
    setLanguage(getStoredLanguage());
  }, []);

  const changeLanguage = useCallback((next) => {
    const safe = dictionaries[next] ? next : DEFAULT_LANG;
    persistLanguage(safe);
    setLanguage(safe);
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage((prev) => {
      const next = prev === "ru" ? "en" : "ru";
      persistLanguage(next);
      return next;
    });
  }, []);

  const value = useMemo(() => {
    const dict = dictionaries[language] || dictionaries[DEFAULT_LANG];
    return {
      language,
      dict,
      t: (key) => translate(dict, key) || key,
      setLanguage: changeLanguage,
      toggleLanguage,
      languages: Object.keys(dictionaries),
    };
  }, [language, changeLanguage, toggleLanguage]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

export function useDictionary() {
  const { dict } = useI18n();
  return dict;
}

export const languages = [
  { id: "ru", label: "RU" },
  { id: "en", label: "EN" },
];

export function formatHeadline(template, playerClass) {
  if (!template) return "";
  return template.replace("{{class}}", playerClass);
}

export { dictionaries };
