import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Button from "../../components/core/Button.jsx";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import Modal from "../../components/core/Modal.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import StatTile from "../../components/core/StatTile.jsx";
import AssetIcon from "../../components/core/AssetIcon.jsx";
import HoldingPriceChart from "./HoldingPriceChart.jsx";
import HoldingInstancesTable from "./HoldingInstancesTable.jsx";
import HoldingStatsPanel from "./HoldingStatsPanel.jsx";
import HoldingCagrSection from "./HoldingCagrSection.jsx";
import HoldingBuySellGauge from "./HoldingBuySellGauge.jsx";
import HoldingAboutSection from "./HoldingAboutSection.jsx";
import HoldingDividendsSection from "./HoldingDividendsSection.jsx";
import HoldingNewsSection from "./HoldingNewsSection.jsx";
import HoldingTransactionsSection from "./HoldingTransactionsSection.jsx";
import HoldingTickerSkeleton from "./HoldingTickerSkeleton.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import {
  getDividends,
  getMetrics,
  getNews,
  getProfile,
  searchTickers,
  MARKET_PROFILE_BADGE_TONES,
} from "../../api/market.js";
import {
  createTransaction,
  deleteTransaction,
  listTransactions,
  updateTransaction,
} from "../../api/transactions.js";
import { deleteHolding, getHolding } from "../../api/holdings.js";
import {
  clearCachedTransactionsForHolding,
  readCachedTransactionsPage,
  writeCachedTransactionsPage,
} from "../../utils/transactionsCache.js";
import { formatCurrency, plTone } from "../sampleFinancials.js";
import {
  computeHoldingValuation,
  formatSyncedDate,
  summarizeHoldingValuations,
} from "../holdingValuation.js";
import { resolveFxRate, rollupInstances } from "./holdingFinancials.js";
import "./HoldingTickerPage.css";

/** Page size for every listTransactions call this page makes — matches
 * backend/transactions/views.py's TransactionPagination default, kept
 * explicit here rather than relying on the server default so a page/cache
 * key always means the same 50-item window on both sides. */
const TRANSACTIONS_PAGE_SIZE = 50;

/** Merge a freshly-fetched `holding` (see api/holdings.js's getHolding) back
 * into the cached accounts tree at whichever account/pie it lives under —
 * called after a transaction create/update/delete so the holding's rollup
 * fields (no_of_shares/average_price_native/invested_native/... — see
 * equicast_core.transactions.compute_holding_rollup) reflect the mutation
 * immediately, without a full accounts refetch. */
function replaceHoldingInAccounts(accounts, holding) {
  return accounts.map((account) => ({
    ...account,
    holdings: (account.holdings ?? []).map((h) => (h.id === holding.id ? holding : h)),
    pies: (account.pies ?? []).map((pie) => ({
      ...pie,
      holdings: (pie.holdings ?? []).map((h) => (h.id === holding.id ? holding : h)),
    })),
  }));
}

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

/**
 * The full holding detail page for one ticker: real Total invested/P&L/P&L%
 * (rolled up from every instance's recorded transactions plus the
 * instrument's real current price — see holdingFinancials.js), a real
 * price chart for this ticker with a 1D..MAX range picker (see
 * HoldingPriceChart.jsx — unlike account/pie pages' consolidated chart
 * (PiePriceChart.jsx), which is real too but has no Candles chart type,
 * since an aggregate's per-date open/high/low is a value-weighted sum
 * across holdings' own bars, not a real traded range), a per-instance
 * shares/avg price table with delete,
 * a two-pane stats section, and an About section —
 * both real data from the market profile endpoint where it exists.
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
  const [marketMetrics, setMarketMetrics] = useState(null);
  const [marketDividends, setMarketDividends] = useState(null);
  const [marketNews, setMarketNews] = useState(null);
  const [transactionsByHolding, setTransactionsByHolding] = useState({});
  const [isDataLoading, setIsDataLoading] = useState(true);

  const [fxRate, setFxRate] = useState(null);
  const [fxState, setFxState] = useState("loading");

  const [isFinancialsOpen, setIsFinancialsOpen] = useState(false);

  const [deletingInstance, setDeletingInstance] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [pieDeleteNotice, setPieDeleteNotice] = useState(null);

  const instances = useMemo(() => {
    const list = [];
    for (const account of accounts) {
      for (const holding of account.holdings ?? []) {
        if (holding.ticker !== ticker) continue;
        list.push({
          holding,
          location: account.name,
          destination: `/accounts/${account.id}`,
          isPieHolding: false,
        });
      }
      for (const pie of account.pies ?? []) {
        for (const holding of pie.holdings ?? []) {
          if (holding.ticker !== ticker) continue;
          list.push({
            holding,
            location: `${account.name} / ${pie.name}`,
            destination: `/accounts/${account.id}/pies/${pie.id}`,
            isPieHolding: true,
          });
        }
      }
    }
    return list;
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

    const metricsPromise = getMetrics(api, assetClass, ticker).catch(() => null);
    // fx has no dividends concept (see api/market.js's getDividends jsdoc) —
    // skip the request entirely rather than hitting the endpoint just to
    // discard the result.
    const dividendsPromise =
      assetClass === "fx" ? Promise.resolve(null) : getDividends(api, assetClass, ticker).catch(() => null);
    const newsPromise = getNews(api, assetClass, ticker).catch(() => null);

    // Page 1 (50 items, most-recent-date-first — see backend/transactions/
    // views.py's TransactionListView.get) per instance, IndexedDB-cached so
    // navigating back to a holding already visited this session doesn't
    // re-hit the API for it — see utils/transactionsCache.js. Financial
    // totals (shares/avg price/invested) come from the holding record
    // itself now (see instanceFinancials below), not from this page, so a
    // fetch failure here only affects the recent-activity pane/drawer.
    const transactionsPromise = isOwned
      ? Promise.all(
          instances.map((instance) => {
            const holdingId = instance.holding.id;
            return readCachedTransactionsPage(holdingId, 1).then((cached) => {
              if (cached) return { holdingId, page: cached, error: false };
              return listTransactions(api, { holdingId, page: 1, pageSize: TRANSACTIONS_PAGE_SIZE })
                .then((page) => {
                  writeCachedTransactionsPage(holdingId, 1, page);
                  return { holdingId, page, error: false };
                })
                .catch(() => ({ holdingId, page: null, error: true }));
            });
          })
        )
      : Promise.resolve([]);

    Promise.all([profilePromise, metricsPromise, dividendsPromise, newsPromise, transactionsPromise]).then(
      ([profileResult, metrics, dividends, news, transactionsResults]) => {
        if (cancelled) return;
        setMarketProfileStatus(profileResult.status);
        setMarketProfile(profileResult.profile);
        setMarketMetrics(metrics);
        setMarketDividends(dividends);
        setMarketNews(news);
        const map = {};
        for (const result of transactionsResults) {
          map[result.holdingId] = result.error
            ? { holdingId: result.holdingId, transactions: [], count: 0, next: null, page: 1, error: true }
            : {
                holdingId: result.holdingId,
                transactions: result.page.results,
                count: result.page.count,
                next: result.page.next,
                page: 1,
                error: false,
              };
        }
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

  // Pie-scoped holdings reject DELETE /api/holdings/<id>/ outright (see
  // backend/holdings/views.py — "Pie-scoped holdings are removed via PUT
  // /api/pies/<id>/holdings/.", since a pie's holdings must always sum to
  // exactly 100% allocation, so removing one is really a re-sync of the
  // whole set, not a single-item delete). Caught here before the
  // confirmation dialog even opens, so clicking delete on one of these rows
  // never hits the API just to be told no.
  const handleDeleteClick = (instance) => {
    setDeleteError(null);
    if (instance.isPieHolding) {
      setDeletingInstance(null);
      setPieDeleteNotice(instance);
      return;
    }
    setPieDeleteNotice(null);
    setDeletingInstance(instance);
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

  // A create/update/delete changes both this holding's transaction list
  // *and* its rollup fields (no_of_shares/average_price_native/invested_...
  // — recomputed server-side, see backend/transactions/views.py's
  // _refresh_holding_rollup), so rather than patching the cached list
  // in place this drops every cached page for the holding and re-fetches
  // page 1 plus the holding itself fresh — the same "write straight back to
  // the source of truth" approach useAccounts.js's setAccounts uses.
  const refreshHoldingAfterMutation = (holdingId) => {
    clearCachedTransactionsForHolding(holdingId);
    return Promise.all([
      listTransactions(api, { holdingId, page: 1, pageSize: TRANSACTIONS_PAGE_SIZE }),
      getHolding(api, holdingId),
    ]).then(([page, holding]) => {
      writeCachedTransactionsPage(holdingId, 1, page);
      setTransactionsByHolding((prev) => ({
        ...prev,
        [holdingId]: {
          holdingId,
          transactions: page.results,
          count: page.count,
          next: page.next,
          page: 1,
          error: false,
        },
      }));
      setCachedAccounts((current) => replaceHoldingInAccounts(current, holding));
    });
  };

  const handleCreateTransaction = (holdingId, fields) =>
    createTransaction(api, { holding_id: holdingId, ...fields }).then((transaction) =>
      refreshHoldingAfterMutation(holdingId).then(() => transaction)
    );

  const handleUpdateTransaction = (holdingId, transactionId, fields) =>
    updateTransaction(api, holdingId, transactionId, fields).then((transaction) =>
      refreshHoldingAfterMutation(holdingId).then(() => transaction)
    );

  const handleDeleteTransaction = (holdingId, transactionId) =>
    deleteTransaction(api, holdingId, transactionId).then(() => refreshHoldingAfterMutation(holdingId));

  // "See all" drawer pagination — fetches the next page for one holding
  // (IndexedDB-cached the same as the initial page-1 load), appending to
  // whatever's already loaded rather than replacing it, so scrolling
  // further in the drawer never re-fetches an earlier page.
  const handleLoadMoreTransactions = (holdingId) => {
    const current = transactionsByHolding[holdingId];
    const nextPage = (current?.page ?? 1) + 1;
    return readCachedTransactionsPage(holdingId, nextPage)
      .then((cached) => cached ?? listTransactions(api, { holdingId, page: nextPage, pageSize: TRANSACTIONS_PAGE_SIZE }))
      .then((page) => {
        writeCachedTransactionsPage(holdingId, nextPage, page);
        setTransactionsByHolding((prev) => ({
          ...prev,
          [holdingId]: {
            holdingId,
            transactions: [...(prev[holdingId]?.transactions ?? []), ...page.results],
            count: page.count,
            next: page.next,
            page: nextPage,
            error: false,
          },
        }));
      });
  };

  const name = marketProfile?.name ?? null;

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
      eyebrow="Holding"
      title={name ?? ticker}
      subtitle={name ? ticker : undefined}
      stickyTitle
      titleIcon={<AssetIcon website={marketProfile?.website} size={64} />}
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
      {isLoading && <HoldingTickerSkeleton isOwned={false} />}
      {error && <Alert tone="danger">{error}</Alert>}

      {!isLoading && !error && notFound && (
        <EmptyState
          title={`${ticker} not found`}
          description="This isn't a ticker we recognize, and you don't hold it in any account or pie."
        />
      )}

      {!isLoading && !error && !notFound && (isResolvingAssetClass || isDataLoading) && (
        <HoldingTickerSkeleton isOwned={isOwned} />
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
            const currentPriceNative = marketProfile?.day_close ?? null;

            let avgPriceNative = null;
            let statGrid = null;
            let ownedSharesSection = null;

            if (isOwned) {
              // Shares/avg price/invested/dividends come straight off the
              // holding record now (no_of_shares/average_price_native/
              // invested_native/dividends_native — see equicast_core.
              // transactions.compute_holding_rollup), not derived from a
              // transaction fetch here — correct even when a holding has
              // more transactions than one page covers, and unaffected by
              // transactionsByHolding's own fetch state.
              const instanceFinancials = instances.map((instance) => {
                const holding = instance.holding;
                return {
                  ...instance,
                  shares: Number(holding.no_of_shares ?? 0),
                  avgPriceNative:
                    holding.average_price_native != null ? Number(holding.average_price_native) : null,
                  invested: Number(holding.invested_native ?? 0),
                  dividendsNative: Number(holding.dividends_native ?? 0),
                  transactionsError: false,
                };
              });

              const totals = rollupInstances(instanceFinancials, currentPriceNative);
              avgPriceNative = totals.shares > 0 ? totals.invested / totals.shares : null;

              // Value/Invested/Profit-loss/Dividends are shown in the user's
              // own default currency using each holding's own current_price/
              // invested/dividends — already converted server-side (see
              // equicast_core.client.MarketDataClient.enrich_holdings) — via
              // the same computeHoldingValuation/summarizeHoldingValuations
              // AccountDetailPage/PieDetailPage use, rather than this page
              // separately re-fetching marketProfile.day_close and its own
              // fx rate and converting client-side. That independent
              // computation could land on a different price/fx snapshot than
              // whatever the accounts/pies fetch had already enriched each
              // holding with, so the exact same holding could show a
              // different Value/Invested/P&L depending on whether you were
              // looking at it from this page or from its account/pie page.
              const holdingsForTicker = instances.map((instance) => instance.holding);
              const valuations = holdingsForTicker.map(computeHoldingValuation);
              const defaultTotals = summarizeHoldingValuations(holdingsForTicker, valuations);
              const totalsTone = plTone(defaultTotals.plPct);
              const totalsCurrency = defaultCurrency;
              const investedDefault = defaultTotals.invested;
              const currentValueDefault = defaultTotals.currentValue;
              const plValueDefault = defaultTotals.plValue;
              const dividendsDefault = defaultTotals.dividends;

              statGrid = (
                <div className="ec-stat-grid">
                  <StatTile
                    label="Value"
                    value={
                      currentValueDefault != null ? (
                        <Balance>{formatMoney(currentValueDefault, totalsCurrency)}</Balance>
                      ) : (
                        "—"
                      )
                    }
                    hint={
                      <>
                        Invested{" "}
                        {investedDefault != null ? (
                          <Balance>{formatMoney(investedDefault, totalsCurrency)}</Balance>
                        ) : (
                          "—"
                        )}
                      </>
                    }
                    tone={totalsTone}
                  />
                  <StatTile
                    label="Shares"
                    value={totals.shares}
                    hint={
                      <>
                        Avg price{" "}
                        {avgPriceNative != null ? (
                          <Balance>{formatMoney(avgPriceNative, nativeCurrency)}</Balance>
                        ) : (
                          "—"
                        )}
                      </>
                    }
                  />
                  <StatTile
                    label="Profit / loss"
                    value={
                      plValueDefault != null ? (
                        <Balance>
                          {plValueDefault >= 0 ? "+" : "-"}
                          {formatMoney(Math.abs(plValueDefault), totalsCurrency)}
                        </Balance>
                      ) : (
                        "—"
                      )
                    }
                    hint={`${defaultTotals.plPct >= 0 ? "+" : "-"}${Math.abs(defaultTotals.plPct).toFixed(1)}%`}
                    tone={totalsTone}
                    hintTone={totalsTone}
                  />
                  <StatTile
                    label="Dividends"
                    value={
                      dividendsDefault != null ? (
                        <Balance>{formatMoney(dividendsDefault, totalsCurrency)}</Balance>
                      ) : (
                        "—"
                      )
                    }
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
                    onDelete={handleDeleteClick}
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
                  avgPrice={avgPriceNative}
                  currentPrice={currentPriceNative}
                />
                {ownedSharesSection}
              </>
            );
          })()}

          <HoldingCagrSection marketMetrics={marketMetrics} />

          <HoldingBuySellGauge marketMetrics={marketMetrics} />

          <HoldingNewsSection news={marketNews} />

          <div className="ec-account-columns">
            <HoldingStatsPanel marketProfile={marketProfile} marketMetrics={marketMetrics} />
            <HoldingAboutSection marketProfile={marketProfile} />
          </div>

          <HoldingDividendsSection dividends={marketDividends} />

          {isOwned && (
            <HoldingTransactionsSection
              instances={instances}
              transactionsByHolding={transactionsByHolding}
              transactionType={userProfile?.transaction_type ?? "AVERAGE"}
              nativeCurrency={marketProfile?.currency ?? null}
              defaultCurrency={userProfile?.default_currency ?? null}
              onCreateTransaction={handleCreateTransaction}
              onUpdateTransaction={handleUpdateTransaction}
              onDeleteTransaction={handleDeleteTransaction}
              onLoadMoreTransactions={handleLoadMoreTransactions}
            />
          )}

          <div className="ec-holding-actions-row">
            <Button variant="secondary" onClick={() => setIsFinancialsOpen(true)}>
              Financials
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
      <Modal
        open={Boolean(pieDeleteNotice)}
        onClose={() => setPieDeleteNotice(null)}
        title="Can't delete from here"
        footer={
          <Button variant="secondary" onClick={() => setPieDeleteNotice(null)}>
            OK
          </Button>
        }
      >
        <p>
          {pieDeleteNotice
            ? `${ticker} in ${pieDeleteNotice.location} is part of a pie's allocation and can't be deleted from here — edit the pie's composition to remove it instead.`
            : ""}
        </p>
      </Modal>
    </AppShell>
  );
}

export default HoldingTickerPage;
