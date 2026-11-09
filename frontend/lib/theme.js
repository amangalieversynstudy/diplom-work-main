import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const THEME_KEY = "ui_theme";
const TRANSITION_MS = 400;

const ThemeContext = createContext({
  theme: "dark",
  setTheme: () => {},
  toggleTheme: () => {},
});

function readStoredTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY);
  } catch {
    return null; // приватный режим или запрет хранилища: тема по системе
  }
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState("dark");
  // Класс темы ставит скрипт в _document до первой отрисовки. Пока сохранённая тема не прочитана,
  // здесь ничего не трогаем: иначе светлая тема на миг стала бы тёмной.
  const [loaded, setLoaded] = useState(false);
  const applied = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    const stored = readStoredTheme();
    // Использовать сохранённую тему или системные настройки как запасной вариант
    setTheme(stored || (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    const root = window.document.documentElement;
    // плавно только при переключении пользователем, не при загрузке страницы
    if (applied.current !== null && applied.current !== theme) {
      root.classList.add("theme-transition");
      clearTimeout(timer.current);
      timer.current = setTimeout(() => root.classList.remove("theme-transition"), TRANSITION_MS);
    }
    root.classList.toggle("dark", theme === "dark");
    applied.current = theme;
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      // тема просто не запомнится
    }
  }, [theme, loaded]);

  useEffect(() => () => clearTimeout(timer.current), []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  const value = useMemo(() => ({
    theme,
    setTheme,
    toggleTheme,
  }), [theme, setTheme, toggleTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
