import { useNavigate } from "react-router-dom";
import ErrorPage from "../../components/errors/ErrorPage.jsx";
import NotFoundIcon from "../../components/errors/NotFoundIcon.jsx";
import Button from "../../components/core/Button.jsx";

/** Shown for any route that doesn't match one of App.jsx's own — replaces
 * the previous silent redirect-to-dashboard, so a bad/stale link actually
 * says so instead of quietly landing somewhere else. */
function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <ErrorPage
      icon={<NotFoundIcon />}
      title="Page not found"
      message="There's nothing here. The page may have moved, or the link might be out of date."
      action={
        <Button variant="primary" onClick={() => navigate("/dashboard")}>
          Back to dashboard
        </Button>
      }
    />
  );
}

export default NotFoundPage;
