import Logo from "../brand/Logo.jsx";
import "./SiteFooter.css";

/**
 * The equiCast brand footer + data-source/no-advice disclaimer, shared
 * between SignInScreen (the logged-out landing page) and DashboardPage
 * (the logged-in landing page) so the two stay identical rather than two
 * copies of this same legal text drifting apart.
 */
function SiteFooter() {
  return (
    <>
      <footer className="ec-landing-foot">
        <Logo compact />
        <span>© {new Date().getFullYear()} equiCast</span>
      </footer>

      <section className="ec-disclaimer">
        <p>
          Market data refreshes on a periodic ingestion cycle (every 6 hours), not a live
          real-time feed — prices and figures shown may lag the market by up to a few hours.
          equiCast is built for long-term investment analysis and forecasting, not intraday or
          high-frequency trading.
        </p>
        <p>
          Market, dividend and corporate-events data referenced on this page is sourced via Yahoo
          Finance (through the open-source yfinance library), for educational and informational
          purposes only — this is not financial advice, and equiCast is not a registered
          investment adviser or broker-dealer. Risk and valuation metrics such as volatility,
          Sharpe ratio, max drawdown and CAGR are calculated by equiCast itself where Yahoo
          Finance doesn&rsquo;t provide them directly, and are not sourced from a licensed data
          provider — validate their accuracy independently before relying on them. Nothing on
          this page is a recommendation to buy, sell or hold any security or currency, and past
          performance or illustrative figures are not indicative of future results. Always do
          your own research or consult a licensed financial advisor before making investment
          decisions.
        </p>
      </section>
    </>
  );
}

export default SiteFooter;
