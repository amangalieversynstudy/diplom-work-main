import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { en } from "./dictionaries/en";
import { ru } from "./dictionaries/ru";

const LANG_KEY = "ui_language";
const DEFAULT_LANG = "ru";

// Собираем словари
const dictionaries = {
  en,
  ru,
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