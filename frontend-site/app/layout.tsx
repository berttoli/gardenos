import type { ReactNode } from "react";
import { ThemeAppearanceProvider } from "./garden/theme/theme-provider";

export default function RootLayout({ children }: { children: ReactNode }) {
  return <ThemeAppearanceProvider>{children}</ThemeAppearanceProvider>;
}
