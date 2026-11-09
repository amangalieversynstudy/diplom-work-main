import { api } from "./api";
import { getTokens } from "./auth";

const KEY = "player_class";

// Frontend id → backend ClassRole pk (must match fixtures/class_roles.json)
export const CLASS_ROLE_IDS = { python: 1, django: 2, devops: 3 };

// pk класса по ключу, который помнит браузер; null, если класса нет или ключ незнакомый
export function classRoleFromKey(key) {
  return CLASS_ROLE_IDS[key] ?? null;
}

export function getPlayerClass() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}

export function setPlayerClass(value) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, value);
}

export function clearPlayerClass() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY);
}

/**
 * Ask the backend whether the current user can choose a class yet.
 * Returns the parsed payload `{ class_unlocked, intro_track, progress, reason }`
 * or `null` if the request fails — callers should fail-open on null.
 * Goes through the shared axios client, so an expired token is refreshed.
 */
export async function fetchIntroStatus() {
  if (typeof window === "undefined" || !getTokens().access) return null;
  try {
    const res = await api.get("/intro-status/");
    return res.data;
  } catch {
    return null;
  }
}
