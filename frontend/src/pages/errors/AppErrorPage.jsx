import ErrorPage from "../../components/errors/ErrorPage.jsx";
import AppErrorIcon from "../../components/errors/AppErrorIcon.jsx";
import Button from "../../components/core/Button.jsx";

/** Rendered by ErrorBoundary in place of a page that crashed while
 * rendering — the fallback of last resort, so a bug shows a plain "this
 * broke" page instead of leaving the tab blank. */
function AppErrorPage() {
  return (
    <ErrorPage
      icon={<AppErrorIcon />}
      title="Something went wrong"
      message="This page ran into an unexpected error. Reloading usually fixes it."
      action={
        <Button variant="primary" onClick={() => window.location.reload()}>
          Reload page
        </Button>
      }
    />
  );
}

export default AppErrorPage;
