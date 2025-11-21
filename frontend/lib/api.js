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

export async function login({ email, username, password }) {
  const identifier = username || email;
  // Отправляем и email, и username: мок-API читает email, DRF(SimpleJWT) — username
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
  list: () => api.get("/task-progress/").then((r) => unwrapList(r.data)),
  create: (payload) => api.post("/task-progress/", payload).then((r) => r.data),
  update: (id, payload) =>
    api.patch(`/task-progress/${id}/`, payload).then((r) => r.data),
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

const callLocalApi = async (url, options = {}) => {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    const error = new Error(errBody?.detail || "Local API error");
    error.status = res.status;
    error.payload = errBody;
    throw error;
  }
  return res.json();
};

export const Runner = {
  execute: (payload) =>
    callLocalApi("/api/runner/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const Payments = {
  checkout: (payload) =>
    callLocalApi("/api/payments/checkout", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export function missionStatus(mission) {
  // Determine visual status using DRF fields
  const up = mission.user_progress;
  if (up?.completed) return "completed";
  if (mission.available) return "available";
  return "locked";
}
