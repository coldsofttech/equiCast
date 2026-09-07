import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Card from "../../components/core/Card.jsx";
import AssetIcon from "../../components/core/AssetIcon.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import StatTile from "../../components/core/StatTile.jsx";
import PieForm from "./PieForm.jsx";
import AllocationEditor from "./AllocationEditor.jsx";
import PiePriceChart from "./PiePriceChart.jsx";
import PieCagrSection from "./PieCagrSection.jsx";
import PieDetailSkeleton from "./PieDetailSkeleton.jsx";
import DiversificationChart from "../accounts/DiversificationChart.jsx";
import HoldingsHeatmap from "../accounts/HoldingsHeatmap.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import { deletePie, getPie, syncPieHoldings, updatePie } from "../../api/pies.js";
import { MENU_ITEMS } from "../menuItems.js";
import { formatCurrency, plTone } from "../sampleFinancials.js";
import {
  computeHoldingValuation,
  summarizeHoldingValuations,
  buildDiversification,
} from "../holdingValuation.js";

/** A pie holding's `invested`/`dividends`/`current_price` (see
 * backend/pies/views.py's `_enrich_holdings`) are all converted to the
 * user's default_currency, not the parent account's own currency — so
 * totals here are labeled/formatted in that currency, read off the cached
 * profile (see useCurrentUser.js), falling back only in the unlikely case
 * it hasn't loaded yet by the time these StatTiles first render. */
const FALLBACK_CURRENCY = "USD";

/**
 * One portfolio's own overview page — same shape as AccountDetailPage (a
 * price chart, a holdings section, bottom-of-page diversification/heatmap),
 * scoped to this pie's own holdings instead of the whole account's. Unlike
 * AccountDetailPage's own price chart (still sample data), every one of
 * these is real here: the price chart (PiePriceChart) aggregates every
 * holding's own real price history, sector/industry diversification
 * (buildDiversification — shared with AccountDetailPage's own, account-wide
 * breakdown) and the holdings heatmap (`weights` prop, shared with
 * AccountDetailPage's own account-wide one — see HoldingsHeatmap) are both
 * real, value-weighted breakdowns of this pie's own holdings. Holdings here
 * are read-only (name,
 * allocation %, live value/P&L off the enriched fields GET /pies/<id>
 * returns — see computeHoldingValuation) — adding/removing/reallocating
 * them happens via AllocationEditor inside its own "Add holdings" Drawer,
 * separate from the "Edit pie" Drawer (name/description only), so editing
 * one never shows form fields for the other.
 */
function PieDetailPage() {
  const { accountId, pieId } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const { setAccounts: setCachedAccounts } = useAccounts();
  const { profile: userProfile } = useCurrentUser();
  const currency = userProfile?.default_currency ?? FALLBACK_CURRENCY;

  const [pie, setPie] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [selectedSector, setSelectedSector] = useState(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const [isHoldingsOpen, setIsHoldingsOpen] = useState(false);
  const [isAllocationSaving, setIsAllocationSaving] = useState(false);
  const [allocationError, setAllocationError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setLoadError(null);
    getPie(api, pieId)
      .then(setPie)
      .catch((err) => setLoadError(err.message ?? "Couldn't load this pie."))
      .finally(() => setIsLoading(false));
  }, [api, pieId]);

  /**
   * Mirrors a pie-level change into the session-cached accounts list (see
   * useAccounts.js) that AccountsListPage/DashboardPage/AccountDetailPage
   * read from — this page loads the pie via its own getPie/syncPieHoldings
   * calls rather than that shared list, so without this a rename or
   * holdings change made here wouldn't show up over there until the cache
   * expired.
   */
  const patchCachedPie = (updater) => {
    setCachedAccounts((current) =>
      current.map((a) =>
        a.id === accountId ? { ...a, pies: (a.pies ?? []).map((p) => (p.id === pieId ? updater(p) : p)) } : a
      )
    );
  };

  const handleUpdate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    updatePie(api, pieId, values)
      .then((updated) => {
        setPie((current) => ({ ...current, ...updated }));
        patchCachedPie((p) => ({ ...p, ...updated }));
        setIsEditOpen(false);
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't update the pie."))
      .finally(() => setIsSaving(false));
  };

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deletePie(api, pieId, { force: (pie.holdings?.length ?? 0) > 0 })
      .then(() => {
        setCachedAccounts((current) =>
          current.map((a) =>
            a.id === accountId ? { ...a, pies: (a.pies ?? []).filter((p) => p.id !== pieId) } : a
          )
        );
        navigate(`/accounts/${accountId}`);
      })
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the pie."))
      .finally(() => setIsDeleting(false));
  };

  const handleSaveAllocation = (batch) => {
    setIsAllocationSaving(true);
    setAllocationError(null);
    // syncPieHoldings' own response isn't enriched with name/sector/
    // industry/current_price (see pies.js's docstring) — getPie is, so the
    // Holdings cards have real data to render as soon as the drawer closes.
    syncPieHoldings(api, pieId, batch)
      .then(() => getPie(api, pieId))
      .then((updated) => {
        setPie(updated);
        patchCachedPie(() => updated);
        setIsHoldingsOpen(false);
      })
      .catch((err) => setAllocationError(err.message ?? "Couldn't save the allocation changes."))
      .finally(() => setIsAllocationSaving(false));
  };

  if (isLoading) {
    return (
      <AppShell
        menuItems={MENU_ITEMS}
        eyebrow="Portfolio"
        title="Loading…"
        actions={
          <Button variant="ghost" onClick={() => navigate(`/accounts/${accountId}`)}>
            Back to account
          </Button>
        }
        footer={<SiteFooter />}
      >
        <PieDetailSkeleton />
      </AppShell>
    );
  }

  if (loadError || !pie) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Pie" footer={<SiteFooter />}>
        <Alert tone="danger">{loadError ?? "Pie not found."}</Alert>
      </AppShell>
    );
  }

  const holdingValuations = (pie.holdings ?? []).map((h) => computeHoldingValuation(h));
  const heatmapWeights = (pie.holdings ?? []).map((h, index) => ({
    ticker: h.ticker,
    value: holdingValuations[index].currentValue,
  }));
  const totals = summarizeHoldingValuations(pie.holdings ?? [], holdingValuations);
  const totalsTone = plTone(totals.plPct);
  const { sectorData, industryData, sectorScore } = buildDiversification(
    pie.holdings ?? [],
    holdingValuations
  );

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Portfolio"
      title={pie.name}
      subtitle={pie.description}
      actions={
        <>
          <Button variant="ghost" onClick={() => navigate(`/accounts/${accountId}`)}>
            Back to account
          </Button>
          <Button
            variant="secondary"
            className="ec-btn-icon-only"
            aria-label="Edit pie"
            onClick={() => setIsEditOpen(true)}
          >
            <i className="bi bi-pencil" aria-hidden="true" />
          </Button>
        </>
      }
      footer={<SiteFooter />}
    >
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

      <PiePriceChart
        holdings={pie.holdings ?? []}
        currency={currency}
        accountId={accountId}
        pieId={pieId}
        investedTotal={totals.invested}
        currentValueTotal={totals.currentValue}
        holdingValuations={holdingValuations}
      />

      <div className="ec-section-head">
        <h2 className="ec-section-title">Holdings</h2>
        <Button variant="primary" size="sm" onClick={() => setIsHoldingsOpen(true)}>
          <i className="bi bi-plus-lg" aria-hidden="true" />
          Add holding
        </Button>
      </div>

      {(pie.holdings ?? []).length === 0 ? (
        <EmptyState
          title="No holdings yet"
          description="Search for a ticker and set its allocation to add it to this pie."
          action={
            <Button variant="primary" onClick={() => setIsHoldingsOpen(true)}>
              Add holding
            </Button>
          }
        />
      ) : (
        <div className="ec-detail-row-list">
          {pie.holdings.map((holding, index) => {
            const valuation = holdingValuations[index];
            const tone = plTone(valuation.plPct);
            const plSign = valuation.plValue >= 0 ? "+" : "-";
            const targetPct = Number(holding.allocation_pct);
            // "Actual" allocation is this holding's share of the pie's real
            // current value, not its stored target — the two drift apart
            // as prices move, which is exactly what this comparison is
            // meant to surface.
            const actualPct =
              totals.currentValue > 0 ? (valuation.currentValue / totals.currentValue) * 100 : 0;
            const allocTone =
              actualPct > targetPct ? "is-up" : actualPct < targetPct ? "is-down" : "is-flat";
            return (
              <Card
                key={holding.id}
                className="ec-detail-row ec-detail-row--clickable"
                role="button"
                tabIndex={0}
                onClick={() =>
                  navigate(`/holdings/${holding.ticker}`, {
                    state: { from: { type: "pie", accountId, pieId } },
                  })
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    navigate(`/holdings/${holding.ticker}`, {
                      state: { from: { type: "pie", accountId, pieId } },
                    });
                  }
                }}
              >
                <div className="ec-detail-row-heading">
                  <AssetIcon website={holding.website} size={32} />
                  <div className="ec-detail-row-main">
                    <h3 className="ec-detail-row-name">
                      {holding.name ? `${holding.name} (${holding.ticker})` : holding.ticker}
                    </h3>
                    <span className="ec-detail-row-meta">
                      {holding.no_of_shares} shares · {targetPct}% target /{" "}
                      <span className={`ec-detail-row-alloc-actual ${allocTone}`}>
                        {actualPct.toFixed(1)}% actual
                      </span>
                    </span>
                  </div>
                </div>
                <div className="ec-detail-row-value">
                  <span className="ec-detail-row-current">
                    {formatCurrency(valuation.currentValue, currency)}
                    {!valuation.hasLivePrice && " (cost basis)"}
                  </span>
                  <span className={`ec-detail-row-pl ${tone}`}>
                    {plSign}
                    {formatCurrency(Math.abs(valuation.plValue), currency)} ({plSign}
                    {Math.abs(valuation.plPct).toFixed(1)}%)
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <div className="ec-divchart-grid">
        <DiversificationChart
          title="Sector diversification"
          score={sectorScore ?? undefined}
          data={sectorData}
          caption="Click a sector to filter industries below; click it again to show all."
          activeLabel={selectedSector}
          onRowClick={(label) => setSelectedSector((current) => (current === label ? null : label))}
        />

        <DiversificationChart
          title={selectedSector ? `Industry diversification — ${selectedSector}` : "Industry diversification"}
          data={
            selectedSector ? industryData.filter((i) => i.sector === selectedSector) : industryData
          }
        />
      </div>

      <PieCagrSection holdings={pie.holdings ?? []} valuations={holdingValuations} />

      <HoldingsHeatmap weights={heatmapWeights} />

      <Card className="ec-danger-zone">
        <div className="ec-danger-zone-text">
          <h3 className="ec-danger-zone-title">Delete this pie</h3>
          <p className="ec-danger-zone-desc">
            {(pie.holdings?.length ?? 0) > 0
              ? "This pie still has holdings. Deleting it will also delete them, along with any recorded transactions. This action is permanent and cannot be undone."
              : "This will permanently delete the pie. This action is permanent and cannot be undone."}
          </p>
        </div>
        <Button variant="danger" onClick={() => setIsDeleteOpen(true)}>
          <i className="bi bi-trash" aria-hidden="true" />
          Delete pie
        </Button>
      </Card>

      <Drawer
        open={isEditOpen}
        onClose={() => {
          setIsEditOpen(false);
          setSaveError(null);
        }}
        title="Edit pie"
      >
        <PieForm
          initialValues={pie}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditOpen(false);
            setSaveError(null);
          }}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      <Drawer
        open={isHoldingsOpen}
        onClose={() => {
          setIsHoldingsOpen(false);
          setAllocationError(null);
        }}
        title="Add holdings"
      >
        <AllocationEditor
          holdings={pie.holdings ?? []}
          onSave={handleSaveAllocation}
          isSaving={isAllocationSaving}
          error={allocationError}
        />
      </Drawer>

      <ConfirmDialog
        open={isDeleteOpen}
        title="Delete pie"
        message={
          (pie.holdings?.length ?? 0) > 0
            ? "This pie still has holdings. Deleting it will also delete them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the pie. This can't be undone."
        }
        confirmLabel="Delete pie"
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

export default PieDetailPage;
