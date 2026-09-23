/**
 * Client-side helpers for GitHub issue #212's UK dividend tax engine —
 * reads `profile.dividend_allowance_used_by_tax_year` (already returned
 * wholesale by GET /identity/me/, see api/identity.js's UserProfile) rather
 * than computing anything server-side doesn't already track. Mirrors
 * `equicast_core.uk_dividend_tax`'s own constants/`uk_tax_year_label` so
 * "today's tax year" always lines up with the key the backend wrote its
 * usage under.
 */

//: Mirrors equicast_core.uk_dividend_tax.UK_DIVIDEND_ALLOWANCE — the first
//: £500 of taxable UK dividend income in a tax year is untaxed. Always GBP,
//: regardless of the user's own default_currency (the backend computes
//: allowance usage in GBP only — see that module's docstring).
export const UK_DIVIDEND_ALLOWANCE = 500;

/**
 * The UK tax year (6 Apr-5 Apr) `date` falls in, as a "YYYY-YY" label (e.g.
 * "2026-27") — mirrors equicast_core.uk_dividend_tax.uk_tax_year_label
 * exactly, so this always agrees with the key the backend stored a given
 * dividend's allowance usage under.
 *
 * @param {Date} date
 * @returns {string}
 */
export function ukTaxYearLabel(date) {
  const year = date.getFullYear();
  const isOnOrAfterTaxYearStart = date.getMonth() + 1 > 4 || (date.getMonth() + 1 === 4 && date.getDate() >= 6);
  const startYear = isOnOrAfterTaxYearStart ? year : year - 1;
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
}

/** `ukTaxYearLabel` for right now — the key to look up in
 * `profile.dividend_allowance_used_by_tax_year` for "this tax year's"
 * allowance usage. */
export function currentUkTaxYearLabel() {
  return ukTaxYearLabel(new Date());
}

/**
 * `profile.dividend_allowance_used_by_tax_year` and
 * `dividend_tax_paid_by_tax_year` (two separately-tracked running totals —
 * see backend/transactions/views.py's _persist_dividend_allowance) merged
 * into one row per tax year, most recent first — DividendTaxPage's table
 * shape. Keyed off the *union* of both maps' tax years rather than just the
 * allowance map's, since a tax year can appear in one without the other
 * (e.g. every dividend that year fell within the allowance, so
 * add_dividend_tax_paid was never called for it — `taxPaid` defaults to `0`
 * in that case, same as an absent `allowanceUsed` would).
 *
 * @param {Record<string, number> | undefined} allowanceByTaxYear
 * @param {Record<string, number> | undefined} taxPaidByTaxYear
 * @returns {{ taxYear: string, allowanceUsed: number, taxPaid: number }[]}
 */
export function sortedDividendTaxRows(allowanceByTaxYear, taxPaidByTaxYear) {
  const taxYears = new Set([
    ...Object.keys(allowanceByTaxYear ?? {}),
    ...Object.keys(taxPaidByTaxYear ?? {}),
  ]);
  return [...taxYears]
    .sort((a, b) => b.localeCompare(a))
    .map((taxYear) => ({
      taxYear,
      allowanceUsed: allowanceByTaxYear?.[taxYear] ?? 0,
      taxPaid: taxPaidByTaxYear?.[taxYear] ?? 0,
    }));
}
