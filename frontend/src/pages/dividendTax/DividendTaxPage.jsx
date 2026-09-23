import { useEffect, useState } from "react";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import DividendAllowanceCard from "./DividendAllowanceCard.jsx";
import { useApi } from "../../api/useApi.js";
import { getMe } from "../../api/identity.js";
import { formatCurrency } from "../sampleFinancials.js";
import { UK_DIVIDEND_ALLOWANCE, currentUkTaxYearLabel, sortedDividendTaxRows } from "./dividendTaxFinancials.js";

/**
 * The dividend allowance page (GitHub issue #212) — reached from the user
 * menu (see Topbar.jsx). Shows this UK tax year's allowance usage at a
 * glance (DividendAllowanceCard, previously on DashboardPage — moved here
 * outright rather than duplicated) plus every tax year's allowance/tax
 * usage below it.
 *
 * Fetches its own fresh `GET /identity/me/` on every mount, deliberately
 * bypassing useCurrentUser()'s sessionStorage cache — `dividend_allowance_
 * used_by_tax_year`/`dividend_tax_paid_by_tax_year` change server-side as a
 * side effect of creating a holding/transaction elsewhere (the backend's
 * own dividend sync + allowance/tax bookkeeping, see
 * backend/transactions/views.py's _persist_dividend_allowance), never
 * through a `setProfile` call on this side, so the cached profile snapshot
 * useCurrentUser() serves everywhere else would otherwise show this page a
 * stale figure for the rest of the tab session. useCurrentUser()'s cache
 * itself is untouched — this page just doesn't use it.
 */
function DividendTaxPage() {
  const api = useApi();
  const [dividendAllowanceUsedByTaxYear, setDividendAllowanceUsedByTaxYear] = useState(undefined);
  const [dividendTaxPaidByTaxYear, setDividendTaxPaidByTaxYear] = useState(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    getMe(api)
      .then((profile) => {
        if (cancelled) return;
        setDividendAllowanceUsedByTaxYear(profile.dividend_allowance_used_by_tax_year);
        setDividendTaxPaidByTaxYear(profile.dividend_tax_paid_by_tax_year);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? "Couldn't load your dividend allowance.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  const currentTaxYear = currentUkTaxYearLabel();
  const rows = sortedDividendTaxRows(dividendAllowanceUsedByTaxYear, dividendTaxPaidByTaxYear);

  return (
    <AppShell
      eyebrow="Portfolio"
      title="Dividend allowance"
      subtitle="Your UK dividend allowance usage, by tax year."
      footer={<SiteFooter />}
    >
      {isLoading && <p className="ec-chart-caption">Loading…</p>}
      {error && <Alert tone="danger">{error}</Alert>}

      {!isLoading && !error && (
        <DividendAllowanceCard dividendAllowanceUsedByTaxYear={dividendAllowanceUsedByTaxYear} />
      )}

      {!isLoading && !error && rows.length === 0 && (
        <EmptyState
          title="No dividend tax activity yet"
          description="Once a taxable (GIA) holding records a dividend, its allowance usage shows up here."
        />
      )}

      {!isLoading && !error && rows.length > 0 && (
        <div className="ec-table-wrap" style={{ marginTop: "var(--ec-s-24)" }}>
          <table className="ec-table">
            <thead>
              <tr>
                <th>Tax year</th>
                <th>Allowance used</th>
                <th>% of allowance</th>
                <th>Remaining</th>
                <th>Tax deducted</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ taxYear, allowanceUsed, taxPaid }) => {
                const pct = (allowanceUsed / UK_DIVIDEND_ALLOWANCE) * 100;
                const remaining = Math.max(0, UK_DIVIDEND_ALLOWANCE - allowanceUsed);
                return (
                  <tr key={taxYear}>
                    <td>
                      {taxYear} {taxYear === currentTaxYear && <Badge tone="accent">Current</Badge>}
                    </td>
                    <td>
                      <Balance>{formatCurrency(allowanceUsed, "GBP")}</Balance>
                    </td>
                    <td>{pct >= 100 ? "Over allowance" : `${Math.round(pct)}%`}</td>
                    <td>
                      <Balance>{formatCurrency(remaining, "GBP")}</Balance>
                    </td>
                    <td>
                      <Balance>{formatCurrency(taxPaid, "GBP")}</Balance>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}

export default DividendTaxPage;
