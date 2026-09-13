import { useEffect, useState } from "react";
import { useApi } from "../../api/useApi.js";
import {
  formatDividendDate,
  formatPrice,
  resolveFxRate,
  selectActiveDeclaredDividend,
} from "./holdingFinancials.js";
import "./HoldingTickerPage.css";

const DISMISS_KEY_PREFIX = "ec-dividend-banner-dismissed:";

/** The ex-dividend date this ticker's banner was last dismissed for, or
 * null if it's never been dismissed (or storage is unavailable) — keyed
 * per ticker so dismissing one ticker's banner doesn't hide another's. */
function readDismissedDate(ticker) {
  try {
    return localStorage.getItem(`${DISMISS_KEY_PREFIX}${ticker}`);
  } catch {
    return null;
  }
}

function writeDismissedDate(ticker, exDividendDate) {
  try {
    localStorage.setItem(`${DISMISS_KEY_PREFIX}${ticker}`, exDividendDate);
  } catch {
    // Storage can be unavailable (private browsing, disabled cookies) — the
    // dismissal just won't persist past this page load.
  }
}

/**
 * GitHub issue #186: a slim banner, styled and positioned like Topbar's
 * offline banner (sticky, right below the top bar), announcing a declared
 * dividend for the ticker this /holdings/:ticker page is showing — visible
 * the moment the page loads rather than requiring a scroll down to the
 * Dividends section to notice it. Shows only while the position is
 * actually owned (`isOwned`) and only for a `status === "declared"` record
 * (see `selectActiveDeclaredDividend`) — an "estimated" forecast isn't a
 * real declared event. Stays up through the ex-dividend date itself and
 * disappears once it's passed, same cutoff `selectActiveDeclaredDividend`
 * applies.
 *
 * The close button dismisses it for that specific ex-dividend date only
 * (persisted in localStorage) — a newly-declared dividend later (a
 * different `ex_dividend_date`) shows the banner again rather than staying
 * dismissed forever.
 *
 * The headline figure is the overall payout for the position —
 * `record.price * sharesOwned` — converted to the user's own default
 * currency once `fxRate` resolves (today's rate, same reasoning
 * HoldingDividendsSection's own FX resolution documents: there's no past
 * date to look a historical rate up for a payout that hasn't happened
 * yet), with the native-currency amount kept alongside in parens. Falls
 * back to native-only while the rate is still loading or unresolved
 * (currency unknown, or no default currency to convert to yet).
 */
function HoldingDividendBanner({ ticker, dividends, isOwned, sharesOwned = 0, defaultCurrency = null }) {
  const api = useApi();
  const record = isOwned ? selectActiveDeclaredDividend(dividends?.dividends ?? []) : null;
  const [dismissedDate, setDismissedDate] = useState(() => readDismissedDate(ticker));
  const [fxRate, setFxRate] = useState(null);

  const currency = dividends?.currency ?? null;

  useEffect(() => {
    if (!currency || !defaultCurrency || currency === defaultCurrency) {
      setFxRate(null);
      return undefined;
    }
    let cancelled = false;
    resolveFxRate(api, currency, defaultCurrency).then((rate) => {
      if (!cancelled) setFxRate(rate);
    });
    return () => {
      cancelled = true;
    };
  }, [api, currency, defaultCurrency]);

  if (!record || dismissedDate === record.ex_dividend_date) return null;

  const handleClose = () => {
    writeDismissedDate(ticker, record.ex_dividend_date);
    setDismissedDate(record.ex_dividend_date);
  };

  const amount = record.price * sharesOwned;
  const showConverted = fxRate != null && defaultCurrency && currency !== defaultCurrency;
  const headlineAmount = showConverted ? amount * fxRate : amount;
  const headlineCurrency = showConverted ? defaultCurrency : currency;

  return (
    <div className="ec-dividend-banner" role="status">
      <i className="bi bi-cash-coin" aria-hidden="true" />
      <span>
        {ticker} declared a dividend worth {formatPrice(headlineAmount, headlineCurrency)}
        {showConverted && ` (${formatPrice(amount, currency)})`} — ex-dividend{" "}
        {formatDividendDate(record.ex_dividend_date)}
        {record.payment_date && `, payment ${formatDividendDate(record.payment_date)}`}.
      </span>
      <button
        type="button"
        className="ec-dividend-banner-close"
        onClick={handleClose}
        aria-label="Dismiss dividend banner"
      >
        <i className="bi bi-x-lg" aria-hidden="true" />
      </button>
    </div>
  );
}

export default HoldingDividendBanner;
