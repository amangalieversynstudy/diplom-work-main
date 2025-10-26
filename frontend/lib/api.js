import axios from "axios";
import { getTokens, setTokens, clearTokens } from "./auth";

// Default to Next.js local API routes for demo; override with NEXT_PUBLIC_API_BASE to use real DRF
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

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

export const ProgressAPI = {
  list: () => api.get("/progress/").then((r) => r.data),
};

export function missionStatus(mission) {
  // Determine visual status using DRF fields
  const up = mission.user_progress;
  if (up?.completed) return "completed";
  if (mission.available) return "available";
  return "locked";
}
