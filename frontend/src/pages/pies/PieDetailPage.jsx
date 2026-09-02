import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Card from "../../components/core/Card.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
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

/**
 * One portfolio's own overview page — same shape as AccountDetailPage
 * (placeholder stats, a consolidated price chart, a holdings section,
 * bottom-of-page diversification/heatmap), scoped to this pie's own
 * holdings instead of the whole account's. The holdings section reuses
 * AllocationEditor exactly as before (add/remove/reallocate — the only way
 * to mutate a pie's holdings), now with ticker search + the allocation
 * ring built in.
 */
function PieDetailPage() {
  const { accountId, pieId } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const { setAccounts: setCachedAccounts } = useAccounts();

  const [pie, setPie] = useState(null);
  const [siblingPies, setSiblingPies] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

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
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Loading…">
        <p className="ec-loading">Loading…</p>
      </AppShell>
    );
  }

  if (loadError || !pie) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Pie">
        <Alert tone="danger">{loadError ?? "Pie not found."}</Alert>
      </AppShell>
    );
  }

  const tickers = (pie.holdings ?? []).map((h) => h.ticker);

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
          <Button variant="secondary" onClick={() => setIsEditOpen(true)}>
            Edit
          </Button>
          <Button variant="danger" onClick={() => setIsDeleteOpen(true)}>
            Delete
          </Button>
        </>
      }
    >
      <div className="ec-stat-grid">
        <StatTile label="Total invested" value="—" hint="Coming soon" />
        <StatTile label="Profit / loss" value="—" hint="Coming soon" />
        <StatTile label="Profit / loss %" value="—" hint="Coming soon" />
      </div>

      <PriceChart pies={siblingPies} seedKey={`pie:${pieId}`} subjectLabel="This portfolio" />

      <div className="ec-section-head">
        <h2 className="ec-section-title">Holdings</h2>
      </div>

      <Card>
        <AllocationEditor
          holdings={pie.holdings ?? []}
          onSave={handleSaveAllocation}
          isSaving={isAllocationSaving}
          error={allocationError}
        />
      </Card>

      <DiversificationChart
        title="Sector diversification"
        score={SECTOR_SCORE}
        data={SECTOR_DATA}
        caption="Illustrative sample data — sector classification isn't wired up to real holdings yet."
      />

      <DiversificationChart
        title="Industry diversification"
        data={INDUSTRY_DATA}
        caption="Illustrative sample data — industry classification isn't wired up to real holdings yet."
      />

      <HoldingsHeatmap tickers={tickers} />

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
