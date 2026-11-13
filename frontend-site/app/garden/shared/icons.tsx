import type { ReactNode } from "react";

export const iconGlyphs = {
  dashboard: (
    <>
      <rect x="4" y="4" width="6" height="6" rx="1.5" />
      <rect x="14" y="4" width="6" height="6" rx="1.5" />
      <rect x="4" y="14" width="6" height="6" rx="1.5" />
      <rect x="14" y="14" width="6" height="6" rx="1.5" />
    </>
  ),
  plants: (
    <>
      <path d="M12 20V10" />
      <path d="M12 11c-2.7-.2-4.7-2-5.7-4.6C9 6 11 7.1 12 10" />
      <path d="M12 13c3.2-.2 5.7-2.3 6.8-5.8-3.7.1-6.1 1.5-6.8 5.8Z" />
    </>
  ),
  tasks: (
    <>
      <path d="M5 6h9" />
      <path d="M5 12h14" />
      <path d="M5 18h10" />
      <path d="M16 5l2 2 3-3" />
      <rect x="4" y="4.5" width="3.6" height="3.6" rx="1" />
    </>
  ),
  spark: (
    <>
      <path d="M12 4.5v3.2" />
      <path d="M12 16.3v3.2" />
      <path d="M4.5 12h3.2" />
      <path d="M16.3 12h3.2" />
      <path d="M7.2 7.2l2.2 2.2" />
      <path d="M14.6 14.6l2.2 2.2" />
      <path d="M16.8 7.2l-2.2 2.2" />
      <path d="M9.4 14.6l-2.2 2.2" />
    </>
  ),
  uikit: (
    <>
      <rect x="4" y="5" width="16" height="4" rx="1.4" />
      <rect x="4" y="11" width="11" height="4" rx="1.4" />
      <rect x="4" y="17" width="8" height="3" rx="1.2" />
    </>
  ),
  health: (
    <>
      <path d="M12 20s-6.5-4.1-8.6-8.1C1.8 8.4 3.7 5.5 6.8 5.5c1.7 0 3 .8 3.9 2 1-1.2 2.3-2 4-2 3 0 4.9 2.9 3.4 6.4C18.6 15.9 12 20 12 20Z" />
      <path d="M5.5 12h4l1.2-2.3 2.1 4 1.3-1.7H19" />
    </>
  ),
  search: (
    <>
      <circle cx="10" cy="10" r="4.8" />
      <path d="M13.5 13.5 18 18" />
    </>
  ),
  bell: (
    <>
      <path d="M6 17h12l-1.3-1.6A4.5 4.5 0 0 1 15 12.5V10a3 3 0 1 0-6 0v2.5c0 1-.4 2-1.1 2.8L6 17Z" />
      <path d="M10 18a2 2 0 0 0 4 0" />
    </>
  ),
  weather: (
    <>
      <circle cx="8" cy="8" r="3" />
      <path d="M5.5 15h10.8a3 3 0 0 0 .2-6 4.5 4.5 0 0 0-8.8 1" />
    </>
  ),
  network: (
    <>
      <circle cx="12" cy="12" r="2.1" />
      <circle cx="5.5" cy="7" r="1.4" />
      <circle cx="18.5" cy="7" r="1.4" />
      <circle cx="6" cy="17.5" r="1.4" />
      <path d="M10.4 10.7 7 8.1" />
      <path d="M13.7 10.7 17 8.1" />
      <path d="M10.2 13.5 7.4 16" />
      <path d="M13.8 13.5 16.6 16" />
    </>
  ),
  calendar: (
    <>
      <rect x="4" y="5" width="16" height="15" rx="3" />
      <path d="M4 9h16" />
      <path d="M8 3.5v3" />
      <path d="M16 3.5v3" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="7.2" />
      <path d="M12 8v4l2.6 1.6" />
    </>
  ),
  offline: (
    <>
      <circle cx="12" cy="12" r="7.2" />
      <path d="M8 8l8 8" />
      <path d="M9 5.5h6" />
    </>
  ),
  add: (
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>
  ),
  inventory: (
    <>
      <path d="M4.5 8.2 12 4l7.5 4.2v9.4L12 22l-7.5-4.4V8.2Z" />
      <path d="M12 4v18" />
      <path d="M4.7 8.2 12 12.4l7.3-4.2" />
    </>
  ),
  queue: (
    <>
      <path d="M5 7h14" />
      <path d="M5 12h10" />
      <path d="M5 17h14" />
      <circle cx="18.5" cy="12" r="1.5" />
    </>
  ),
  map: (
    <>
      <path d="M4.5 6.5 9 5l6 2 4.5-1.5v12L15 19l-6-2-4.5 1.5v-12Z" />
      <path d="M9 5v12" />
      <path d="M15 7v12" />
    </>
  ),
  leaf: (
    <>
      <path d="M5.5 14.8c4.8-8.7 11.5-9 13-9-1 6.8-4 12.5-11.4 12.5-2.9 0-4-1.7-1.6-3.5Z" />
      <path d="M9 13.8c1.5-1.4 4.2-3.7 7.7-5.2" />
    </>
  ),
  bellOutline: (
    <>
      <path d="M6 17h12l-1.3-1.5A4.7 4.7 0 0 1 15 12.4V10a3 3 0 1 0-6 0v2.4c0 1-.4 2-1.1 2.8L6 17Z" />
      <path d="M10.5 18a1.5 1.5 0 0 0 3 0" />
    </>
  ),
  people: (
    <>
      <circle cx="8" cy="8" r="2.6" />
      <circle cx="16" cy="9" r="2.2" />
      <path d="M4.5 18c.7-3 2.6-4.6 5.5-4.6 2.8 0 4.7 1.4 5.4 4.2" />
      <path d="M12.8 18c.4-1.8 1.6-2.9 3.8-2.9 1.8 0 3 .8 3.7 2.6" />
    </>
  ),
  reports: (
    <>
      <rect x="5" y="4.5" width="10" height="15" rx="2.4" />
      <path d="M8 9h4" />
      <path d="M8 12h4" />
      <path d="M8 15h4" />
      <path d="M16 7v10" />
      <path d="M16 17h3" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3.1" />
      <path d="M12 4.5v2" />
      <path d="M12 17.5v2" />
      <path d="M4.5 12h2" />
      <path d="M17.5 12h2" />
      <path d="M6.7 6.7l1.4 1.4" />
      <path d="M15.9 15.9l1.4 1.4" />
      <path d="M17.3 6.7l-1.4 1.4" />
      <path d="M8.1 15.9l-1.4 1.4" />
    </>
  ),
  palette: (
    <>
      <path d="M12 4.5c-4.1 0-7.5 3-7.5 6.8 0 4.1 3.3 7.2 7.5 7.2h1.2c1.4 0 2.1.8 2.1 1.8 0 .9-.8 1.7-1.9 1.7-1.8 0-2.6 1.5-1.8 2.8h.1" />
      <circle cx="8.2" cy="9" r="1.1" />
      <circle cx="12" cy="7.8" r="1.1" />
      <circle cx="15.6" cy="9.4" r="1.1" />
      <circle cx="9.5" cy="13.2" r="1.1" />
    </>
  ),
  dots: (
    <>
      <circle cx="12" cy="6.5" r="1.2" />
      <circle cx="12" cy="12" r="1.2" />
      <circle cx="12" cy="17.5" r="1.2" />
    </>
  ),
  chevron: (
    <>
      <path d="M9 6l6 6-6 6" />
    </>
  ),
  layers: (
    <>
      <path d="M12 5 4.5 9l7.5 4 7.5-4-7.5-4Z" />
      <path d="M4.5 13l7.5 4 7.5-4" />
      <path d="M4.5 17l7.5 4 7.5-4" />
    </>
  ),
  minus: (
    <>
      <path d="M5 12h14" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="7" />
      <path d="M14.7 9.3 10 10.5 9.3 15.2 14 14l.7-4.7Z" />
    </>
  ),
  pin: (
    <>
      <path d="M12 21s5-5.2 5-10a5 5 0 1 0-10 0c0 4.8 5 10 5 10Z" />
      <circle cx="12" cy="11" r="2.1" />
    </>
  ),
  chart: (
    <>
      <path d="M5 18h14" />
      <path d="M7 15V10" />
      <path d="M12 15V7" />
      <path d="M17 15V12" />
    </>
  ),
  thermometer: (
    <>
      <path d="M12 4.5v9" />
      <path d="M12 18a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
      <path d="M10 4.5h4" />
    </>
  ),
  droplet: (
    <>
      <path d="M12 4.5c2.9 3.6 5.8 6.8 5.8 10.2a5.8 5.8 0 1 1-11.6 0C6.2 11.3 9.1 8.1 12 4.5Z" />
    </>
  ),
  notebook: (
    <>
      <path d="M6 4.5h11.5a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2Z" />
      <path d="M8.5 4.5v15" />
      <path d="M11 8h5" />
      <path d="M11 12h5" />
      <path d="M11 16h3" />
    </>
  ),
  camera: (
    <>
      <rect x="4.5" y="7" width="15" height="11" rx="3" />
      <path d="M9 7l1.2-2h3.6L15 7" />
      <circle cx="12" cy="12.5" r="3.1" />
    </>
  ),
  phone: (
    <>
      <rect x="7" y="3.5" width="10" height="17" rx="2.5" />
      <path d="M10 6.5h4" />
      <circle cx="12" cy="17.5" r="0.8" />
    </>
  ),
  alert: (
    <>
      <path d="M12 5 20 19H4L12 5Z" />
      <path d="M12 9v4" />
      <path d="M12 16.2h.01" />
    </>
  ),
  water: (
    <>
      <path d="M12 4.5c2.9 3.6 5.8 6.8 5.8 10.2a5.8 5.8 0 1 1-11.6 0C6.2 11.3 9.1 8.1 12 4.5Z" />
    </>
  ),
  arrow: (
    <>
      <path d="M5 12h13" />
      <path d="M13 6l5 6-5 6" />
    </>
  ),
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof iconGlyphs;

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={`garden-icon ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {iconGlyphs[name]}
    </svg>
  );
}
