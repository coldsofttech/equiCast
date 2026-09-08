import { useEffect, useState } from "react";
import Card from "../../components/core/Card.jsx";
import Tabs from "../../components/core/Tabs.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import TickerSearchField from "../pies/TickerSearchField.jsx";
import WatchlistForm from "./WatchlistForm.jsx";
import WatchlistEntryCard from "./WatchlistEntryCard.jsx";
import { useApi } from "../../api/useApi.js";
import {
  listWatchlists,
  createWatchlist,
  updateWatchlist,
  deleteWatchlist,
} from "../../api/watchlists.js";
import { createHolding, deleteHolding } from "../../api/holdings.js";
import "./WatchlistsPanel.css";

/**
 * The /dashboard watchlists panel: one Card, tabbed across the five system
 * defaults (see backend/watchlists/views.py's SYSTEM_WATCHLISTS — always
 * present, always first) followed by the caller's own custom watchlists
 * (up to MAX_WATCHLISTS, currently 5). Global Markets, Top Winners, and Top
 * Losers are the three system tabs with real content — built weekly by
 * equicast-watchlist (packages/watchlist) and read back via
 * `_SYSTEM_WATCHLIST_STORAGE_KEYS` in the backend view (Top Winners/Losers
 * rank the whole stock/ETF universe by trailing 1-year CAGR — see
 * equicast_watchlist.movers — rather than Global Markets' hand-curated fx/
 * future/benchmark list); the two "(Your Accounts)" tabs still come back
 * with `holdings: []` until their own population logic exists. A custom
 * watchlist's holdings are real — added/removed here via the same
 * POST/DELETE /api/holdings/ a direct account holding uses (see
 * TickerSearchField/handleAddHolding), just with `watchlist_id` instead of
 * `account_id` and never a nested transaction (watchlist holdings don't
 * carry shares/cost basis — see HoldingListView.post). Every entry, system
 * or custom, renders as the same WatchlistEntryCard (logo/name/ticker/
 * native price/1w+1m change, plus 1y change for Top Winners/Losers) — a
 * system tab is otherwise read-only: no rename/delete, no add/remove-
 * holding controls.
 */
function WatchlistsPanel() {
  const api = useApi();

  const [watchlists, setWatchlists] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [activeId, setActiveId] = useState(null);

  const load = () => {
    setIsLoading(true);
    setLoadError(null);
    listWatchlists(api)
      .then((result) => {
        setWatchlists(result);
        setActiveId((current) => current ?? result[0]?.id ?? null);
      })
      .catch((err) => setLoadError(err.message ?? "Couldn't load watchlists."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [api]);

  const active = watchlists.find((w) => w.id === activeId) ?? null;

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const closeCreate = () => {
    setIsCreateOpen(false);
    setSaveError(null);
  };

  const handleCreate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    createWatchlist(api, values)
      .then((created) => {
        setWatchlists((current) => [...current, created]);
        setActiveId(created.id);
        closeCreate();
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't create the watchlist."))
      .finally(() => setIsSaving(false));
  };

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isEditSaving, setIsEditSaving] = useState(false);
  const [editError, setEditError] = useState(null);

  const closeEdit = () => {
    setIsEditOpen(false);
    setEditError(null);
  };

  const handleEdit = (values) => {
    setIsEditSaving(true);
    setEditError(null);
    updateWatchlist(api, active.id, values)
      .then((updated) => {
        setWatchlists((current) => current.map((w) => (w.id === updated.id ? { ...w, ...updated } : w)));
        closeEdit();
      })
      .catch((err) => setEditError(err.message ?? "Couldn't update the watchlist."))
      .finally(() => setIsEditSaving(false));
  };

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deleteWatchlist(api, active.id, { force: (active.holdings?.length ?? 0) > 0 })
      .then(() => {
        setWatchlists((current) => current.filter((w) => w.id !== active.id));
        setActiveId(watchlists[0]?.id ?? null);
        setIsDeleteOpen(false);
      })
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the watchlist."))
      .finally(() => setIsDeleting(false));
  };

  const [isAddHoldingOpen, setIsAddHoldingOpen] = useState(false);
  const [addHoldingError, setAddHoldingError] = useState(null);

  const handleAddHolding = ({ ticker, asset_class }) => {
    setAddHoldingError(null);
    if ((active.holdings ?? []).some((h) => h.ticker === ticker)) {
      setAddHoldingError(`${ticker} is already on this watchlist.`);
      return;
    }
    createHolding(api, { ticker, asset_class, watchlist_id: active.id })
      .then((holding) => {
        setWatchlists((current) =>
          current.map((w) =>
            w.id === active.id ? { ...w, holdings: [...(w.holdings ?? []), holding] } : w
          )
        );
      })
      .catch((err) => setAddHoldingError(err.message ?? "Couldn't add the holding."));
  };

  const handleRemoveHolding = (holdingId) => {
    deleteHolding(api, holdingId).then(() => {
      setWatchlists((current) =>
        current.map((w) =>
          w.id === active.id ? { ...w, holdings: (w.holdings ?? []).filter((h) => h.id !== holdingId) } : w
        )
      );
    });
  };

  return (
    <div className="ec-watchlist-section">
      <div className="ec-section-head">
        <h2 className="ec-section-title">Watchlists</h2>
        <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
          <i className="bi bi-plus-lg" aria-hidden="true" />
          New watchlist
        </Button>
      </div>

      <Card className="ec-watchlist-panel">
        {isLoading && <p className="ec-loading">Loading…</p>}
        {loadError && <Alert tone="danger">{loadError}</Alert>}

        {!isLoading && !loadError && (
          <>
            <Tabs
              tabs={watchlists.map((w) => ({
                id: w.id,
                label: w.name,
                badge: w.holdings?.length ?? 0,
              }))}
              activeId={activeId}
              onChange={setActiveId}
            />

            {active && (
              <div className="ec-watchlist-tab-content">
                {active.type === "custom" && (
                  <div className="ec-watchlist-tab-actions">
                    {active.description && <p className="ec-watchlist-tab-desc">{active.description}</p>}
                    <div className="ec-watchlist-tab-buttons">
                      <Button variant="secondary" size="sm" onClick={() => setIsAddHoldingOpen(true)}>
                        <i className="bi bi-plus-lg" aria-hidden="true" />
                        Add holding
                      </Button>
                      <button
                        type="button"
                        className="ec-icon-btn"
                        aria-label={`Rename ${active.name}`}
                        onClick={() => setIsEditOpen(true)}
                      >
                        <i className="bi bi-pencil" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="ec-icon-btn ec-icon-btn--danger"
                        aria-label={`Delete ${active.name}`}
                        onClick={() => setIsDeleteOpen(true)}
                      >
                        <i className="bi bi-trash" aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                )}

                {(active.holdings ?? []).length === 0 ? (
                  <EmptyState
                    title="No holdings yet"
                    description={
                      active.type === "system"
                        ? "No entries published for this watchlist yet — check back after the next update."
                        : "Search for a ticker to add it to this watchlist."
                    }
                    action={
                      active.type === "custom" && (
                        <Button variant="primary" onClick={() => setIsAddHoldingOpen(true)}>
                          Add holding
                        </Button>
                      )
                    }
                  />
                ) : (
                  <div className="ec-watchlist-card-grid">
                    {active.holdings.map((holding) => (
                      <WatchlistEntryCard
                        key={holding.id ?? holding.ticker}
                        holding={holding}
                        isRemovable={active.type === "custom"}
                        onRemove={() => handleRemoveHolding(holding.id)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </Card>

      <Drawer open={isCreateOpen} onClose={closeCreate} title="New watchlist">
        <WatchlistForm
          onSubmit={handleCreate}
          onCancel={closeCreate}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      {active && active.type === "custom" && (
        <>
          <Drawer open={isEditOpen} onClose={closeEdit} title="Edit watchlist">
            <WatchlistForm
              initialValues={active}
              onSubmit={handleEdit}
              onCancel={closeEdit}
              isSubmitting={isEditSaving}
              error={editError}
            />
          </Drawer>

          <Drawer
            open={isAddHoldingOpen}
            onClose={() => {
              setIsAddHoldingOpen(false);
              setAddHoldingError(null);
            }}
            title="Add holding"
          >
            <p className="ec-watchlist-holding-hint">
              Search for a ticker to add it to &ldquo;{active.name}&rdquo;.
            </p>
            {addHoldingError && <Alert tone="danger">{addHoldingError}</Alert>}
            <TickerSearchField onSelect={handleAddHolding} />
          </Drawer>

          <ConfirmDialog
            open={isDeleteOpen}
            title="Delete watchlist"
            message={
              (active.holdings?.length ?? 0) > 0
                ? "This watchlist still has holdings on it. Deleting it will remove them too. This can't be undone."
                : "This will permanently delete the watchlist. This can't be undone."
            }
            confirmLabel="Delete watchlist"
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
        </>
      )}
    </div>
  );
}

export default WatchlistsPanel;
