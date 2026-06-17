import "@fontsource-variable/bricolage-grotesque/index.css";
import "@fontsource/space-mono/400.css";
import "@fontsource/space-mono/700.css";
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.tsx";
import { initTheme } from "./lib/theme.ts";
import "./index.css";
import "./theme.css";

// Apply the persisted theme before first paint so there's no flash.
initTheme();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root not found");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
