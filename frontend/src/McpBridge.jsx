import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useApp } from "@modelcontextprotocol/ext-apps/react";

const McpBridgeContext = createContext(null);

export function McpBridgeProvider({ children }) {
  const embedded = window.parent !== window;
  const [toolData, setToolData] = useState(null);
  const [theme, setTheme] = useState("light");
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [containerHeight, setContainerHeight] = useState(null);

  const { app, isConnected } = useApp({
    appInfo: { name: "ExploreTree", version: "1.0.0" },
    capabilities: { availableDisplayModes: ["inline", "fullscreen"] },
    onAppCreated: (createdApp) => {
      createdApp.ontoolresult = (result) => {
        if (result?.structuredContent) {
          setToolData(result.structuredContent);
        }
      };
      createdApp.onhostcontextchanged = (context) => {
        if (context?.theme) setTheme(context.theme === "dark" ? "dark" : "light");
        if (context?.displayMode) {
          setIsFullscreen(context.displayMode === "fullscreen");
        }
        const height =
          context?.containerDimensions?.maxHeight ??
          context?.containerDimensions?.height;
        if (Number.isFinite(height) && height > 0) {
          setContainerHeight(height);
        }
      };
    },
  });

  useEffect(() => {
    if (!app || !isConnected) return;
    const context = app.getHostContext();
    if (context?.theme) setTheme(context.theme === "dark" ? "dark" : "light");
    if (context?.displayMode) {
      setIsFullscreen(context.displayMode === "fullscreen");
    }
    const height =
      context?.containerDimensions?.maxHeight ??
      context?.containerDimensions?.height;
    if (Number.isFinite(height) && height > 0) {
      setContainerHeight(height);
    }
  }, [app, isConnected]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const callTool = useCallback(
    async (name, args = {}) => {
      if (!app || !isConnected) {
        throw new Error("The MCP host connection is not ready.");
      }
      const result = await app.callServerTool({ name, arguments: args });
      if (result.isError) {
        const message = result.content
          ?.filter((item) => item.type === "text")
          .map((item) => item.text)
          .join("") || "Tool call failed.";
        throw new Error(message);
      }
      return result.structuredContent;
    },
    [app, isConnected]
  );

  const openExternal = useCallback(
    (url) => {
      if (!url) return;
      if (app && isConnected && typeof app.openLink === "function") {
        app.openLink({ url });
        return;
      }
      window.open(url, "_blank", "noopener,noreferrer");
    },
    [app, isConnected]
  );

  const toggleFullscreen = useCallback(async () => {
    if (!app || !isConnected || typeof app.requestDisplayMode !== "function") {
      return;
    }
    const mode = isFullscreen ? "inline" : "fullscreen";
    const result = await app.requestDisplayMode({ mode });
    setIsFullscreen(result.mode === "fullscreen");
  }, [app, isConnected, isFullscreen]);

  const updateModelContext = useCallback(
    async (text, structuredContent) => {
      if (!app || !isConnected || typeof app.updateModelContext !== "function") {
        throw new Error("The MCP host does not support model context updates.");
      }
      await app.updateModelContext({
        content: [{ type: "text", text }],
        structuredContent,
      });
    },
    [app, isConnected]
  );

  const sendMessage = useCallback(
    async (text) => {
      if (!app || !isConnected || typeof app.sendMessage !== "function") {
        throw new Error("The MCP host does not support follow-up messages.");
      }
      const result = await app.sendMessage({
        role: "user",
        content: [{ type: "text", text }],
      });
      if (result?.isError) {
        throw new Error("The MCP host rejected the follow-up message.");
      }
    },
    [app, isConnected]
  );

  useEffect(() => {
    if (!app || !isConnected || typeof app.sendSizeChanged !== "function") return;
    let timer;
    const notifySize = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        app.sendSizeChanged({
          width: document.documentElement.scrollWidth,
          height: document.documentElement.scrollHeight,
        });
      }, 100);
    };
    const observer = new ResizeObserver(notifySize);
    observer.observe(document.body);
    notifySize();
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [app, isConnected]);

  const canFullscreen =
    !!(app && isConnected && typeof app.requestDisplayMode === "function");

  return (
    <McpBridgeContext.Provider
      value={{
        embedded,
        toolData,
        isConnected,
        isFullscreen,
        containerHeight,
        canFullscreen,
        callTool,
        openExternal,
        toggleFullscreen,
        updateModelContext,
        sendMessage,
      }}
    >
      {children}
    </McpBridgeContext.Provider>
  );
}

export function useMcpBridge() {
  const context = useContext(McpBridgeContext);
  if (!context) {
    throw new Error("useMcpBridge must be used within McpBridgeProvider.");
  }
  return context;
}
