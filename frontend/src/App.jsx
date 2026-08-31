import AppShell from "./components/shell/AppShell.jsx";
import "./App.css";

const MENU_ITEMS = [
  { id: "portfolio", label: "Portfolio" },
  { id: "watchlists", label: "Watchlists" },
  { id: "search", label: "Search" },
];

function App() {
  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Phase 0"
      title="App shell"
      subtitle="Design tokens and the topbar/menubar shell are wired up — accounts, pies, holdings, and everything else come in later phases."
    >
      <div className="ec-placeholder">
        <p>Domain pages aren&rsquo;t built yet.</p>
      </div>
    </AppShell>
  );
}

export default App;
