/**
 * Shared MenuBar config for every authenticated page. "Portfolio" is the
 * only item with a real destination so far (`to` routes it via MenuBar's
 * NavLink branch) — Watchlists/Search stay inert placeholders (MenuBar's
 * plain-button branch) until those phases exist.
 */
export const MENU_ITEMS = [
  { id: "portfolio", label: "Portfolio", to: "/accounts" },
  { id: "watchlists", label: "Watchlists" },
  { id: "search", label: "Search" },
];
