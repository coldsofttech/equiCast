import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
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
import { useApi } from "../../api/useApi.js";
import { deleteAccount, getAccount, updateAccount } from "../../api/accounts.js";
import { deletePie } from "../../api/pies.js";
import { MENU_ITEMS } from "../menuItems.js";
import { INDUSTRY_DATA, SECTOR_DATA, SECTOR_SCORE } from "../diversificationSampleData.js";
import "./AccountDetailPage.css";

function AccountDetailPage() {
  const { accountId } = useParams();
  const api = useApi();
  const navigate = useNavigate();

  const [account, setAccount] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const [isCreatePortfolioOpen, setIsCreatePortfolioOpen] = useState(false);

  const [deletingPieId, setDeletingPieId] = useState(null);
  const [pieDeleteError, setPieDeleteError] = useState(null);

  const load = () => {
    setIsLoading(true);
    setLoadError(null);
    getAccount(api, accountId)
      .then(setAccount)
      .catch((err) => setLoadError(err.message ?? "Couldn't load this account."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [api, accountId]);

  const handleUpdate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    updateAccount(api, accountId, values)
      .then((updated) => {
        setAccount((current) => ({ ...current, ...updated }));
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
      .then(() => navigate("/accounts"))
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the account."))
      .finally(() => setIsDeleting(false));
  };

  const handlePortfolioCreated = (pie) => {
    setAccount((current) => ({ ...current, pies: [...(current.pies ?? []), pie] }));
  };

  const handlePortfolioHoldingsSaved = (updatedPie) => {
    setAccount((current) => ({
      ...current,
      pies: current.pies.map((p) => (p.id === updatedPie.id ? updatedPie : p)),
    }));
  };

  const handleDeletePie = (pie) => {
    setPieDeleteError(null);
    deletePie(api, pie.id, { force: (pie.holdings?.length ?? 0) > 0 })
      .then(() => {
        setAccount((current) => ({
          ...current,
          pies: current.pies.filter((p) => p.id !== pie.id),
        }));
        setDeletingPieId(null);
      })
      .catch((err) => setPieDeleteError(err.message ?? "Couldn't delete the pie."));
  };

  if (isLoading) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Loading…">
        <p className="ec-loading">Loading…</p>
      </AppShell>
    );
  }

  if (loadError || !account) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Account">
        <Alert tone="danger">{loadError ?? "Account not found."}</Alert>
      </AppShell>
    );
  }

  const pieBeingDeleted = account.pies?.find((p) => p.id === deletingPieId);
  const directHoldings = account.holdings ?? [];
  const allTickers = [
    ...directHoldings.map((h) => h.ticker),
    ...(account.pies ?? []).flatMap((p) => (p.holdings ?? []).map((h) => h.ticker)),
  ];

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Portfolio"
      title={account.name}
      subtitle={account.description}
      actions={
        <>
          <Button variant="secondary" onClick={() => setIsEditOpen(true)}>
            Edit
          </Button>
          <Button variant="danger" onClick={() => setIsDeleteOpen(true)}>
            Delete
          </Button>
        </>
      }
    >
      <div className="ec-account-detail-badges">
        <Badge tone="accent">{account.account_type}</Badge>
        <Badge tone="neutral">{account.currency}</Badge>
        <Badge tone={account.transaction_type === "TRANSACTION" ? "purple" : "info"}>
          {account.transaction_type === "TRANSACTION" ? "Per-transaction" : "Average cost"}
        </Badge>
      </div>

      <div className="ec-stat-grid">
        <StatTile label="Total invested" value="—" hint="Coming soon" />
        <StatTile label="Profit / loss" value="—" hint="Coming soon" />
        <StatTile label="Profit / loss %" value="—" hint="Coming soon" />
      </div>

      <PriceChart pies={account.pies ?? []} seedKey={`account:${accountId}`} subjectLabel="This account" />

      <div className="ec-section-head">
        <h2 className="ec-section-title">Portfolios</h2>
        <Button variant="primary" size="sm" onClick={() => setIsCreatePortfolioOpen(true)}>
          <i className="bi bi-plus-lg" aria-hidden="true" />
          Create portfolio
        </Button>
      </div>

      {pieDeleteError && <Alert tone="danger">{pieDeleteError}</Alert>}

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
        <div className="ec-account-grid">
          {account.pies.map((pie) => (
            <Card
              key={pie.id}
              className="ec-account-card"
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
              <div className="ec-account-card-head">
                <h3 className="ec-account-card-name">{pie.name}</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(event) => {
                    event.stopPropagation();
                    setDeletingPieId(pie.id);
                  }}
                >
                  Delete
                </Button>
              </div>
              <p className="ec-account-card-desc">{pie.description}</p>
              <span className="ec-account-card-count">{(pie.holdings ?? []).length} holdings</span>
            </Card>
          ))}
        </div>
      )}

      <div className="ec-section-head">
        <h2 className="ec-section-title">Holdings</h2>
      </div>

      {directHoldings.length === 0 ? (
        <EmptyState
          title="No direct holdings"
          description="Holdings added straight to this account (not inside a pie) will show up here."
        />
      ) : (
        <div className="ec-table-wrap">
          <table className="ec-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Asset class</th>
              </tr>
            </thead>
            <tbody>
              {directHoldings.map((holding) => (
                <tr key={holding.id}>
                  <td className="ec-table-name">{holding.ticker}</td>
                  <td>
                    <Badge tone="neutral">{holding.asset_class}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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

      <HoldingsHeatmap tickers={allTickers} />

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
        onHoldingsSaved={handlePortfolioHoldingsSaved}
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

      <ConfirmDialog
        open={Boolean(deletingPieId)}
        title="Delete pie"
        message={
          pieBeingDeleted && (pieBeingDeleted.holdings?.length ?? 0) > 0
            ? "This pie still has holdings. Deleting it will also delete them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the pie. This can't be undone."
        }
        confirmLabel="Delete pie"
        onConfirm={() => pieBeingDeleted && handleDeletePie(pieBeingDeleted)}
        onCancel={() => setDeletingPieId(null)}
      />
    </AppShell>
  );
}

export default AccountDetailPage;
