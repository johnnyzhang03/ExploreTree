import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { McpBridgeProvider } from "./McpBridge.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <McpBridgeProvider>
    <App />
  </McpBridgeProvider>
);
