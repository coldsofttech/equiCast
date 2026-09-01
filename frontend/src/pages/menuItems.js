/**
 * Shared MenuBar config for every authenticated page. Dashboard is the
 * only item with a real destination so far (`to` routes it via MenuBar's
 * NavLink branch) — Watchlists/Search stay inert placeholders (MenuBar's
 * plain-button branch) until those phases exist. Accounts isn't here: it
 * lives in UserMenu's account dropdown instead (see Topbar/UserMenu.jsx),
 * reached from there or from a Dashboard account card.
 */
export const MENU_ITEMS = [
  { id: "dashboard", label: "Dashboard", to: "/dashboard" },
  { id: "watchlists", label: "Watchlists" },
  { id: "search", label: "Search" },
];
