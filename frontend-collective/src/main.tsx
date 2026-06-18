import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import CommercialApp from "./CommercialApp";
import CollectiveLanding from "./CollectiveLanding";
import BuildingRegressionPage from "./pages/BuildingRegressionPage";
import { getCollectiveSegment, redirectToCollectiveSubpath } from "./routing";
import { applyColorScheme, readStoredColorScheme } from "./constants/displayUi";
import "./index.css";

applyColorScheme(readStoredColorScheme());

const qc = new QueryClient();

function Root() {
  const view = new URLSearchParams(window.location.search).get("view");

  if (view === "commercial") {
    redirectToCollectiveSubpath("commercial");
    return null;
  }

  if (view === "regression") {
    return <BuildingRegressionPage />;
  }

  const segment = getCollectiveSegment();
  if (segment === "residential") return <App />;
  if (segment === "commercial") return <CommercialApp />;
  return <CollectiveLanding />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <Root />
    </QueryClientProvider>
  </React.StrictMode>,
);
