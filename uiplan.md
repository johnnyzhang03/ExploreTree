# ExploreTree UI/UX Improvement Plan

Based on Microsoft's [User experience guidelines for MCP apps in declarative agents for Microsoft 365 Copilot](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-mcp-apps-ui-guidelines).

## 1. Separate inline and expanded experiences

- Replace the current 720px embedded mini-application with a concise inline widget.
- Show the research question, progress or completion state, coverage, and a few top-level branches.
- Limit inline actions to two.
- Remove map switching, breadcrumbs, media, and detail navigation from inline mode.
- Keep Cards, Map, sources, media, expansion, and branch details in the SDK's expanded/fullscreen mode.

## 2. Adopt Fluent 2

- Add Fluent React components and icons.
- Use host-aware light and dark themes.
- Apply Fluent typography, spacing tokens, radii, focus styles, and 24px card padding.
- Replace the current Google-style colors and custom controls.

## 3. Improve information hierarchy

- Make the research question and current state immediately clear.
- Present structured progress and evidence coverage without duplicating Copilot's response.
- Surface evidence gaps prominently but calmly.

## 4. Make every state explicit

- Introduce consistent connecting, planning, researching, updating, completed, disconnected, and error states.
- Disable unavailable actions.
- Provide clear success and error feedback with recovery actions.
- Replace generic top-bar status text with contextual widget feedback.

## 5. Refine the expanded workspace

- Add an agent header, active-task context, exit control, and an "Open in ExploreTree" handoff.
- Preserve Cards and Map as contextual visualization controls.
- Simplify the detail panel.
- Prioritize insight, evidence, sources, then optional media and actions.

## 6. Improve accessibility and responsive behavior

- Add keyboard support to cards and D3 nodes.
- Use semantic buttons and accessible labels.
- Add live status announcements and focus management.
- Respect reduced-motion preferences.
- Ensure inline mode remains glanceable without internal scrolling at narrow widths.

## 7. Restructure implementation

- Split `frontend/src/App.jsx` into focused inline-widget, expanded-workspace, status, and detail components.
- Update `frontend/src/McpBridge.jsx` for Fluent theming and display-mode handling.
- Add the full-application handoff URL to the MCP structured payload in `backend/app/mcp_server.py`.
- Preserve the existing standalone application behavior.
