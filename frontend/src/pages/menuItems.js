/**
 * Shared MenuBar config for every authenticated page. Dashboard is the
 * only item with a real destination so far (`to` routes it via MenuBar's
 * NavLink branch) — Watchlists stays an inert placeholder (MenuBar's
 * plain-button branch) until that phase exists. Accounts isn't here: it
 * lives in UserMenu's account dropdown instead (see Topbar/UserMenu.jsx),
 * reached from there or from a Dashboard account card. Search isn't here
 * either — it's reached via TopbarSearch (Enter routes to /search?q=...)
 * rather than a MenuBar entry.
 */
export const MENU_ITEMS = [
  { id: "dashboard", label: "Dashboard", to: "/dashboard" },
  { id: "watchlists", label: "Watchlists" },
];
