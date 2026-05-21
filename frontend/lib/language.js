const KEY = "selected_language";

export const LANGUAGES = {
  python: {
    id: "python",
    name: "Python",
    description: "Скрипты, алгоритмы, веб-фреймворки, ML",
    crest: "🐍",
    color: "from-yellow-500 to-blue-500",
    available: true,
    classes: ["python", "django", "devops"],
  },
  javascript: {
    id: "javascript",
    name: "JavaScript",
    description: "Frontend, Node.js, full-stack",
    crest: "⚡",
    color: "from-yellow-400 to-orange-500",
    available: false,
    classes: [],
  },
  go: {
    id: "go",
    name: "Go",
    description: "Микросервисы, конкурентность, инфраструктура",
    crest: "🚀",
    color: "from-cyan-400 to-blue-600",
    available: false,
    classes: [],
  },
};

export function getSelectedLanguage() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}

export function setSelectedLanguage(id) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, id);
}

export function clearSelectedLanguage() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
}

export function getLanguageData(id) {
  return LANGUAGES[id] || null;
}
