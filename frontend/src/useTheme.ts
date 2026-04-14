import { useEffect, useState } from "react";

export type ThemeMode = "light" | "dark" | "auto";

const STORAGE_KEY = "mediareviewer-theme";
const CYCLE: ThemeMode[] = ["auto", "light", "dark"];

function resolveEffectiveTheme(mode: ThemeMode): "light" | "dark" {
  if (mode !== "auto") return mode;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Persist and apply the theme mode, returning current mode and a cycle function. */
export function useTheme(): [ThemeMode, () => void] {
  const [mode, setMode] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "auto") return stored;
    return "auto";
  });

  useEffect(() => {
    const html = document.documentElement;

    const apply = (): void => {
      html.setAttribute("data-bs-theme", resolveEffectiveTheme(mode));
    };

    apply();

    if (mode !== "auto") return undefined;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", apply);
    return () => {
      mq.removeEventListener("change", apply);
    };
  }, [mode]);

  const cycleTheme = (): void => {
    const next = CYCLE[(CYCLE.indexOf(mode) + 1) % CYCLE.length] ?? "auto";
    localStorage.setItem(STORAGE_KEY, next);
    setMode(next);
  };

  return [mode, cycleTheme];
}
