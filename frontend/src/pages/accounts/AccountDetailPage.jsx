import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import StatTile from "../../components/core/StatTile.jsx";
import AccountForm from "./AccountForm.jsx";
import PriceChart from "./PriceChart.jsx";
import DiversificationChart from "./DiversificationChart.jsx";
import HoldingsHeatmap from "./HoldingsHeatmap.jsx";
import CreatePortfolioDrawer from "./CreatePortfolioDrawer.jsx";
import TickerSearchField from "../pies/TickerSearchField.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import { deleteAccount, getAccount, updateAccount } from "../../api/accounts.js";
import { createHolding } from "../../api/holdings.js";
import { MENU_ITEMS } from "../menuItems.js";
import { INDUSTRY_DATA, SECTOR_DATA, SECTOR_SCORE } from "../diversificationSampleData.js";
import { formatCurrency, TICKER_NAMES, buildPieSample, buildHoldingSample, plTone } from "../sampleFinancials.js";
import { computeHoldingValuation, summarizeHoldingValuations } from "../holdingValuation.js";
import "./AccountDetailPage.css";

/** An account's real holdings (direct and pie-nested alike) carry
 * `invested`/`dividends`/`current_price` already converted to the user's
 * default_currency, not the account's own `currency` (see
 * api/accounts.js's `Holding` typedef and equicast_core.client.
 * MarketDataClient.enrich_holdings) — same reasoning as PieDetailPage's own
 * top stat row, so the real Value/Profit-loss/Dividends-so-far cards below
 * are labeled in that currency, not `account.currency` (which the still-
 * synthetic Portfolios/Holdings rows and chart further down keep using). */
const FALLBACK_CURRENCY = "USD";

function AccountDetailPage() {
  const { accountId } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const { setAccounts: setCachedAccounts } = useAccounts();
  const { profile: userProfile } = useCurrentUser();

  const [account, setAccount] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [selectedSector, setSelectedSector] = useState(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const [isCreatePortfolioOpen, setIsCreatePortfolioOpen] = useState(false);

  const [isAddHoldingOpen, setIsAddHoldingOpen] = useState(false);
  const [addHoldingError, setAddHoldingError] = useState(null);

  const load = () => {
    setIsLoading(true);
    setLoadError(null);
    getAccount(api, accountId)
      .then(setAccount)
      .catch((err) => setLoadError(err.message ?? "Couldn't load this account."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [api, accountId]);

  /**
   * Applies the same update to the session-cached accounts list (see
   * useAccounts.js) that AccountsListPage/DashboardPage read from — this
   * page loads its own copy via getAccount rather than that shared list, so
   * without this, a field/pie/holding change made here wouldn't show up over
   * there until the cache expired (tab close) or someone edited that account
   * directly from the table.
   */
  const patchCachedAccount = (updater) => {
    setCachedAccounts((current) => current.map((a) => (a.id === accountId ? updater(a) : a)));
  };

  const handleUpdate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    updateAccount(api, accountId, values)
      .then((updated) => {
        setAccount((current) => ({ ...current, ...updated }));
        patchCachedAccount((a) => ({ ...a, ...updated }));
        setIsEditOpen(false);
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't update the account."))
      .finally(() => setIsSaving(false));
  };

  const needsForce = account && ((account.pies?.length ?? 0) > 0 || (account.holdings?.length ?? 0) > 0);

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deleteAccount(api, accountId, { force: needsForce })
      .then(() => {
        setCachedAccounts((current) => current.filter((a) => a.id !== accountId));
        navigate("/accounts");
      })
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the account."))
      .finally(() => setIsDeleting(false));
  };

  const handlePortfolioCreated = (pie) => {
    setAccount((current) => ({ ...current, pies: [...(current.pies ?? []), pie] }));
    patchCachedAccount((a) => ({ ...a, pies: [...(a.pies ?? []), pie] }));
  };

  const handleAddHolding = ({ ticker, asset_class }) => {
    setAddHoldingError(null);
    if ((account.holdings ?? []).some((h) => h.ticker === ticker)) {
      setAddHoldingError(`${ticker} is already held directly in this account.`);
      return;
    }
    createHolding(api, { ticker, asset_class, account_id: accountId })
      .then((holding) => {
        setAccount((current) => ({ ...current, holdings: [...(current.holdings ?? []), holding] }));
        patchCachedAccount((a) => ({ ...a, holdings: [...(a.holdings ?? []), holding] }));
      })
      .catch((err) => setAddHoldingError(err.message ?? "Couldn't add the holding."));
  };

  if (isLoading) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Account" title="Loading…" footer={<SiteFooter />}>
        <p className="ec-loading">Loading…</p>
      </AppShell>
    );
  }

  if (loadError || !account) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Account" title="Account" footer={<SiteFooter />}>
        <Alert tone="danger">{loadError ?? "Account not found."}</Alert>
      </AppShell>
    );
  }

  const directHoldings = account.holdings ?? [];
  const pieHoldings = (account.pies ?? []).flatMap((p) => p.holdings ?? []);
  const allHoldings = [...directHoldings, ...pieHoldings];
  const allTickers = allHoldings.map((h) => h.ticker);
  const currency = userProfile?.default_currency ?? FALLBACK_CURRENCY;
  const holdingValuations = allHoldings.map(computeHoldingValuation);
  const totals = summarizeHoldingValuations(allHoldings, holdingValuations);
  const totalsTone = plTone(totals.plPct);

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Account"
      title={account.name}
      subtitle={account.description}
      actions={
        <Button
          variant="secondary"
          className="ec-btn-icon-only"
          aria-label="Edit account"
          onClick={() => setIsEditOpen(true)}
        >
          <i className="bi bi-pencil" aria-hidden="true" />
        </Button>
      }
      footer={<SiteFooter />}
    >
      <div className="ec-account-detail-badges">
        <Badge tone="accent">{account.account_type}</Badge>
        <Badge tone="neutral">{account.currency}</Badge>
      </div>

      <div className="ec-stat-grid">
        <StatTile
          label="Value"
          value={formatCurrency(totals.currentValue, currency)}
          hint={`Invested ${formatCurrency(totals.invested, currency)}`}
        />
        <StatTile
          label="Profit / loss"
          value={`${totals.plValue >= 0 ? "+" : "-"}${formatCurrency(Math.abs(totals.plValue), currency)}`}
          tone={totalsTone}
          hint={`${totals.plPct >= 0 ? "+" : "-"}${Math.abs(totals.plPct).toFixed(1)}%`}
          hintTone={totalsTone}
        />
        <StatTile label="Dividends so far" value={formatCurrency(totals.dividends, currency)} />
      </div>

      <PriceChart pies={account.pies ?? []} seedKey={`account:${accountId}`} subjectLabel="This account" />

      <div className="ec-account-columns">
        <div>
          <div className="ec-section-head">
            <h2 className="ec-section-title">Portfolios</h2>
            <Button variant="primary" size="sm" onClick={() => setIsCreatePortfolioOpen(true)}>
              <i className="bi bi-plus-lg" aria-hidden="true" />
              Create portfolio
            </Button>
          </div>

          {(account.pies ?? []).length === 0 ? (
            <EmptyState
              title="No portfolios yet"
              description="A pie holds a 100%-allocated slice of this account across one or more tickers."
              action={
                <Button variant="primary" onClick={() => setIsCreatePortfolioOpen(true)}>
                  Create portfolio
                </Button>
              }
            />
          ) : (
            <div className="ec-detail-row-list">
              {account.pies.map((pie) => {
                const sample = buildPieSample(pie.id);
                const tone = plTone(sample.plPct);
                const plSign = sample.plValue >= 0 ? "+" : "-";
                return (
                  <Card
                    key={pie.id}
                    className="ec-detail-row ec-detail-row--clickable"
                    role="button"
                    tabIndex={0}
                    onClick={() => navigate(`/accounts/${accountId}/pies/${pie.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/accounts/${accountId}/pies/${pie.id}`);
                      }
                    }}
                  >
                    <div className="ec-detail-row-main">
                      <h3 className="ec-detail-row-name">{pie.name}</h3>
                      <span className="ec-detail-row-meta">{(pie.holdings ?? []).length} holdings</span>
                    </div>
                    <div className="ec-detail-row-value">
                      <span className="ec-detail-row-current">
                        {formatCurrency(sample.currentValue, account.currency)}
                      </span>
                      <span className={`ec-detail-row-pl ${tone}`}>
                        {plSign}
                        {formatCurrency(Math.abs(sample.plValue), account.currency)} ({plSign}
                        {Math.abs(sample.plPct).toFixed(1)}%)
                      </span>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        <div>
          <div className="ec-section-head">
            <h2 className="ec-section-title">Holdings</h2>
            <Button variant="primary" size="sm" onClick={() => setIsAddHoldingOpen(true)}>
              <i className="bi bi-plus-lg" aria-hidden="true" />
              Add holding
            </Button>
          </div>

          {directHoldings.length === 0 ? (
            <EmptyState
              title="No direct holdings"
              description="Holdings added straight to this account (not inside a pie) will show up here."
              action={
                <Button variant="primary" onClick={() => setIsAddHoldingOpen(true)}>
                  Add holding
                </Button>
              }
            />
          ) : (
            <div className="ec-detail-row-list">
              {directHoldings.map((holding) => {
                const sample = buildHoldingSample(holding.id);
                const tone = plTone(sample.plPct);
                const plSign = sample.plValue >= 0 ? "+" : "-";
                const name = TICKER_NAMES[holding.ticker];
                return (
                  <Card
                    key={holding.id}
                    className="ec-detail-row ec-detail-row--clickable"
                    role="button"
                    tabIndex={0}
                    onClick={() =>
                      navigate(`/holdings/${holding.ticker}`, {
                        state: { from: { type: "account", accountId } },
                      })
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/holdings/${holding.ticker}`, {
                          state: { from: { type: "account", accountId } },
                        });
                      }
                    }}
                  >
                    <div className="ec-detail-row-main">
                      <h3 className="ec-detail-row-name">
                        {name ? `${name} (${holding.ticker})` : holding.ticker}
                      </h3>
                      <span className="ec-detail-row-meta">{sample.shares} shares</span>
                    </div>
                    <div className="ec-detail-row-value">
                      <span className="ec-detail-row-current">
                        {formatCurrency(sample.currentValue, account.currency)}
                      </span>
                      <span className={`ec-detail-row-pl ${tone}`}>
                        {plSign}
                        {formatCurrency(Math.abs(sample.plValue), account.currency)} ({plSign}
                        {Math.abs(sample.plPct).toFixed(1)}%)
                      </span>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="ec-divchart-grid">
        <DiversificationChart
          title="Sector diversification"
          score={SECTOR_SCORE}
          data={SECTOR_DATA}
          caption="Illustrative sample data — sector classification isn't wired up to real holdings yet. Click a sector to filter industries below; click it again to show all."
          activeLabel={selectedSector}
          onRowClick={(label) => setSelectedSector((current) => (current === label ? null : label))}
        />

        <DiversificationChart
          title={selectedSector ? `Industry diversification — ${selectedSector}` : "Industry diversification"}
          data={
            selectedSector ? INDUSTRY_DATA.filter((i) => i.sector === selectedSector) : INDUSTRY_DATA
          }
          caption="Illustrative sample data — industry classification isn't wired up to real holdings yet."
        />
      </div>

      <HoldingsHeatmap tickers={allTickers} />

      <Card className="ec-danger-zone">
        <div className="ec-danger-zone-text">
          <h3 className="ec-danger-zone-title">Delete this account</h3>
          <p className="ec-danger-zone-desc">
            {needsForce
              ? "This account still has pies and/or holdings. Deleting it will also delete all of them, along with any recorded transactions. This action is permanent and cannot be undone."
              : "This will permanently delete the account. This action is permanent and cannot be undone."}
          </p>
        </div>
        <Button variant="danger" onClick={() => setIsDeleteOpen(true)}>
          <i className="bi bi-trash" aria-hidden="true" />
          Delete account
        </Button>
      </Card>

      <Drawer
        open={isAddHoldingOpen}
        onClose={() => {
          setIsAddHoldingOpen(false);
          setAddHoldingError(null);
        }}
        title="Add holding"
      >
        <p className="ec-account-holding-hint">
          Search for a ticker to add it directly to this account, outside of any pie.
        </p>
        {addHoldingError && <Alert tone="danger">{addHoldingError}</Alert>}
        <TickerSearchField onSelect={handleAddHolding} />
      </Drawer>

      <Drawer
        open={isEditOpen}
        onClose={() => {
          setIsEditOpen(false);
          setSaveError(null);
        }}
        title="Edit account"
      >
        <AccountForm
          initialValues={account}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditOpen(false);
            setSaveError(null);
          }}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      <CreatePortfolioDrawer
        open={isCreatePortfolioOpen}
        accountId={accountId}
        onClose={() => setIsCreatePortfolioOpen(false)}
        onCreated={handlePortfolioCreated}
      />

      <ConfirmDialog
        open={isDeleteOpen}
        title="Delete account"
        message={
          needsForce
            ? "This account still has pies and/or holdings. Deleting it will also delete all of them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the account. This can't be undone."
        }
        confirmLabel="Delete account"
        isLoading={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => {
          setIsDeleteOpen(false);
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

export default AccountDetailPage;
