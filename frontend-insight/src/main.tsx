import React from "react";
import ReactDOM from "react-dom/client";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import App from "./App";
import "./index.css";

applyColorScheme(readStoredColorScheme());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
