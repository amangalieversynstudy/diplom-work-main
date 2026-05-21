const KEY = "player_class";

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

function getAuthToken() {
  if (typeof window === "undefined") return null;
  return (
    localStorage.getItem("access") ||
    localStorage.getItem("token") ||
    localStorage.getItem("access_token")
  );
}

/**
 * Ask the backend whether the current user can choose a class yet.
 * Returns the parsed payload `{ class_unlocked, intro_track, progress, reason }`
 * or `null` if the request fails — callers should fail-open on null.
 */
export async function fetchIntroStatus() {
  if (typeof window === "undefined") return null;
  const token = getAuthToken();
  if (!token) return null;
  const base = process.env.NEXT_PUBLIC_API_URL || "/api";
  try {
    const res = await fetch(`${base}/intro-status/`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}