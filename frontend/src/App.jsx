import { useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth.jsx";
import CookieBanner from "./components/cookies/CookieBanner.jsx";
import ErrorBoundary from "./components/errors/ErrorBoundary.jsx";
import AppErrorPage from "./pages/errors/AppErrorPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AccountsListPage from "./pages/accounts/AccountsListPage.jsx";
import GoalsListPage from "./pages/goals/GoalsListPage.jsx";
import AccountDetailPage from "./pages/accounts/AccountDetailPage.jsx";
import PieDetailPage from "./pages/pies/PieDetailPage.jsx";
import SearchPage from "./pages/search/SearchPage.jsx";
import HoldingTickerPage from "./pages/holdings/HoldingTickerPage.jsx";
import CookiePolicyPage from "./pages/CookiePolicyPage.jsx";
import { initAnalytics, trackPageview } from "./utils/analytics.js";
import WatchlistsPage from "./pages/watchlists/WatchlistsPage.jsx";
import ImportPage from "./pages/import/ImportPage.jsx";
import SupportPage from "./pages/support/SupportPage.jsx";
import NotFoundPage from "./pages/errors/NotFoundPage.jsx";
import TermsAndConditionsPage from "./pages/TermsAndConditionsPage.jsx";
import PrivacyPolicyPage from "./pages/PrivacyPolicyPage.jsx";

function App() {
  const location = useLocation();

  useEffect(() => {
    initAnalytics();
  }, []);

  useEffect(() => {
    trackPageview(location.pathname + location.search);
  }, [location]);

  return (
    <ErrorBoundary fallback={<AppErrorPage />}>
      <Routes>
        <Route path="/cookie-policy" element={<CookiePolicyPage />} />
        <Route path="/terms-and-conditions" element={<TermsAndConditionsPage />} />
        <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
        <Route
          element={
            <RequireAuth>
              <Outlet />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/accounts" element={<AccountsListPage />} />
          <Route path="/accounts/:accountId" element={<AccountDetailPage />} />
          <Route path="/accounts/:accountId/pies/:pieId" element={<PieDetailPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/holdings/:ticker" element={<HoldingTickerPage />} />
          <Route path="/watchlists" element={<WatchlistsPage />} />
          <Route path="/goals" element={<GoalsListPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/support" element={<SupportPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
      <CookieBanner />
    </ErrorBoundary>
  );
}

export default App;
