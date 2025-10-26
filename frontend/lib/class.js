const KEY = "player_class";

export function getPlayerClass() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}

export function setPlayerClass(value) {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY, value);
}
