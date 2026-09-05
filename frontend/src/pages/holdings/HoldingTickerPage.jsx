import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Button from "../../components/core/Button.jsx";
import Badge from "../../components/core/Badge.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import StatTile from "../../components/core/StatTile.jsx";
import AssetIcon from "../../components/core/AssetIcon.jsx";
import HoldingPriceChart from "./HoldingPriceChart.jsx";
import HoldingInstancesTable from "./HoldingInstancesTable.jsx";
import HoldingStatsPanel from "./HoldingStatsPanel.jsx";
import HoldingAboutSection from "./HoldingAboutSection.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import { getProfile, getPrices, searchTickers, MARKET_PROFILE_BADGE_TONES } from "../../api/market.js";
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
  return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
    value
  );
}

/** marketProfile.last_updated is a full ISO 8601 datetime (see
 * equicast_core's writers) — the Synced badge only needs the date. */
function formatSyncedDate(isoDatetime) {
  const date = new Date(isoDatetime);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/**
 * The full holding detail page for one ticker: real Total invested/P&L/P&L%
 * (rolled up from every instance's recorded transactions plus the
 * instrument's real current price — see holdingFinancials.js), a real
 * price chart for this ticker with a 1D..MAX range picker (see
 * HoldingPriceChart.jsx — unlike account/pie pages' consolidated chart,
 * which stays illustrative since there's no real portfolio-valuation
 * series to plot yet), a per-instance shares/avg price table with delete,
 * a two-pane stats section, and an About section —
 * both real data from the market profile endpoint where it exists, with the
 * handful of fields the backend doesn't expose yet (P/E, volatility,
 * average volume, dividend frequency) shown as clearly-hinted placeholders.
 *
 * Reached by ticker, not holding id — the same ticker can be a separate
 * holding record directly in an account and/or inside one or more pies
 * (see the `instances` memo below), so this page aggregates every one of
 * them rather than assuming just one. A ticker the user doesn't hold
 * anywhere still shows its market profile/chart/about section (just
 * without the Total invested/P&L stats or Owned shares table, which need
 * real holdings to compute) — SearchPage links every result here, held or
 * not, and getProfile/getPrices need an asset class no owned instance
 * supplies in that case, so it's resolved from SearchPage's router state
 * when available, falling back to one searchTickers lookup otherwise (a
 * direct link, refresh, or share of the URL).
 */
function HoldingTickerPage() {
  const { ticker } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
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

  const isOwned = instances.length > 0;

  // Only needed when the ticker isn't held anywhere — an owned instance
  // already carries its asset class. `location.state?.assetClass` (set by
  // SearchPage's row click) skips the extra lookup for that flow; anything
  // else (a direct link, a refresh) falls back to one searchTickers call.
  const [resolvedAssetClass, setResolvedAssetClass] = useState(null);
  const [assetClassStatus, setAssetClassStatus] = useState("idle");

  useEffect(() => {
    if (isOwned) return undefined;

    const stateAssetClass = location.state?.assetClass;
    if (stateAssetClass) {
      setResolvedAssetClass(stateAssetClass);
      setAssetClassStatus("resolved");
      return undefined;
    }

    let cancelled = false;
    setAssetClassStatus("loading");
    setResolvedAssetClass(null);
    searchTickers(api, ticker, { pageSize: 5 })
      .then((response) => {
        if (cancelled) return;
        const match = response.results.find(
          (result) => result.ticker.toUpperCase() === ticker.toUpperCase()
        );
        setResolvedAssetClass(match ? match.type : null);
        setAssetClassStatus(match ? "resolved" : "not-found");
      })
      .catch(() => {
        if (!cancelled) setAssetClassStatus("not-found");
      });
    return () => {
      cancelled = true;
    };
  }, [api, ticker, isOwned, location.state]);

  const assetClass = isOwned ? instances[0].holding.asset_class : resolvedAssetClass;
  const notFound = !isOwned && assetClassStatus === "not-found";
  const isResolvingAssetClass = !isOwned && (assetClassStatus === "idle" || assetClassStatus === "loading");

  useEffect(() => {
    if (!assetClass) {
      setIsDataLoading(false);
      return undefined;
    }

    let cancelled = false;
    setIsDataLoading(true);

    const profilePromise = getProfile(api, assetClass, ticker)
      .then((profile) => ({ status: "ok", profile }))
      .catch((err) => ({ status: err.status === 404 ? "missing" : "error", profile: null }));

    // Fixed at "1y" regardless of the price chart's own range picker below
    // — this is the Stats panel's 52-week high/low window, a distinct
    // concept from whatever range the user has the chart set to.
    const pricesPromise = getPrices(api, assetClass, ticker, { range: "1y" })
      .then((res) => res.prices)
      .catch(() => null);

    const transactionsPromise = isOwned
      ? Promise.all(
          instances.map((instance) =>
            listTransactions(api, { holdingId: instance.holding.id })
              .then((transactions) => ({ holdingId: instance.holding.id, transactions, error: false }))
              .catch(() => ({ holdingId: instance.holding.id, transactions: [], error: true }))
          )
        )
      : Promise.resolve([]);

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
  }, [api, ticker, assetClass, isOwned, instances]);

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

  // Only known when this page was reached via a row click from
  // AccountDetailPage/PieDetailPage (they pass it as router state) — a
  // direct link/refresh/dashboard visit has no "back to" context, so no
  // link shows in that case.
  const backFrom = location.state?.from;
  const backTarget =
    backFrom?.type === "account"
      ? { label: "Back to account", path: `/accounts/${backFrom.accountId}` }
      : backFrom?.type === "pie"
        ? { label: "Back to portfolio", path: `/accounts/${backFrom.accountId}/pies/${backFrom.pieId}` }
        : null;

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Holding"
      title={name ?? ticker}
      subtitle={name ? ticker : undefined}
      titleIcon={<AssetIcon website={marketProfile?.website} size={32} />}
      titleBadges={
        marketProfile && (marketProfile.exchange || marketProfile.quote_type || marketProfile.last_updated) ? (
          <>
            {marketProfile.exchange && (
              <Badge tone={MARKET_PROFILE_BADGE_TONES.exchange}>
                Exchange: {marketProfile.exchange}
              </Badge>
            )}
            {marketProfile.quote_type && (
              <Badge tone={MARKET_PROFILE_BADGE_TONES.quoteType}>
                Quote type: {marketProfile.quote_type}
              </Badge>
            )}
            {marketProfile.last_updated && formatSyncedDate(marketProfile.last_updated) && (
              <Badge tone={MARKET_PROFILE_BADGE_TONES.synced}>
                Synced: {formatSyncedDate(marketProfile.last_updated)}
              </Badge>
            )}
          </>
        ) : undefined
      }
      actions={
        backTarget && (
          <Button variant="ghost" onClick={() => navigate(backTarget.path)}>
            {backTarget.label}
          </Button>
        )
      }
      footer={<SiteFooter />}
    >
      {isLoading && <p className="ec-loading">Loading…</p>}
      {error && <Alert tone="danger">{error}</Alert>}

      {!isLoading && !error && notFound && (
        <EmptyState
          title={`${ticker} not found`}
          description="This isn't a ticker we recognize, and you don't hold it in any account or pie."
        />
      )}

      {!isLoading && !error && !notFound && (isResolvingAssetClass || isDataLoading) && (
        <p className="ec-loading">Loading…</p>
      )}

      {!isLoading && !error && !notFound && !isResolvingAssetClass && !isDataLoading && (
        <>
          {marketProfileStatus === "missing" ? (
            <div className="ec-holding-notice">
              <Alert tone="info">
                No real market data is published for {ticker} yet
                {isOwned ? " — showing what’s available from your recorded transactions only." : "."}
              </Alert>
            </div>
          ) : (
            !isOwned && (
              <div className="ec-holding-notice">
                <Alert tone="info">You don&rsquo;t currently hold {ticker} in any account or pie.</Alert>
              </div>
            )
          )}

          {(() => {
            const nativeCurrency = marketProfile?.currency ?? null;
            const defaultCurrency = userProfile?.default_currency ?? null;
            const currentPriceNative = marketProfile?.day_close ?? marketProfile?.day_average ?? null;

            let avgPriceNative = null;
            let statGrid = null;
            let ownedSharesSection = null;

            if (isOwned) {
              const instanceFinancials = instances.map((instance) => {
                const entry = transactionsByHolding[instance.holding.id];
                if (!entry || entry.error) {
                  return { ...instance, shares: 0, avgPriceNative: null, invested: 0, transactionsError: Boolean(entry?.error) };
                }
                const financials = deriveInstanceFinancials(entry.transactions, instance.transactionType);
                return { ...instance, ...financials, transactionsError: false };
              });

              const totals = rollupInstances(instanceFinancials, currentPriceNative);
              const totalsTone = plTone(totals.plPct ?? 0);
              avgPriceNative = totals.shares > 0 ? totals.invested / totals.shares : null;

              // Total invested/Profit-loss are shown in the user's own default
              // currency (fxRate converts nativeCurrency -> defaultCurrency —
              // see resolveFxRate), not the holding's native currency: a GBP
              // account holding a USD stock should read in GBP here, same
              // reasoning as HoldingInstancesTable's own default-currency
              // column. Profit/loss % needs no conversion, being currency-free.
              // When there's no market profile at all (marketProfileStatus ===
              // "missing"), nativeCurrency is null, so there's nothing to
              // convert from/to — shown as a plain currency-less number
              // instead of blocking forever on an fx lookup the page never
              // even attempts in that case (see the fxRate effect above).
              const totalsLoading = nativeCurrency != null && fxState === "loading";
              const totalsCurrency = nativeCurrency == null ? null : defaultCurrency;
              const investedDefault =
                nativeCurrency == null ? totals.invested : fxRate != null ? totals.invested * fxRate : null;
              const plValueDefault =
                totals.plValue == null
                  ? null
                  : nativeCurrency == null
                    ? totals.plValue
                    : fxRate != null
                      ? totals.plValue * fxRate
                      : null;

              statGrid = (
                <div className="ec-stat-grid">
                  <StatTile
                    label="Total invested"
                    value={
                      totalsLoading
                        ? "…"
                        : investedDefault != null
                          ? formatMoney(investedDefault, totalsCurrency)
                          : "—"
                    }
                    hint="Real data"
                  />
                  <StatTile
                    label="Profit / loss"
                    value={
                      totalsLoading
                        ? "…"
                        : plValueDefault != null
                          ? `${plValueDefault >= 0 ? "+" : "-"}${formatMoney(Math.abs(plValueDefault), totalsCurrency)}`
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
              );

              ownedSharesSection = (
                <>
                  <div className="ec-section-head">
                    <h2 className="ec-section-title">Owned shares</h2>
                  </div>
                  <HoldingInstancesTable
                    instances={instanceFinancials}
                    nativeCurrency={nativeCurrency}
                    defaultCurrency={defaultCurrency}
                    fxRate={fxRate}
                    fxState={fxState}
                    onDelete={setDeletingInstance}
                    onRowClick={(instance) => navigate(instance.destination)}
                  />
                </>
              );
            }

            return (
              <>
                {statGrid}
                <HoldingPriceChart
                  assetClass={assetClass}
                  ticker={ticker}
                  currency={nativeCurrency}
                  holdings={otherHoldings}
                  avgPrice={avgPriceNative}
                />
                {ownedSharesSection}
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
