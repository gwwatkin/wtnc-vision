// browser.js — Frame browser sidebar mode (stub; implemented by task8).
//
// Exports:
//   openBrowser({ run, centerTs })
//     → renders frame-browser mode into #sidebar-content (opens #sidebar if
//       closed); centerTs: ISO string anchor, or null ⇒ anchor at meta.last_ts.

/**
 * Open the frame browser in the sidebar.
 *
 * @param {{ run: string, centerTs: string|null }} opts
 */
export function openBrowser({ run, centerTs }) {
  // stub — render a placeholder so the page keeps working today (task1 §)
  const sidebarContent = document.getElementById("sidebar-content");
  const sidebar = document.getElementById("sidebar");

  if (!sidebarContent || !sidebar) return;

  sidebarContent.innerHTML =
    '<p style="color:#666;font-size:0.9rem;padding:1rem 0;">' +
    "Frame browser not available yet." +
    "</p>";

  sidebar.removeAttribute("hidden");
}
