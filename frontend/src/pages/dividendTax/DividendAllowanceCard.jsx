import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import GoalProgressBar from "../../components/goals/GoalProgressBar.jsx";
import { formatCurrency } from "../sampleFinancials.js";
import { UK_DIVIDEND_ALLOWANCE, currentUkTaxYearLabel } from "./dividendTaxFinancials.js";
import "../goals/Goals.css";

/**
 * DividendTaxPage's "this tax year, at a glance" summary card — this UK tax
 * year's `dividend_allowance_used_by_tax_year` usage against the fixed £500
 * allowance (GitHub issue #212), same "current value + progress bar" layout
 * GoalCard.jsx uses for a savings goal. Always GBP — see
 * dividendTaxFinancials.js's UK_DIVIDEND_ALLOWANCE comment. Sits above the
 * rest of DividendTaxPage's own full tax-year-by-tax-year table.
 *
 * @param {{ dividendAllowanceUsedByTaxYear: Record<string, number> | undefined }} props
 */
function DividendAllowanceCard({ dividendAllowanceUsedByTaxYear }) {
  const taxYear = currentUkTaxYearLabel();
  const used = dividendAllowanceUsedByTaxYear?.[taxYear] ?? 0;
  const pct = (used / UK_DIVIDEND_ALLOWANCE) * 100;
  const isOverAllowance = used > UK_DIVIDEND_ALLOWANCE;

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">Dividend allowance</h3>
        {isOverAllowance && <Badge tone="warning">Over allowance</Badge>}
      </div>

      <div className="ec-account-card-value">
        <Balance className="ec-account-card-current">{formatCurrency(used, "GBP")}</Balance>
        <span className="ec-goal-card-progress-row">
          <span>
            {Math.round(pct)}% of {formatCurrency(UK_DIVIDEND_ALLOWANCE, "GBP")}
          </span>
        </span>
      </div>

      <GoalProgressBar pct={pct} achieved={isOverAllowance} />

      <span className="ec-chart-caption">Tax year {taxYear}</span>
    </Card>
  );
}

export default DividendAllowanceCard;
