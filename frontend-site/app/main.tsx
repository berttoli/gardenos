import { createRoot } from "react-dom/client";
import RootLayout from "./layout";
import Dashboard from "./page";
import "./globals.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("The application root is missing.");
}

createRoot(container).render(
  <RootLayout>
    <Dashboard />
  </RootLayout>,
);
