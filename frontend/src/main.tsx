import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { api } from "./api";
import { installCopilot } from "./copilot-context";
import "./hoard-theme.css";
import "./index.css";

installCopilot({ getPhoto: api.getPhoto, getEdits: api.getEdits, getAlbum: api.getAlbum, getVideo: api.getVideo });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
