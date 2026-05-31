import axios from "axios";
import { getTokens, setTokens, clearTokens } from "./auth";

// Default to Django backend in dev, but allow overriding (or falling back to Next.js mock API)
const fallbackBase =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000/api" : "/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || fallbackBase;

export const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const { access } = getTokens();
  if (access) config.headers.Authorization = `Bearer ${access}`;
  // MID-06: пробрасываем язык в backend, чтобы он отдавал title_ru/title_en
  // согласно выбору пользователя.
  if (typeof window !== "undefined") {
    const lang = window.localStorage.getItem("ui_language");
    if (lang) config.headers["Accept-Language"] = lang;
  }
  return config;
});

let isRefreshing = false;
let queue = [];

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const { refresh } = getTokens();
      if (!refresh) {
        clearTokens();
        if (typeof window !== "undefined") window.location.href = "/login";
        return Promise.reject(error);
      }
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          queue.push({ resolve, reject });
        })
          .then((token) => {
            original.headers.Authorization = `Bearer ${token}`;
            return api(original);
          })
          .catch(Promise.reject);
      }
      isRefreshing = true;
      try {
        const resp = await axios.post(`${API_BASE}/auth/jwt/refresh/`, {
          refresh,
        });
        const newAccess = resp.data?.access;
        setTokens({ access: newAccess });
        queue.forEach((p) => p.resolve(newAccess));
        queue = [];
        original.headers.Authorization = `Bearer ${newAccess}`;
        return api(original);
      } catch (e) {
        queue.forEach((p) => p.reject(e));
        queue = [];
        clearTokens();
        if (typeof window !== "undefined") window.location.href = "/login";
        return Promise.reject(e);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 429) {
      const detail = error.response.data?.detail || "Too many requests. Please wait.";
      throw new Error(detail);
    }
    return Promise.reject(error);
  }
);

export default api;

export async function login({ email, username, password }) {
  const identifier = username || email;
  // Отправляем и email, и username: backend LoginView поддерживает оба
  const payload = {
    email: email || identifier,
    username: identifier,
    password,
  };
  const { data } = await api.post("/auth/jwt/create/", payload);
  setTokens({ access: data.access, refresh: data.refresh });
  return data;
}

export function logout() {
  clearTokens();
  if (typeof window !== "undefined") window.location.href = "/login";
}

export const Missions = {
  list: () => api.get("/missions/").then((r) => r.data),
  get: (id) => api.get(`/missions/${id}/`).then((r) => r.data),
  start: (id) => api.post(`/missions/${id}/start/`).then((r) => r.data),
  complete: (id) => api.post(`/missions/${id}/complete/`).then((r) => r.data),
};

export const MissionTasks = {
  list: (missionId, params = {}) =>
    api
      .get("/mission-tasks/", { params: { mission: missionId, ...params } })
      .then((r) => r.data),
};

const unwrapList = (data) => {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
};

export const TaskProgressAPI = {
  list: (missionId) => 
    api.get("/task-progress/", { params: { mission: missionId } }).then((r) => unwrapList(r.data)),
  
  create: (payload) => api.post("/task-progress/", payload).then((r) => r.data),
  
  update: (id, payload) =>
    api.patch(`/task-progress/${id}/`, payload).then((r) => r.data),
    
  submit: (taskId, payload) => 
    api.post("/task-progress/", { task: taskId, ...payload }).then((r) => r.data),
};

export const Ranks = {
  list: () => api.get("/ranks/").then((r) => unwrapList(r.data)),
};

export const LeaderboardAPI = {
  list: (params = {}) =>
    api
      .get("/leaderboard/", { params })
      .then((r) => unwrapList(r.data))
      .catch((err) => {
        if (err?.response?.status === 404) return [];
        throw err;
      }),
};

export const Profile = {
  me: async () => {
    try {
      const { data } = await api.get("/profile/me/");
      return data;
    } catch (e) {
      if (e?.response?.status === 404) {
        const { data } = await api.get("/auth/me/");
        return data;
      }
      throw e;
    }
  },
  update: async (payload) => {
    // Бэкенд ProfileMeView принимает плоский объект:
    // {username, email, display_name, bio, class_role}
    // и сам обновляет связанные User + Profile.
    const { data } = await api.patch("/profile/me/", payload);
    return data;
  },
  // ДОБАВЛЕННЫЙ МЕТОД ДЛЯ ИНВЕНТАРЯ:
  consumeItem: async (itemType) => {
    const { data } = await api.post("/profile/use-item/", { item_type: itemType });
    return data;
  },
};

export async function registerUser({ username, email, password }) {
  // DRF: POST /api/auth/register/
  const { data } = await api.post("/auth/register/", {
    username,
    email,
    password,
  });
  return data;
}

export const Locations = {
  list: () => api.get("/locations/").then((r) => r.data),
  get: (id) => api.get(`/locations/${id}/`).then((r) => r.data),
};

export const Tracks = {
  list: () => api.get("/tracks/").then((r) => r.data),
  get: (id) => api.get(`/tracks/${id}/`).then((r) => r.data),
};

export const ProgressAPI = {
  list: () => api.get("/progress/").then((r) => r.data),
};

export const Runner = {
  execute: (code) => api.post("/runner/execute/", { code }),
};

export const AIAssist = {
  /**
   * Ask Gemini for a hint on the current task.
   * @param {string} code        Current code in the editor
   * @param {string} taskDesc    Task description (body_ru or body_en)
   * @param {string} language    Programming language ("python")
   * @returns {Promise<{hint: string}>}
   */
  getHint: (code, taskDesc, language = "python") =>
    api
      .post("/ai-assist/", { code, task_description: taskDesc, language })
      .then((r) => r.data),
};

/**
 * Build a WebSocket URL for the streaming runner.
 *
 * Reuses the same origin as the REST API base, swaps http(s) → ws(s),
 * strips the trailing `/api` segment, and appends the access JWT as a
 * query parameter (the only way to authenticate a browser WebSocket,
 * since `Authorization` headers are not supported by the WS API).
 *
 * Returns null when no token is provided AND the origin cannot be derived
 * (SSR with no NEXT_PUBLIC_API_BASE).
 */
export function getRunnerWsUrl(accessToken) {
  let httpBase = API_BASE;
  let origin;
  if (httpBase.startsWith("http")) {
    try {
      origin = new URL(httpBase).origin;
    } catch {
      return null;
    }
  } else if (typeof window !== "undefined") {
    origin = window.location.origin;
  } else {
    return null;
  }
  const wsOrigin = origin.replace(/^http/i, "ws");
  const token = accessToken ? `?token=${encodeURIComponent(accessToken)}` : "";
  return `${wsOrigin}/ws/runner/${token}`;
}

export function missionStatus(mission) {
  // Determine visual status using DRF fields
  const up = mission.user_progress;
  if (up?.completed) return "completed";
  if (mission.available) return "available";
  return "locked";
}
