import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { applyColorScheme, readStoredColorScheme } from "@ch2/macro-shell/displayUi";
import App from "./App";
import TwinExperimentLab from "./components/TwinExperimentLab";
import { isTwinLabRequested } from "./api/twinLabClient";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const qc = new QueryClient();

function Root() {
  const [labOpen, setLabOpen] = useState(() => isTwinLabRequested());

  if (labOpen) {
    return (
      <TwinExperimentLab
        onClose={() => {
          setLabOpen(false);
          const url = new URL(window.location.href);
          url.searchParams.delete("lab");
          window.history.replaceState({}, "", url.pathname + url.search);
        }}
      />
    );
  }
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <Root />
    </QueryClientProvider>
  </React.StrictMode>,
);
