import { useEffect, useRef, useState } from "react";
import Topbar from "./Topbar.jsx";
import "./AppShell.css";

// Must track tokens.css's --ec-topbar-h (52px) — IntersectionObserver's
// rootMargin can't read a CSS custom property, so this shrinks the
// observed viewport from the top by the same amount Topbar's sticky
// height already covers, meaning the frozen title flips on exactly when
// the real <h1> passes behind Topbar, not some arbitrary scroll distance.
const STICKY_TITLE_ROOT_MARGIN = "-52px 0px 0px 0px";

/**
 * The Phase 0 app shell: Topbar chrome, wrapping a page-head
 * (eyebrow/title/sub/actions) + whatever content the page passes as
 * children. `footer` is optional, rendered full-width below `<main>`
 * (outside its padding) rather than as part of `children` — DashboardPage
 * uses it for SiteFooter, matching the login page's footer/disclaimer
 * edge-to-edge. `sidebar` is also optional — when given, `children`
 * renders beside it (SearchPage uses it for its filter pane) instead of
 * taking the full page width. `titleIcon`, when given, renders to the
 * left of the eyebrow/title/subtitle block (e.g. HoldingTickerPage's
 * website favicon) — it's the caller's job to only pass it once whatever
 * the icon depends on has resolved. `titleBadges`, when given, renders
 * below the subtitle (e.g. HoldingTickerPage's Exchange/Quote type
 * Badges).
 *
 * `greeting`, when given, renders as its own centered row above the whole
 * page-head — title *and* `actions` (e.g. DashboardPage's "View all
 * accounts" button) — rather than being scoped to the title column
 * (DashboardPage's random time-of-day welcome message).
 *
 * `stickyTitle`, when true, watches the real `<h1>` with an
 * IntersectionObserver and fades/slides in a fixed bar under Topbar
 * showing `title` once the real one scrolls out of view (and back out
 * once you scroll back up to it) — used by the three detail pages
 * (AccountDetailPage, PieDetailPage, HoldingTickerPage) so the entity's
 * name stays visible while scrolling through a long page. Off by default;
 * every other page just has nothing in that space now that MenuBar (nav
 * with no real destinations beyond the logo-linked Dashboard) is gone.
 *
 * `narrow`, when true, caps `.ec-page` at a readable text-column width
 * instead of the usual 1120px — used by PrivacyPolicyPage/
 * TermsAndConditionsPage so a signed-in visitor's page-head (title/
 * subtitle) and prose body share one centered column, same as the
 * standalone signed-out layout, rather than a full-width dashboard-style
 * page.
 *
 * `centerTitle`, when true, centers the page-head instead of its usual
 * left-aligned/space-between layout — used by NotFoundPage/
 * ServiceUnavailablePage so `title` lines up with their own centered
 * icon/message/action body underneath, rather than sitting flush left
 * above centered content.
 */
function AppShell({
  greeting,
  eyebrow,
  title,
  subtitle,
  titleIcon,
  titleBadges,
  actions,
  children,
  footer,
  sidebar,
  stickyTitle = false,
  narrow = false,
  centerTitle = false,
}) {
  const titleRef = useRef(null);
  const [isTitleFrozen, setIsTitleFrozen] = useState(false);

  useEffect(() => {
    if (!stickyTitle || !titleRef.current) return undefined;
    const observer = new IntersectionObserver(
      ([entry]) => setIsTitleFrozen(!entry.isIntersecting),
      { rootMargin: STICKY_TITLE_ROOT_MARGIN }
    );
    observer.observe(titleRef.current);
    return () => observer.disconnect();
  }, [stickyTitle]);

  return (
    <div className="ec-app">
      <Topbar />
      {stickyTitle && (
        <div className={`ec-frozen-title${isTitleFrozen ? " is-visible" : ""}`} aria-hidden={!isTitleFrozen}>
          {title}
        </div>
      )}
      <main className={`ec-page${narrow ? " ec-page--narrow" : ""}`}>
        {greeting && <div className="ec-page-greeting">{greeting}</div>}
        <div className={`ec-page-head${centerTitle ? " ec-page-head--center" : ""}`}>
          <div className="ec-page-head-main">
            {titleIcon && <div className="ec-page-title-icon">{titleIcon}</div>}
            <div>
              {eyebrow && <div className="ec-eyebrow">{eyebrow}</div>}
              <h1 className="ec-page-title" ref={titleRef}>
                {title}
              </h1>
              {subtitle && <p className="ec-page-sub">{subtitle}</p>}
              {titleBadges && <div className="ec-page-title-badges">{titleBadges}</div>}
            </div>
          </div>
          {actions && <div className="ec-page-actions">{actions}</div>}
        </div>
        {sidebar ? (
          <div className="ec-page-with-sidebar">
            <aside className="ec-page-sidebar">{sidebar}</aside>
            <div className="ec-page-content">{children}</div>
          </div>
        ) : (
          children
        )}
      </main>
      {footer}
    </div>
  );
}

export default AppShell;
