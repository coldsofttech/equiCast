import ComingSoonPage from "../ComingSoonPage.jsx";

/**
 * Placeholder for GitHub issue #170's "Goals" menu entry — unlike
 * Watchlists, there's no Goals backend on `main` at all yet (an earlier
 * feat/goals branch built one but was never merged), so this is a plain
 * placeholder pending that work being taken up as its own issue.
 */
function GoalsPage() {
  return (
    <ComingSoonPage
      eyebrow="Goals"
      title="Goals"
      icon="bi-flag"
      message="Set savings targets against your accounts and pies, and track your progress toward them. This page is on its way."
    />
  );
}

export default GoalsPage;
