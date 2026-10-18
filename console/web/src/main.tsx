import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { browserTransport, Client } from "./app/client";
import "./app/shell.css";

const client = new Client(browserTransport, window.location.hostname);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App client={client} />
  </StrictMode>,
);
