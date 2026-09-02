import Topbar from "./Topbar.jsx";
import MenuBar from "./MenuBar.jsx";
import "./AppShell.css";

/**
 * The Phase 0 app shell: Topbar + MenuBar chrome, wrapping a page-head
 * (eyebrow/title/sub/actions) + whatever content the page passes as
 * children. `menuItems` is required — deciding what the nav shows is the
 * caller's job (App.jsx today; a router later), not this component's.
 * `footer` is optional, rendered full-width below `<main>` (outside its
 * padding) rather than as part of `children` — DashboardPage uses it for
 * SiteFooter, matching the login page's footer/disclaimer edge-to-edge.
 */
function AppShell({ menuItems, eyebrow, title, subtitle, actions, children, footer }) {
  return (
    <div className="ec-app">
      <Topbar />
      <MenuBar items={menuItems} />
      <main className="ec-page">
        <div className="ec-page-head">
          <div>
            {eyebrow && <div className="ec-eyebrow">{eyebrow}</div>}
            <h1 className="ec-page-title">{title}</h1>
            {subtitle && <p className="ec-page-sub">{subtitle}</p>}
          </div>
          {actions && <div className="ec-page-actions">{actions}</div>}
        </div>
        {children}
      </main>
      {footer}
    </div>
  );
}

export default AppShell;
