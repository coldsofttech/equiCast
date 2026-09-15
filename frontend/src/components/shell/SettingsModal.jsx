import { useEffect, useState } from "react";
import Modal from "../core/Modal.jsx";
import ConfirmDialog from "../core/ConfirmDialog.jsx";
import { SelectField, TextField } from "../core/Field.jsx";
import Button from "../core/Button.jsx";
import Alert from "../core/Alert.jsx";
import { useApi } from "../../api/useApi.js";
import {
  deleteAccount,
  updateDefaultCurrency,
  updateFxWarmupCurrencies,
  updateIncomeTaxBand,
  updateTaxResidency,
  updateTransactionType,
} from "../../api/identity.js";
import { clearAllCaches } from "../../utils/marketDataCache.js";
import CURRENCIES from "../../config/currencies.json";
import "./SettingsModal.css";

/** Matches equicast_core.user_profiles.DEFAULT_FX_WARMUP_CURRENCIES — used
 * only as this form's fallback when `profile.fx_warmup_currencies` hasn't
 * loaded yet (the same "seed from the backend default until we know
 * otherwise" reasoning as `currency`/`transactionType` below). */
const DEFAULT_FX_WARMUP_CURRENCIES = ["GBP", "USD", "EUR"];

/** GitHub issue #158 — the exact phrase a user must type into the
 * delete-account confirmation field before the Delete button enables. */
const DELETE_CONFIRM_PHRASE = "DELETE";

/**
 * Opened from UserMenu's "Settings" item. Three settings: default_currency
 * (options from the bundled currencies.json — no API call to fetch them,
 * see identity.js's updateDefaultCurrency doc — rather than a closed
 * `<select>` fetched at runtime), transaction_type (a single global
 * setting governing how every holding across every account/pie records
 * transactions — see equicast_core.transactions module docstring; the
 * backend rejects the change with a 409 once the user has any transaction
 * recorded anywhere, surfaced here as `error`), and fx_warmup_currencies
 * (GitHub issue #149 — which currencies the login-time FX warm-up, see
 * utils/fxWarmup.js, pairs against `default_currency`), tax_residency and
 * income_tax_band (GitHub issue #94 — v1 tax logic is UK-only, so
 * tax_residency only ever offers "UK" for now; income_tax_band is a
 * self-declared band, always per-user, never household-pooled).
 *
 * Each setting saves independently (its own PATCH) so changing one doesn't
 * require re-submitting the others, and a transaction_type 409 doesn't
 * block a currency/warm-up-list change made in the same visit.
 *
 * Also has a "Danger zone" section (GitHub issue #158) for permanently
 * deleting the caller's equicast account — every accounts/pies/goals/
 * watchlists/holdings/transactions record, plus their profile. Gated
 * behind typing "DELETE" into a confirmation field (stronger than the
 * plain confirm/cancel `ConfirmDialog` the cache-reset section above
 * uses, given how much more this destroys) in its own nested `Modal`.
 * `onAccountDeleted` is called once the DELETE succeeds — UserMenu wires
 * it to the same cache-clear-then-Auth0-logout flow its own sign-out
 * button uses, since a deleted account has nothing left to stay signed
 * into (v1 scope only deletes equicast's own data, not the Auth0
 * identity itself — see the issue).
 */
function SettingsModal({ open, onClose, profile, onSaved, onAccountDeleted }) {
  const api = useApi();
  const [currency, setCurrency] = useState(profile?.default_currency ?? CURRENCIES[0].code);
  const [transactionType, setTransactionType] = useState(profile?.transaction_type ?? "AVERAGE");
  const [fxWarmupCurrencies, setFxWarmupCurrencies] = useState(
    profile?.fx_warmup_currencies ?? DEFAULT_FX_WARMUP_CURRENCIES
  );
  const [taxResidency, setTaxResidency] = useState(profile?.tax_residency ?? "UK");
  const [incomeTaxBand, setIncomeTaxBand] = useState(profile?.income_tax_band ?? "BASIC");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  // GitHub issue #184: wipes every account/pie/holding/price/dividend/etc.
  // cached in IndexedDB (see marketDataCache.js's clearAllCaches) — nothing
  // here touches the sessionStorage-backed profile/greeting caches, since
  // the issue's own scope is specifically "clears all the indexed db".
  // Confirmed via ConfirmDialog first since the resulting re-download can
  // noticeably slow down the next few pages the user opens; on success this
  // just shows a done message rather than reloading, so an in-progress edit
  // elsewhere on the page isn't interrupted — the cache empties immediately,
  // and whatever's already on screen keeps showing until the user next
  // navigates or refreshes.
  const [isResetCacheConfirmOpen, setIsResetCacheConfirmOpen] = useState(false);
  const [isResettingCache, setIsResettingCache] = useState(false);
  const [cacheResetDone, setCacheResetDone] = useState(false);

  // GitHub issue #158: permanently deletes the caller's equicast account.
  // deleteConfirmText is compared against DELETE_CONFIRM_PHRASE to gate the
  // Delete button, same "must type an exact phrase" pattern as GitHub's own
  // repo-deletion confirmation.
  const [isDeleteAccountOpen, setIsDeleteAccountOpen] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  // SettingsModal stays mounted between opens (only its inner <Modal> un/
  // remounts visually, see UserMenu.jsx), so without this a "Cache cleared"
  // message (or a stale delete-account error/confirmation text) from a
  // previous visit would still be showing the next time the drawer is
  // reopened.
  useEffect(() => {
    if (open) {
      setCacheResetDone(false);
      setIsResetCacheConfirmOpen(false);
      setIsDeleteAccountOpen(false);
      setDeleteConfirmText("");
      setDeleteError(null);
    }
  }, [open]);

  const handleResetCache = () => {
    setIsResettingCache(true);
    clearAllCaches().then(() => {
      setIsResettingCache(false);
      setIsResetCacheConfirmOpen(false);
      setCacheResetDone(true);
    });
  };

  const handleDeleteAccount = () => {
    setIsDeletingAccount(true);
    setDeleteError(null);
    deleteAccount(api)
      .then(() => onAccountDeleted())
      .catch((err) => {
        setDeleteError(err.message ?? "Couldn't delete your account.");
        setIsDeletingAccount(false);
      });
  };

  const toggleFxWarmupCurrency = (code) => {
    setFxWarmupCurrencies((current) =>
      current.includes(code) ? current.filter((c) => c !== code) : [...current, code]
    );
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);

    const currencyChanged = currency !== (profile?.default_currency ?? CURRENCIES[0].code);
    const transactionTypeChanged = transactionType !== (profile?.transaction_type ?? "AVERAGE");
    const originalFxWarmupCurrencies = profile?.fx_warmup_currencies ?? DEFAULT_FX_WARMUP_CURRENCIES;
    const fxWarmupCurrenciesChanged =
      JSON.stringify([...fxWarmupCurrencies].sort()) !==
      JSON.stringify([...originalFxWarmupCurrencies].sort());
    const taxResidencyChanged = taxResidency !== (profile?.tax_residency ?? "UK");
    const incomeTaxBandChanged = incomeTaxBand !== (profile?.income_tax_band ?? "BASIC");

    Promise.resolve(currencyChanged ? updateDefaultCurrency(api, currency) : profile)
      .then((updated) =>
        transactionTypeChanged ? updateTransactionType(api, transactionType) : updated
      )
      .then((updated) =>
        fxWarmupCurrenciesChanged ? updateFxWarmupCurrencies(api, fxWarmupCurrencies) : updated
      )
      .then((updated) => (taxResidencyChanged ? updateTaxResidency(api, taxResidency) : updated))
      .then((updated) =>
        incomeTaxBandChanged ? updateIncomeTaxBand(api, incomeTaxBand) : updated
      )
      .then((updated) => {
        onSaved(updated);
        onClose();
      })
      .catch((err) => setError(err.message ?? "Couldn't update your settings."))
      .finally(() => setIsSaving(false));
  };

  return (
    <Modal open={open} onClose={onClose} title="Settings">
      <form onSubmit={handleSubmit} className="ec-form">
        {error && <Alert tone="danger">{error}</Alert>}
        <SelectField
          id="settings-default-currency"
          label="Default currency"
          value={currency}
          onChange={(event) => setCurrency(event.target.value)}
          hint="Used to value your accounts consistently across currencies."
        >
          {CURRENCIES.map((option) => (
            <option key={option.code} value={option.code}>
              {option.code} — {option.name}
            </option>
          ))}
        </SelectField>
        <SelectField
          id="settings-transaction-type"
          label="Transaction type"
          value={transactionType}
          onChange={(event) => setTransactionType(event.target.value)}
          hint="AVERAGE tracks one running average cost per holding; TRANSACTION keeps every buy/sell separately. Locked once you have any transaction recorded."
        >
          <option value="AVERAGE">Average cost</option>
          <option value="TRANSACTION">Per-transaction</option>
        </SelectField>
        <SelectField
          id="settings-tax-residency"
          label="Tax residency"
          value={taxResidency}
          onChange={(event) => setTaxResidency(event.target.value)}
          hint="Currently only UK is supported. Upcoming release to include more"
        >
          <option value="UK">UK</option>
        </SelectField>
        <SelectField
          id="settings-income-tax-band"
          label="Income tax band"
          value={incomeTaxBand}
          onChange={(event) => setIncomeTaxBand(event.target.value)}
          hint="Self-declared — used to work out the tax due on GIA income once outside your dividend/CGT allowance. ISA/SIPP/LISA/JISA holdings are unaffected."
        >
          <option value="NONE">Non-taxpayer (0%)</option>
          <option value="BASIC">Basic rate (20%)</option>
          <option value="HIGHER">Higher rate (40%)</option>
          <option value="ADDITIONAL">Additional rate (45%)</option>
        </SelectField>
        <div className="ec-field">
          <span className="ec-field-label">FX warm-up currencies</span>
          <div className="ec-settings-fx-warmup-list">
            {CURRENCIES.map((option) => (
              <label key={option.code} className="ec-settings-fx-warmup-item">
                <input
                  type="checkbox"
                  checked={fxWarmupCurrencies.includes(option.code)}
                  onChange={() => toggleFxWarmupCurrency(option.code)}
                />
                {option.code}
              </label>
            ))}
          </div>
          <span className="ec-field-hint">
            Pre-warmed against your default currency when you sign in, so adding a transaction in
            one of these doesn&rsquo;t wait on a fresh FX lookup.
          </span>
        </div>
        <div className="ec-form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" isLoading={isSaving}>
            Save
          </Button>
        </div>
      </form>

      <div className="ec-settings-cache-section">
        <span className="ec-field-label">Cache</span>
        {cacheResetDone ? (
          <Alert tone="success">
            Cache cleared. Accounts, pies, and holdings will re-download from the network the next
            time you open them.
          </Alert>
        ) : (
          <>
            <p className="ec-field-hint">
              Clears every account, pie, and holding cached on this device. The next pages you open
              will re-download that information from the network instead, which can take a little
              longer than usual to load.
            </p>
            <Button type="button" variant="secondary" onClick={() => setIsResetCacheConfirmOpen(true)}>
              Reset cache
            </Button>
          </>
        )}
      </div>

      <ConfirmDialog
        open={isResetCacheConfirmOpen}
        title="Reset cache"
        message="This clears every account, pie, and holding cached on this device. They'll be re-downloaded from the network the next time you open them, which could take a little longer than usual to load. This can't be undone."
        confirmLabel="Reset cache"
        isLoading={isResettingCache}
        onConfirm={handleResetCache}
        onCancel={() => setIsResetCacheConfirmOpen(false)}
      />

      <div className="ec-settings-danger-section">
        <span className="ec-field-label">Danger zone</span>
        <p className="ec-field-hint">
          Permanently deletes your equicast account — every account, pie, goal, watchlist,
          holding, and transaction. This can&rsquo;t be undone.
        </p>
        <Button
          type="button"
          variant="danger"
          onClick={() => {
            setDeleteError(null);
            setDeleteConfirmText("");
            setIsDeleteAccountOpen(true);
          }}
        >
          Delete my account
        </Button>
      </div>

      <Modal
        open={isDeleteAccountOpen}
        onClose={() => (isDeletingAccount ? undefined : setIsDeleteAccountOpen(false))}
        title="Delete my account"
        footer={
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setIsDeleteAccountOpen(false)}
              disabled={isDeletingAccount}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={handleDeleteAccount}
              isLoading={isDeletingAccount}
              disabled={deleteConfirmText !== DELETE_CONFIRM_PHRASE}
            >
              Delete my account
            </Button>
          </>
        }
      >
        {deleteError && <Alert tone="danger">{deleteError}</Alert>}
        <p>
          This permanently deletes every account, pie, goal, watchlist, holding, and transaction
          you have on equicast. There&rsquo;s no undo, and no recovery once it&rsquo;s done.
        </p>
        <TextField
          id="settings-delete-confirm"
          label={`Type ${DELETE_CONFIRM_PHRASE} to confirm`}
          value={deleteConfirmText}
          onChange={(event) => setDeleteConfirmText(event.target.value)}
          disabled={isDeletingAccount}
          autoComplete="off"
        />
      </Modal>
    </Modal>
  );
}

export default SettingsModal;
