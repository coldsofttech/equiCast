import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Card from "../../components/core/Card.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import StatTile from "../../components/core/StatTile.jsx";
import PieForm from "./PieForm.jsx";
import AllocationEditor from "./AllocationEditor.jsx";
import PriceChart from "../accounts/PriceChart.jsx";
import DiversificationChart from "../accounts/DiversificationChart.jsx";
import HoldingsHeatmap from "../accounts/HoldingsHeatmap.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { deletePie, getPie, listPies, syncPieHoldings, updatePie } from "../../api/pies.js";
import { MENU_ITEMS } from "../menuItems.js";
import { INDUSTRY_DATA, SECTOR_DATA, SECTOR_SCORE } from "../diversificationSampleData.js";
import {
  formatCurrency,
  TICKER_NAMES,
  buildPieSample,
  buildHoldingSample,
  plTone,
  aggregateSamples,
} from "../sampleFinancials.js";

/** GET /pies/<id> doesn't carry the parent account's currency (see
 * backend/pies/views.py), so it's read off the session-cached accounts
 * list (see useAccounts.js) this page already pulls from for cache
 * patching — falling back to this only in the unlikely case that list
 * hasn't loaded yet by the time these StatTiles first render. */
const FALLBACK_CURRENCY = "USD";

/**
 * One portfolio's own overview page — same shape as AccountDetailPage
 * (placeholder stats, a consolidated price chart, a holdings section,
 * bottom-of-page diversification/heatmap), scoped to this pie's own
 * holdings instead of the whole account's. Holdings here are read-only
 * (name, allocation %, sample value/P&L) — adding/removing/reallocating
 * them happens via AllocationEditor inside the "Edit pie" Drawer instead.
 */
function PieDetailPage() {
  const { accountId, pieId } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const { accounts, setAccounts: setCachedAccounts } = useAccounts();
  const currency = accounts.find((a) => a.id === accountId)?.currency ?? FALLBACK_CURRENCY;

  const [pie, setPie] = useState(null);
  const [siblingPies, setSiblingPies] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [selectedSector, setSelectedSector] = useState(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

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

  useEffect(() => {
    // Non-critical for the page to function — if this fails, the price
    // chart's compare picker just offers benchmarks only, so no error
    // state is surfaced for it.
    listPies(api, { accountId })
      .then((pies) => setSiblingPies(pies.filter((p) => p.id !== pieId)))
      .catch(() => {});
  }, [api, accountId, pieId]);

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
    syncPieHoldings(api, pieId, batch)
      .then((updated) => {
        setPie(updated);
        patchCachedPie(() => updated);
      })
      .catch((err) => setAllocationError(err.message ?? "Couldn't save the allocation changes."))
      .finally(() => setIsAllocationSaving(false));
  };

  if (isLoading) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Loading…" footer={<SiteFooter />}>
        <p className="ec-loading">Loading…</p>
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

  const tickers = (pie.holdings ?? []).map((h) => h.ticker);
  // Seeded by the pie's own id (same as the sample AccountDetailPage shows
  // for this pie in its Portfolios list), not derived from pie.holdings —
  // a pie with zero holdings would otherwise sample to a flat $0 here,
  // and this keeps the two pages' numbers for the same pie consistent.
  const totals = aggregateSamples([buildPieSample(pieId)]);
  const totalsTone = plTone(totals.plPct);

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
          label="Total invested"
          value={formatCurrency(totals.invested, currency)}
          hint="Sample data"
        />
        <StatTile
          label="Profit / loss"
          value={`${totals.plValue >= 0 ? "+" : "-"}${formatCurrency(Math.abs(totals.plValue), currency)}`}
          tone={totalsTone}
          hint="Sample data"
        />
        <StatTile
          label="Profit / loss %"
          value={`${totals.plPct >= 0 ? "+" : "-"}${Math.abs(totals.plPct).toFixed(1)}%`}
          tone={totalsTone}
          hint="Sample data"
        />
      </div>

      <PriceChart pies={siblingPies} seedKey={`pie:${pieId}`} subjectLabel="This portfolio" />

      <div className="ec-section-head">
        <h2 className="ec-section-title">Holdings</h2>
      </div>

      {(pie.holdings ?? []).length === 0 ? (
        <EmptyState
          title="No holdings yet"
          description="Add holdings and set their allocation from the Edit action above."
        />
      ) : (
        <div className="ec-detail-row-list">
          {pie.holdings.map((holding) => {
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
                onClick={() => navigate(`/holdings/${holding.ticker}`)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    navigate(`/holdings/${holding.ticker}`);
                  }
                }}
              >
                <div className="ec-detail-row-main">
                  <h3 className="ec-detail-row-name">
                    {name ? `${name} (${holding.ticker})` : holding.ticker}
                  </h3>
                  <span className="ec-detail-row-meta">{holding.allocation_pct}% allocated</span>
                </div>
                <div className="ec-detail-row-value">
                  <span className="ec-detail-row-current">
                    {formatCurrency(sample.currentValue, currency)}
                  </span>
                  <span className={`ec-detail-row-pl ${tone}`}>
                    {plSign}
                    {formatCurrency(Math.abs(sample.plValue), currency)} ({plSign}
                    {Math.abs(sample.plPct).toFixed(1)}%)
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

      <HoldingsHeatmap tickers={tickers} />

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

        <div className="ec-section-head">
          <h3 className="ec-section-title">Holdings</h3>
        </div>
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
