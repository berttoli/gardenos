"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { Icon } from "../shared/icons";
import {
  themeDefinitions,
  themeIds,
  type ThemeAppearancePreferences,
  type ThemeAppearanceState,
  type ThemeDefinition,
  type ThemeId,
  themePreferenceStorageKey,
} from "./theme-data";

type ThemeAppearanceContextValue = {
  theme: ThemeId;
  themeDefinition: ThemeDefinition;
  preferences: ThemeAppearancePreferences;
  setTheme: (theme: ThemeId) => void;
  updatePreferences: (next: Partial<ThemeAppearancePreferences>) => void;
  resetPreferences: () => void;
  resolvePreferences: (theme: ThemeId) => ThemeAppearancePreferences;
};

const ThemeAppearanceContext = createContext<ThemeAppearanceContextValue | null>(null);

type Rgba = {
  r: number;
  g: number;
  b: number;
  a: number;
};

const EMPTY_STATE: ThemeAppearanceState = {
  theme: "sage",
  preferences: {},
};

const SEMANTIC_COLOR_VARS = [
  "--app-bg",
  "--app-bg-secondary",
  "--surface-1",
  "--surface-2",
  "--surface-3",
  "--surface-glass",
  "--surface-glass-strong",
  "--surface-hover",
  "--surface-selected",
  "--text-primary",
  "--text-secondary",
  "--text-muted",
  "--border-subtle",
  "--border-strong",
  "--border-highlight",
  "--accent-primary",
  "--accent-primary-hover",
  "--accent-secondary",
  "--accent-soft",
  "--focus-ring",
  "--shadow-color",
  "--glass-highlight",
  "--status-urgent",
  "--status-urgent-bg",
  "--status-high",
  "--status-high-bg",
  "--status-medium",
  "--status-medium-bg",
  "--status-low",
  "--status-low-bg",
  "--ambient-orb-1",
  "--ambient-orb-2",
  "--ambient-orb-3",
  "--ambient-orb-4",
] as const;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function round(value: number) {
  return Math.round(value);
}

function normalizeHex(value: string) {
  const trimmed = value.trim();

  if (/^#[0-9a-fA-F]{3}$/.test(trimmed)) {
    return `#${trimmed
      .slice(1)
      .split("")
      .map((segment) => `${segment}${segment}`)
      .join("")
      .toUpperCase()}`;
  }

  if (/^#[0-9a-fA-F]{6}$/.test(trimmed)) {
    return trimmed.toUpperCase();
  }

  return null;
}

function parseColor(value: string): Rgba | null {
  const hex = normalizeHex(value);

  if (hex) {
    const number = Number.parseInt(hex.slice(1), 16);

    return {
      r: (number >> 16) & 255,
      g: (number >> 8) & 255,
      b: number & 255,
      a: 1,
    };
  }

  const rgbaMatch = value.trim().match(/^rgba?\(([^)]+)\)$/i);

  if (!rgbaMatch) {
    return null;
  }

  const parts = rgbaMatch[1]
    .split(",")
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (parts.length < 3) {
    return null;
  }

  const [r, g, b] = parts.slice(0, 3).map((part) => Number.parseFloat(part));
  const a = parts[3] != null ? Number.parseFloat(parts[3]) : 1;

  if ([r, g, b, a].some((entry) => Number.isNaN(entry))) {
    return null;
  }

  return {
    r: clamp(r, 0, 255),
    g: clamp(g, 0, 255),
    b: clamp(b, 0, 255),
    a: clamp(a, 0, 1),
  };
}

function rgbaToString(color: Rgba) {
  const alpha = Math.round(color.a * 1000) / 1000;
  return alpha >= 1 ? rgbToHex(color) : `rgba(${round(color.r)}, ${round(color.g)}, ${round(color.b)}, ${alpha})`;
}

function rgbToHex(color: Pick<Rgba, "r" | "g" | "b">) {
  return `#${[color.r, color.g, color.b]
    .map((channel) => clamp(round(channel), 0, 255).toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase()}`;
}

function mixColors(left: Rgba, right: Rgba, ratio: number): Rgba {
  const mix = clamp(ratio, 0, 1);

  return {
    r: left.r * (1 - mix) + right.r * mix,
    g: left.g * (1 - mix) + right.g * mix,
    b: left.b * (1 - mix) + right.b * mix,
    a: left.a * (1 - mix) + right.a * mix,
  };
}

function rgbToHsl(color: Rgba) {
  const red = color.r / 255;
  const green = color.g / 255;
  const blue = color.b / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const delta = max - min;
  const lightness = (max + min) / 2;
  const saturation = delta === 0 ? 0 : delta / (1 - Math.abs(2 * lightness - 1));
  let hue = 0;

  if (delta !== 0) {
    switch (max) {
      case red:
        hue = ((green - blue) / delta) % 6;
        break;
      case green:
        hue = (blue - red) / delta + 2;
        break;
      default:
        hue = (red - green) / delta + 4;
        break;
    }
  }

  return {
    h: ((hue * 60) + 360) % 360,
    s: saturation,
    l: lightness,
  };
}

function hslToRgb(hsl: { h: number; s: number; l: number }, alpha: number): Rgba {
  const hue = ((hsl.h % 360) + 360) % 360;
  const saturation = clamp(hsl.s, 0, 1);
  const lightness = clamp(hsl.l, 0, 1);
  const chroma = (1 - Math.abs(2 * lightness - 1)) * saturation;
  const huePrime = hue / 60;
  const secondary = chroma * (1 - Math.abs((huePrime % 2) - 1));
  let red = 0;
  let green = 0;
  let blue = 0;

  if (huePrime >= 0 && huePrime < 1) {
    red = chroma;
    green = secondary;
  } else if (huePrime < 2) {
    red = secondary;
    green = chroma;
  } else if (huePrime < 3) {
    green = chroma;
    blue = secondary;
  } else if (huePrime < 4) {
    green = secondary;
    blue = chroma;
  } else if (huePrime < 5) {
    red = secondary;
    blue = chroma;
  } else {
    red = chroma;
    blue = secondary;
  }

  const match = lightness - chroma / 2;

  return {
    r: clamp((red + match) * 255, 0, 255),
    g: clamp((green + match) * 255, 0, 255),
    b: clamp((blue + match) * 255, 0, 255),
    a: clamp(alpha, 0, 1),
  };
}

function tuneContrast(color: Rgba, contrast: number) {
  const hsl = rgbToHsl(color);
  const adjustment = contrast / 100;
  const newLightness = clamp(0.5 + (hsl.l - 0.5) * adjustment, 0, 1);

  return hslToRgb(
    {
      h: hsl.h,
      s: hsl.s,
      l: newLightness,
    },
    color.a,
  );
}

function tuneSaturation(color: Rgba, saturation: number) {
  const hsl = rgbToHsl(color);
  const newSaturation = clamp(hsl.s * (saturation / 100), 0, 1);

  return hslToRgb(
    {
      h: hsl.h,
      s: newSaturation,
      l: hsl.l,
    },
    color.a,
  );
}

function isSurfaceToken(token: string) {
  return (
    token === "--app-bg" ||
    token === "--app-bg-secondary" ||
    token === "--surface-1" ||
    token === "--surface-2" ||
    token === "--surface-3" ||
    token === "--surface-glass" ||
    token === "--surface-glass-strong" ||
    token === "--surface-hover" ||
    token === "--surface-selected" ||
    token === "--accent-soft" ||
    token === "--ambient-orb-1" ||
    token === "--ambient-orb-2" ||
    token === "--ambient-orb-3" ||
    token === "--ambient-orb-4"
  );
}

function isAccentToken(token: string) {
  return (
    token === "--accent-primary" ||
    token === "--accent-primary-hover" ||
    token === "--accent-secondary" ||
    token === "--focus-ring" ||
    token === "--border-highlight"
  );
}

function tintStrengthForToken(token: string) {
  if (token === "--surface-glass" || token === "--surface-glass-strong") {
    return 0;
  }

  if (token === "--accent-primary") {
    return 0.34;
  }

  if (token === "--accent-primary-hover") {
    return 0.42;
  }

  if (token === "--accent-secondary") {
    return 0.26;
  }

  if (token === "--focus-ring") {
    return 0.4;
  }

  if (token === "--surface-selected") {
    return 0.08;
  }

  if (token === "--surface-hover") {
    return 0.06;
  }

  if (token === "--surface-3") {
    return 0.05;
  }

  if (token === "--surface-2") {
    return 0.04;
  }

  if (token === "--surface-1") {
    return 0.03;
  }

  if (token === "--app-bg-secondary") {
    return 0.04;
  }

  if (token === "--app-bg") {
    return 0.02;
  }

  if (token.startsWith("--ambient-orb")) {
    return 0.1;
  }

  return 0;
}

function adjustColorToken(token: string, value: string, prefs: ThemeAppearancePreferences) {
  const parsed = parseColor(value);

  if (!parsed) {
    return value;
  }

  const tintColor = parseColor(prefs.tint) ?? parseColor(themeDefinitions.sage.defaults.tint);
  const contrast = clamp(prefs.contrast, 80, 120);
  const saturation = clamp(prefs.saturation, 0, 140);
  const monochrome = themeDefinitions.daylily.id === "daylily" && prefs.saturation === 0;
  let next = parsed;

  if (monochrome || token === "--text-primary" || token === "--text-secondary" || token === "--text-muted") {
    next = tuneContrast(next, contrast);

    if (!monochrome) {
      next = tuneSaturation(next, saturation);
    }

    return rgbaToString(next);
  }

  const saturationFactor = monochrome ? 0 : saturation;

  if (isSurfaceToken(token) || isAccentToken(token) || token === "--border-subtle" || token === "--border-strong") {
    next = tuneSaturation(next, saturationFactor);
  }

  if (
    isAccentToken(token) ||
    token === "--surface-hover" ||
    token === "--surface-selected" ||
    token === "--surface-1" ||
    token === "--surface-2" ||
    token === "--surface-3" ||
    token === "--app-bg" ||
    token === "--app-bg-secondary" ||
    token === "--border-subtle" ||
    token === "--border-strong"
  ) {
    next = tuneContrast(next, contrast);
  }

  const tintStrength = tintStrengthForToken(token);
  if (tintStrength > 0 && tintColor) {
    next = mixColors(next, tintColor, tintStrength);
  }

  if ((token === "--surface-glass" || token === "--surface-glass-strong") && prefs.applyTintToGlass && tintColor) {
    next = mixColors(next, tintColor, token === "--surface-glass-strong" ? 0.16 : 0.12);
  }

  return rgbaToString(next);
}

export function resolveThemeAppearance(theme: ThemeId, preferences?: Partial<Record<ThemeId, ThemeAppearancePreferences>>) {
  const definition = themeDefinitions[theme];
  const prefs = normalizePreferences(theme, preferences?.[theme]);
  const vars: Record<string, string> = {
    ...definition.tokens,
  };

  for (const token of SEMANTIC_COLOR_VARS) {
    if (definition.tokens[token] == null) {
      continue;
    }

    vars[token] = adjustColorToken(token, definition.tokens[token], prefs);
  }

  return {
    definition,
    preferences: prefs,
    vars,
  };
}

export function normalizePreferences(theme: ThemeId, preferences?: Partial<ThemeAppearancePreferences> | null): ThemeAppearancePreferences {
  const defaults = themeDefinitions[theme].defaults;

  if (!preferences) {
    return { ...defaults };
  }

  const tint = normalizeHex(preferences.tint ?? defaults.tint) ?? defaults.tint;
  const isDaylily = theme === "daylily";

  return {
    tint: isDaylily ? "#7A7A7A" : tint,
    contrast: clamp(Number.isFinite(preferences.contrast as number) ? Number(preferences.contrast) : defaults.contrast, 80, 120),
    saturation: isDaylily ? 0 : clamp(Number.isFinite(preferences.saturation as number) ? Number(preferences.saturation) : defaults.saturation, 0, 140),
    applyTintToGlass: typeof preferences.applyTintToGlass === "boolean" ? preferences.applyTintToGlass : defaults.applyTintToGlass,
  };
}

export function normalizeAppearanceState(value: unknown): ThemeAppearanceState {
  const defaults = EMPTY_STATE;

  if (!value || typeof value !== "object") {
    return defaults;
  }

  const candidate = value as Partial<ThemeAppearanceState>;
  const theme = themeIds.includes(candidate.theme as ThemeId) ? (candidate.theme as ThemeId) : defaults.theme;
  const preferences: Partial<Record<ThemeId, ThemeAppearancePreferences>> = {};

  if (candidate.preferences && typeof candidate.preferences === "object") {
    for (const themeId of themeIds) {
      const entry = candidate.preferences[themeId];
      if (entry && typeof entry === "object") {
        preferences[themeId] = normalizePreferences(themeId, entry);
      }
    }
  }

  return {
    theme,
    preferences,
  };
}

export function loadAppearanceState(): ThemeAppearanceState {
  if (typeof window === "undefined") {
    return EMPTY_STATE;
  }

  try {
    const raw = window.localStorage.getItem(themePreferenceStorageKey);
    if (!raw) {
      return EMPTY_STATE;
    }

    return normalizeAppearanceState(JSON.parse(raw) as unknown);
  } catch {
    return EMPTY_STATE;
  }
}

export function saveAppearanceState(state: ThemeAppearanceState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(themePreferenceStorageKey, JSON.stringify(state));
}

export function setThemeDocumentVars(theme: ThemeId, preferences: ThemeAppearancePreferences) {
  const { vars, definition } = resolveThemeAppearance(theme, { [theme]: preferences });

  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = definition.colorScheme;

  for (const [key, value] of Object.entries(vars)) {
    root.style.setProperty(key, value);
  }
}

function ThemeSelectorButton({ active, theme }: { active: boolean; theme: ThemeDefinition }) {
  return (
    <>
      <span className="target-theme-option-swatches" aria-hidden="true">
        {theme.swatches.map((swatch) => (
          <span key={swatch} style={{ background: swatch }} />
        ))}
      </span>

      <span className="target-theme-option-copy">
        <strong>{theme.name}</strong>
        <span>{theme.description}</span>
      </span>

      <span className="target-theme-option-pill">{active ? "Active" : "Use"}</span>
    </>
  );
}

function ThemeSlider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  disabled,
  suffix = "%",
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  suffix?: string;
}) {
  return (
    <label className="target-appearance-slider">
      <span className="target-appearance-slider-head">
        <strong>{label}</strong>
        <span aria-live="polite">
          {value}
          {suffix}
        </span>
      </span>
      <input
        aria-label={`${label} ${value}${suffix}`}
        disabled={disabled}
        min={min}
        max={max}
        step={step}
        type="range"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function ThemeToggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button className="target-appearance-switch" data-checked={checked ? "true" : "false"} type="button" onClick={() => onChange(!checked)}>
      <span>Apply to glass surfaces</span>
      <span className="target-appearance-switch-track" aria-hidden="true">
        <span />
      </span>
    </button>
  );
}

export function ThemeAppearanceProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ThemeAppearanceState>(EMPTY_STATE);
  const [hasLoadedPreferences, setHasLoadedPreferences] = useState(false);
  const currentTheme = state.theme;
  const themeDefinition = themeDefinitions[currentTheme];
  const preferences = useMemo(() => normalizePreferences(currentTheme, state.preferences[currentTheme]), [currentTheme, state.preferences]);

  useLayoutEffect(() => {
    const loadedState = loadAppearanceState();
    setState(loadedState);
    setHasLoadedPreferences(true);
  }, []);

  useEffect(() => {
    setThemeDocumentVars(currentTheme, preferences);
  }, [currentTheme, preferences]);

  useEffect(() => {
    if (!hasLoadedPreferences) {
      return;
    }

    saveAppearanceState(state);
  }, [hasLoadedPreferences, state]);

  const updatePreferences = useCallback((next: Partial<ThemeAppearancePreferences>) => {
    setState((current) => {
      const theme = current.theme;
      const nextPreferences = normalizePreferences(theme, {
        ...themeDefinitions[theme].defaults,
        ...current.preferences[theme],
        ...next,
      });

      return {
        ...current,
        preferences: {
          ...current.preferences,
          [theme]: nextPreferences,
        },
      };
    });
  }, []);

  const setTheme = useCallback((nextTheme: ThemeId) => {
    setState((current) => {
      const nextPreferences = current.preferences[nextTheme] ?? { ...themeDefinitions[nextTheme].defaults };
      return {
        ...current,
        theme: nextTheme,
        preferences: {
          ...current.preferences,
          [nextTheme]: normalizePreferences(nextTheme, nextPreferences),
        },
      };
    });
  }, []);

  const resetPreferences = useCallback(() => {
    setState((current) => {
      const theme = current.theme;
      return {
        ...current,
        preferences: {
          ...current.preferences,
          [theme]: { ...themeDefinitions[theme].defaults },
        },
      };
    });
  }, []);

  const resolveTheme = useCallback((theme: ThemeId) => normalizePreferences(theme, state.preferences[theme]), [state.preferences]);

  const contextValue = useMemo<ThemeAppearanceContextValue>(
    () => ({
      theme: currentTheme,
      themeDefinition,
      preferences,
      setTheme,
      updatePreferences,
      resetPreferences,
      resolvePreferences: resolveTheme,
    }),
    [currentTheme, themeDefinition, preferences, setTheme, updatePreferences, resetPreferences, resolveTheme],
  );

  return <ThemeAppearanceContext.Provider value={contextValue}>{children}</ThemeAppearanceContext.Provider>;
}

export function useThemeAppearance() {
  const context = useContext(ThemeAppearanceContext);

  if (!context) {
    throw new Error("useThemeAppearance must be used within ThemeAppearanceProvider");
  }

  return context;
}

export function ThemeMenu() {
  const { theme, setTheme, updatePreferences, resetPreferences, resolvePreferences } = useThemeAppearance();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDetailsElement | null>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const mountedRef = useRef(false);

  const resolved = resolvePreferences(theme);
  const selectedTheme = themeDefinitions[theme];
  const tintDisabled = theme === "daylily";
  const saturationDisabled = theme === "daylily";

  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;
      return;
    }

    if (!open) {
      triggerRef.current?.focus();
      return;
    }

    const focusTarget = panelRef.current?.querySelector<HTMLElement>("[data-theme-option='true']") ?? panelRef.current?.querySelector<HTMLElement>("input, button");
    focusTarget?.focus();
  }, [open]);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const node = menuRef.current;

      if (!node || !node.open) {
        return;
      }

      if (event.target instanceof Node && node.contains(event.target)) {
        return;
      }

      node.open = false;
      setOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }

      const node = menuRef.current;
      if (node?.open) {
        node.open = false;
        setOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const closeMenu = () => {
    const node = menuRef.current;
    if (node) {
      node.open = false;
    }
    setOpen(false);
  };

  return (
    <details
      ref={menuRef}
      className="target-popover target-theme-menu"
      data-open={open ? "true" : "false"}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary ref={triggerRef} className="target-popover-trigger target-theme-trigger" aria-label="Appearance">
        <Icon name="palette" className="target-theme-trigger-icon" />
      </summary>

      <div ref={panelRef} className="target-popover-panel target-theme-panel" data-align="right" data-side="bottom" role="group" aria-label="Appearance settings">
        <div className="target-theme-panel-head">
          <div>
            <span className="section-label">Appearance</span>
            <strong>Customize {selectedTheme.name}</strong>
          </div>
          <span className="target-theme-panel-chip" aria-label={`Selected theme ${selectedTheme.name}`}>
            {selectedTheme.name}
          </span>
        </div>

        <div className="target-theme-grid" aria-label="Theme options">
          {themeIds.map((themeId) => (
            <button
              key={themeId}
              className="target-theme-card-shell"
              data-active={themeId === theme ? "true" : "false"}
              data-theme-id={themeId}
              type="button"
              aria-current={themeId === theme ? "true" : undefined}
              onClick={() => setTheme(themeId)}
            >
              <ThemeSelectorButton active={themeId === theme} theme={themeDefinitions[themeId]} />
            </button>
          ))}
        </div>

        <div className="target-theme-controls">
          <div className="target-theme-section-head">
            <span className="section-label">Theme</span>
            <span className="target-theme-section-meta">Current theme and surface settings</span>
          </div>

          <label className="target-appearance-color-row">
            <span className="target-appearance-color-label">
              <strong>Tint</strong>
              <span>{tintDisabled ? "Monochrome locked" : "Accent tint"}</span>
            </span>
            <span className="target-appearance-color-group">
              <span className="target-appearance-color-swatch" style={{ background: resolved.tint }} aria-hidden="true" />
              <input
                aria-label="Tint color"
                disabled={tintDisabled}
                type="color"
                value={resolved.tint}
                onChange={(event) => updatePreferences({ tint: event.target.value.toUpperCase() })}
              />
              <input
                aria-label="Tint hex value"
                disabled={tintDisabled}
                maxLength={7}
                spellCheck={false}
                type="text"
                value={resolved.tint}
                onChange={(event) => {
                  const normalized = normalizeHex(event.target.value);
                  if (normalized) {
                    updatePreferences({ tint: normalized });
                  }
                }}
              />
            </span>
          </label>

          <ThemeSlider
            label="Contrast"
            value={resolved.contrast}
            min={80}
            max={120}
            step={1}
            onChange={(value) => updatePreferences({ contrast: value })}
            suffix="%"
          />

          <ThemeSlider
            label="Saturation"
            value={resolved.saturation}
            min={0}
            max={140}
            step={1}
            disabled={saturationDisabled}
            onChange={(value) => updatePreferences({ saturation: value })}
            suffix="%"
          />

          <ThemeToggle
            checked={resolved.applyTintToGlass}
            onChange={(next) => updatePreferences({ applyTintToGlass: next })}
          />
        </div>

        <div className="target-theme-actions">
          <button className="target-theme-reset" type="button" onClick={resetPreferences}>
            Reset
          </button>
          <button className="target-theme-done" type="button" onClick={closeMenu}>
            Done
          </button>
        </div>
      </div>
    </details>
  );
}

export function ThemeBootstrapScript() {
  const script = `
    (function () {
      try {
        var raw = localStorage.getItem(${JSON.stringify(themePreferenceStorageKey)});
        if (!raw) return;
        var parsed = JSON.parse(raw);
        if (parsed && parsed.theme) {
          document.documentElement.dataset.theme = parsed.theme;
          document.documentElement.style.colorScheme = ["ink-botanical", "night-shade", "smoked-olive"].indexOf(parsed.theme) >= 0 ? "dark" : "light";
        }
      } catch (error) {}
    })();
  `;

  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}

export function themePanelInlineStyles(theme: ThemeId, preferences: ThemeAppearancePreferences): CSSProperties {
  const resolved = resolveThemeAppearance(theme, { [theme]: preferences });
  return Object.fromEntries(Object.entries(resolved.vars)) as CSSProperties;
}
