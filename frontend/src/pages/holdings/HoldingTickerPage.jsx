import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Card from "../../components/core/Card.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import { useAccounts } from "../../api/useAccounts.js";
import { MENU_ITEMS } from "../menuItems.js";
import { formatCurrency, TICKER_NAMES, buildHoldingSample, plTone } from "../sampleFinancials.js";

/**
 * Every "instance" of one ticker across the signed-in user's whole
 * portfolio — the same ticker can be held directly in more than one
 * account, and again inside one or more pies, each as its own separate
 * holding record (own id, own transactions, possibly a different
 * account currency). Reached by clicking a holding card on
 * AccountDetailPage. Reads from the same session-cached accounts list
 * (see useAccounts.js) the Dashboard/Accounts pages use, rather than a
 * dedicated endpoint — there's no per-ticker API yet, and the cached list
 * already carries every account's nested pies/holdings.
 */
function HoldingTickerPage() {
  const { ticker } = useParams();
  const navigate = useNavigate();
  const { accounts, isLoading, error } = useAccounts();

  const instances = useMemo(() => {
    const list = [];
    for (const account of accounts) {
      for (const holding of account.holdings ?? []) {
        if (holding.ticker !== ticker) continue;
        list.push({
          holding,
          location: account.name,
          destination: `/accounts/${account.id}`,
          currency: account.currency,
          sample: buildHoldingSample(holding.id),
        });
      }
      for (const pie of account.pies ?? []) {
        for (const holding of pie.holdings ?? []) {
          if (holding.ticker !== ticker) continue;
          list.push({
            holding,
            location: `${account.name} / ${pie.name}`,
            destination: `/accounts/${account.id}/pies/${pie.id}`,
            currency: account.currency,
            sample: buildHoldingSample(holding.id),
          });
        }
      }
    }
    return list;
  }, [accounts, ticker]);

  const totalShares = instances.reduce((sum, inst) => sum + inst.sample.shares, 0);
  const name = TICKER_NAMES[ticker];

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Holding"
      title={name ? `${name} (${ticker})` : ticker}
      subtitle={
        instances.length > 0
          ? `Held in ${instances.length} place${instances.length === 1 ? "" : "s"} across your accounts — ${totalShares} shares in total (sample).`
          : undefined
      }
      footer={<SiteFooter />}
    >
      {isLoading && <p className="ec-loading">Loading…</p>}
      {error && <Alert tone="danger">{error}</Alert>}

      {!isLoading && !error && instances.length === 0 && (
        <EmptyState
          title={`No holdings of ${ticker}`}
          description="This ticker isn't held directly or inside a pie in any of your accounts."
        />
      )}

      {!isLoading && !error && instances.length > 0 && (
        <>
          <div className="ec-detail-row-list">
            {instances.map((inst) => {
              const tone = plTone(inst.sample.plPct);
              const plSign = inst.sample.plValue >= 0 ? "+" : "-";
              return (
                <Card
                  key={inst.holding.id}
                  className="ec-detail-row ec-detail-row--clickable"
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(inst.destination)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      navigate(inst.destination);
                    }
                  }}
                >
                  <div className="ec-detail-row-main">
                    <h3 className="ec-detail-row-name">{inst.location}</h3>
                    <span className="ec-detail-row-meta">{inst.sample.shares} shares</span>
                  </div>
                  <div className="ec-detail-row-value">
                    <span className="ec-detail-row-current">
                      {formatCurrency(inst.sample.currentValue, inst.currency)}
                    </span>
                    <span className={`ec-detail-row-pl ${tone}`}>
                      {plSign}
                      {formatCurrency(Math.abs(inst.sample.plValue), inst.currency)} ({plSign}
                      {Math.abs(inst.sample.plPct).toFixed(1)}%)
                    </span>
                  </div>
                </Card>
              );
            })}
          </div>

          <p className="ec-chart-caption">
            Sample data — share counts, values and P&amp;L shown here are illustrative, not
            pulled from real pricing yet. Totals aren&rsquo;t summed across instances in
            different currencies.
          </p>
        </>
      )}
    </AppShell>
  );
}

export default HoldingTickerPage;
