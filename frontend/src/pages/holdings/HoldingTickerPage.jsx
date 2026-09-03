import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import StatTile from "../../components/core/StatTile.jsx";
import PriceChart from "../accounts/PriceChart.jsx";
import HoldingInstancesTable from "./HoldingInstancesTable.jsx";
import HoldingStatsPanel from "./HoldingStatsPanel.jsx";
import HoldingAboutSection from "./HoldingAboutSection.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import { getProfile, getPrices } from "../../api/market.js";
import { listTransactions } from "../../api/transactions.js";
import { deleteHolding } from "../../api/holdings.js";
import { MENU_ITEMS } from "../menuItems.js";
import { TICKER_NAMES, formatCurrency, plTone } from "../sampleFinancials.js";
import { deriveInstanceFinancials, resolveFxRate, rollupInstances } from "./holdingFinancials.js";
import "./HoldingTickerPage.css";

/** formatCurrency requires a currency code — this page's totals are real,
 * computed from transactions, and available even before/without a market
 * profile (e.g. a 404'd ticker), so unlike every other page's StatTiles
 * this can't assume a currency is always known by the time it renders. */
function formatMoney(value, currency) {
  if (currency) return formatCurrency(value, currency);
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

/**
 * The full holding detail page for one ticker: real Total invested/P&L/P&L%
 * (rolled up from every instance's recorded transactions plus the
 * instrument's real current price — see holdingFinancials.js), the same
 * illustrative consolidated chart pattern account/pie pages use (now also
 * offering other holdings as a compare option), a per-instance shares/avg
 * price table with delete, a two-pane stats section, and an About section —
 * both real data from the market profile endpoint where it exists, with the
 * handful of fields the backend doesn't expose yet (P/E, volatility,
 * average volume, dividend frequency) shown as clearly-hinted placeholders.
 *
 * Reached by ticker, not holding id — the same ticker can be a separate
 * holding record directly in an account and/or inside one or more pies
 * (see the `instances` memo below), so this page aggregates every one of
 * them rather than assuming just one.
 */
function HoldingTickerPage() {
  const { ticker } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { accounts, isLoading, error, setAccounts: setCachedAccounts } = useAccounts();
  const { profile: userProfile } = useCurrentUser();

  const [marketProfile, setMarketProfile] = useState(null);
  const [marketProfileStatus, setMarketProfileStatus] = useState("loading");
  const [priceResults, setPriceResults] = useState(null);
  const [transactionsByHolding, setTransactionsByHolding] = useState({});
  const [isDataLoading, setIsDataLoading] = useState(true);

  const [fxRate, setFxRate] = useState(null);
  const [fxState, setFxState] = useState("loading");

  const [isFinancialsOpen, setIsFinancialsOpen] = useState(false);
  const [isTransactionsOpen, setIsTransactionsOpen] = useState(false);

  const [deletingInstance, setDeletingInstance] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const instances = useMemo(() => {
    const list = [];
    for (const account of accounts) {
      for (const holding of account.holdings ?? []) {
        if (holding.ticker !== ticker) continue;
        list.push({
          holding,
          location: account.name,
          destination: `/accounts/${account.id}`,
          transactionType: account.transaction_type,
        });
      }
      for (const pie of account.pies ?? []) {
        for (const holding of pie.holdings ?? []) {
          if (holding.ticker !== ticker) continue;
          list.push({
            holding,
            location: `${account.name} / ${pie.name}`,
            destination: `/accounts/${account.id}/pies/${pie.id}`,
            transactionType: account.transaction_type,
          });
        }
      }
    }
    return list;
  }, [accounts, ticker]);

  const otherHoldings = useMemo(() => {
    const seen = new Map();
    const addAll = (holdings) => {
      for (const holding of holdings) {
        if (holding.ticker !== ticker && !seen.has(holding.ticker)) {
          seen.set(holding.ticker, {
            id: holding.ticker,
            name: TICKER_NAMES[holding.ticker] ?? holding.ticker,
          });
        }
      }
    };
    for (const account of accounts) {
      addAll(account.holdings ?? []);
      for (const pie of account.pies ?? []) addAll(pie.holdings ?? []);
    }
    return [...seen.values()];
  }, [accounts, ticker]);

  useEffect(() => {
    if (instances.length === 0) {
      setIsDataLoading(false);
      return undefined;
    }

    let cancelled = false;
    setIsDataLoading(true);
    const assetClass = instances[0].holding.asset_class;

    const profilePromise = getProfile(api, assetClass, ticker)
      .then((profile) => ({ status: "ok", profile }))
      .catch((err) => ({ status: err.status === 404 ? "missing" : "error", profile: null }));

    const pricesPromise = getPrices(api, assetClass, ticker)
      .then((res) => res.results)
      .catch(() => null);

    const transactionsPromise = Promise.all(
      instances.map((instance) =>
        listTransactions(api, { holdingId: instance.holding.id })
          .then((transactions) => ({ holdingId: instance.holding.id, transactions, error: false }))
          .catch(() => ({ holdingId: instance.holding.id, transactions: [], error: true }))
      )
    );

    Promise.all([profilePromise, pricesPromise, transactionsPromise]).then(
      ([profileResult, prices, transactionsResults]) => {
        if (cancelled) return;
        setMarketProfileStatus(profileResult.status);
        setMarketProfile(profileResult.profile);
        setPriceResults(prices);
        const map = {};
        for (const result of transactionsResults) map[result.holdingId] = result;
        setTransactionsByHolding(map);
        setIsDataLoading(false);
      }
    );

    return () => {
      cancelled = true;
    };
  }, [api, ticker, instances]);

  useEffect(() => {
    if (!marketProfile || !userProfile) return undefined;
    let cancelled = false;
    setFxState("loading");
    resolveFxRate(api, marketProfile.currency, userProfile.default_currency).then((rate) => {
      if (cancelled) return;
      setFxRate(rate);
      setFxState(rate != null ? "ok" : "unavailable");
    });
    return () => {
      cancelled = true;
    };
  }, [api, marketProfile, userProfile]);

  const removeInstanceFromCache = (holdingId) => {
    setCachedAccounts((current) =>
      current.map((account) => ({
        ...account,
        holdings: (account.holdings ?? []).filter((h) => h.id !== holdingId),
        pies: (account.pies ?? []).map((pie) => ({
          ...pie,
          holdings: (pie.holdings ?? []).filter((h) => h.id !== holdingId),
        })),
      }))
    );
  };

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deleteHolding(api, deletingInstance.holding.id)
      .then(() => {
        removeInstanceFromCache(deletingInstance.holding.id);
        setDeletingInstance(null);
      })
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete this holding."))
      .finally(() => setIsDeleting(false));
  };

  const name = TICKER_NAMES[ticker];

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Holding"
      title={name ?? ticker}
      subtitle={name ? ticker : undefined}
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

      {!isLoading && !error && instances.length > 0 && isDataLoading && (
        <p className="ec-loading">Loading…</p>
      )}

      {!isLoading && !error && instances.length > 0 && !isDataLoading && (
        <>
          {marketProfileStatus === "missing" && (
            <Alert tone="info">
              No real market data is published for {ticker} yet — showing what&rsquo;s available
              from your recorded transactions only.
            </Alert>
          )}

          {(() => {
            const instanceFinancials = instances.map((instance) => {
              const entry = transactionsByHolding[instance.holding.id];
              if (!entry || entry.error) {
                return { ...instance, shares: 0, avgPriceNative: null, invested: 0, transactionsError: Boolean(entry?.error) };
              }
              const financials = deriveInstanceFinancials(entry.transactions, instance.transactionType);
              return { ...instance, ...financials, transactionsError: false };
            });

            const nativeCurrency = marketProfile?.currency ?? null;
            const currentPriceNative = marketProfile?.day_close ?? marketProfile?.day_average ?? null;
            const totals = rollupInstances(instanceFinancials, currentPriceNative);
            const totalsTone = plTone(totals.plPct ?? 0);

            return (
              <>
                {totals.shares > 0 && (
                  <div className="ec-stat-grid">
                    <StatTile
                      label="Total invested"
                      value={formatMoney(totals.invested, nativeCurrency)}
                      hint="Real data"
                    />
                    <StatTile
                      label="Profit / loss"
                      value={
                        totals.plValue != null
                          ? `${totals.plValue >= 0 ? "+" : "-"}${formatMoney(Math.abs(totals.plValue), nativeCurrency)}`
                          : "—"
                      }
                      tone={totalsTone}
                      hint="Real data"
                    />
                    <StatTile
                      label="Profit / loss %"
                      value={totals.plPct != null ? `${totals.plPct >= 0 ? "+" : "-"}${Math.abs(totals.plPct).toFixed(1)}%` : "—"}
                      tone={totalsTone}
                      hint="Real data"
                    />
                  </div>
                )}

                <PriceChart
                  holdings={otherHoldings}
                  seedKey={`holding:${ticker}`}
                  subjectLabel="This holding"
                />

                {totals.shares > 0 && (
                  <>
                    <div className="ec-section-head">
                      <h2 className="ec-section-title">Owned shares</h2>
                    </div>
                    <HoldingInstancesTable
                      instances={instanceFinancials}
                      nativeCurrency={nativeCurrency}
                      defaultCurrency={userProfile?.default_currency ?? null}
                      fxRate={fxRate}
                      fxState={fxState}
                      onDelete={setDeletingInstance}
                      onRowClick={(instance) => navigate(instance.destination)}
                    />
                  </>
                )}
              </>
            );
          })()}

          <div className="ec-account-columns">
            <HoldingStatsPanel ticker={ticker} marketProfile={marketProfile} priceResults={priceResults} />
            <HoldingAboutSection marketProfile={marketProfile} />
          </div>

          <div className="ec-holding-actions-row">
            <Button variant="secondary" onClick={() => setIsFinancialsOpen(true)}>
              Financials
            </Button>
            <Button variant="secondary" onClick={() => setIsTransactionsOpen(true)}>
              Transactions
            </Button>
          </div>
        </>
      )}

      <Drawer open={isFinancialsOpen} onClose={() => setIsFinancialsOpen(false)} title="Financials">
        <EmptyState
          title="Financials coming soon"
          description="Income statements, balance sheets and cash-flow data aren't wired up yet."
        />
      </Drawer>

      <Drawer open={isTransactionsOpen} onClose={() => setIsTransactionsOpen(false)} title="Transactions">
        <EmptyState
          title="Transactions coming soon"
          description="Viewing and managing this holding's recorded transactions isn't wired up yet."
        />
      </Drawer>

      <ConfirmDialog
        open={Boolean(deletingInstance)}
        title="Delete holding"
        message={
          deletingInstance
            ? `This will remove ${ticker} from ${deletingInstance.location}. Any recorded transactions for it will also be deleted. This can't be undone.`
            : ""
        }
        confirmLabel="Delete"
        isLoading={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => {
          setDeletingInstance(null);
          setDeleteError(null);
        }}
      />
      {deleteError && (
        <div className="ec-detail-delete-error">
          <Alert tone="danger">{deleteError}</Alert>
        </div>
      )}
    </AppShell>
  );
}

export default HoldingTickerPage;
