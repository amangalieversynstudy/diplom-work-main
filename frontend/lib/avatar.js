import { useEffect, useState } from "react";

const KEY = "avatar_config";

export const defaultAvatar = {
  archetype: "mage",
  hair: "#fcd34d",
  armor: "#7c3aed",
  accent: "#22d3ee",
  weapon: "#f97316",
};

export const archetypes = [
  { id: "mage", label: "Mage" },
  { id: "rogue", label: "Rogue" },
  { id: "knight", label: "Knight" },
];

export const palette = [
  "#fcd34d",
  "#38bdf8",
  "#f472b6",
  "#4ade80",
  "#fb923c",
  "#c4b5fd",
  "#facc15",
];

function mergeConfig(raw) {
  return { ...defaultAvatar, ...(raw || {}) };
}

export function getAvatarConfig() {
  if (typeof window === "undefined") return defaultAvatar;
  try {
    const raw = JSON.parse(window.localStorage.getItem(KEY) || "null");
    return mergeConfig(raw);
  } catch (e) {
    return defaultAvatar;
  }
}

export function setAvatarConfig(patch) {
  if (typeof window === "undefined") return;
  const current = getAvatarConfig();
  const next = { ...current, ...patch };
  window.localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function useAvatarConfig() {
  const [config, setConfig] = useState(defaultAvatar);

  useEffect(() => {
    setConfig(getAvatarConfig());
  }, []);

  function update(patch) {
    const next = setAvatarConfig(patch);
    setConfig(next);
  }

  return [config, update];
}
