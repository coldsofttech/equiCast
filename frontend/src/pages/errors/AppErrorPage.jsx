import { useAuth0 } from "@auth0/auth0-react";
import AppShell from "../../components/shell/AppShell.jsx";
import PublicHeader from "../../components/shell/PublicHeader.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import ErrorBoundary from "../../components/errors/ErrorBoundary.jsx";
import ErrorPage from "../../components/errors/ErrorPage.jsx";
import AppErrorIcon from "../../components/errors/AppErrorIcon.jsx";
import Button from "../../components/core/Button.jsx";
import "../../components/errors/ErrorPage.css";

const TITLE = "Something went wrong";
const MESSAGE = "This page ran into an unexpected error. Reloading usually fixes it.";

function ReloadButton() {
  return (
    <Button variant="primary" onClick={() => window.location.reload()}>
      Reload page
    </Button>
  );
}

/**
 * Rendered by ErrorBoundary in place of a page that crashed while
 * rendering — the fallback of last resort, so a bug shows a plain "this
 * broke" page instead of leaving the tab blank. Reached whether or not the
 * user is signed in (ErrorBoundary wraps App.jsx's whole route tree, above
 * RequireAuth), so which chrome renders is picked the same way
 * PrivacyPolicyPage/TermsAndConditionsPage already do: `isAuthenticated`
 * gets the normal AppShell/SiteFooter chrome, same as NotFoundPage/
 * ServiceUnavailablePage; a signed-out visitor (e.g. the public landing
 * page's demo chart failing to load — GitHub issue #213) gets `PublicHeader`
 * instead, so the logged-in-only search box and account menu never show up
 * for someone who was never signed in to begin with.
 *
 * The crash that brought down the page being replaced could, in principle,
 * have originated inside Topbar itself — Topbar renders on every one of
 * those pages too, and ErrorBoundary catches a crash anywhere in the tree.
 * Re-rendering that same Topbar here would just crash again, and a second
 * crash during this fallback's own render isn't caught by the boundary
 * that already fired — so AppShell/Topbar/SiteFooter are wrapped in their
 * own nested ErrorBoundary, falling back to the bare standalone ErrorPage
 * (no Topbar/footer, just the icon/message/reload button) if that happens.
 * PublicHeader carries no such risk — it's a static logo/theme-toggle row
 * with no data fetching, same as every other signed-out page that uses it.
 */
function AppErrorPage() {
  const { isAuthenticated } = useAuth0();

  const body = (
    <div className="ec-errorpage-body">
      <div className="ec-errorpage-icon" aria-hidden="true">
        <AppErrorIcon />
      </div>
      <p className="ec-errorpage-message">{MESSAGE}</p>
      <div className="ec-errorpage-action">
        <ReloadButton />
      </div>
    </div>
  );

  if (isAuthenticated) {
    return (
      <ErrorBoundary
        fallback={<ErrorPage icon={<AppErrorIcon />} title={TITLE} message={MESSAGE} action={<ReloadButton />} />}
      >
        <AppShell narrow centerTitle title={TITLE} footer={<SiteFooter />}>
          {body}
        </AppShell>
      </ErrorBoundary>
    );
  }

  return (
    <div className="ec-errorpage-public">
      <PublicHeader />
      <div className="ec-errorpage-body">
        <div className="ec-errorpage-icon" aria-hidden="true">
          <AppErrorIcon />
        </div>
        <h1 className="ec-errorpage-title">{TITLE}</h1>
        <p className="ec-errorpage-message">{MESSAGE}</p>
        <div className="ec-errorpage-action">
          <ReloadButton />
        </div>
      </div>
      <SiteFooter />
    </div>
  );
}

export default AppErrorPage;
