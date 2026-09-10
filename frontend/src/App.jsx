import { useEffect } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth.jsx";
import CookieBanner from "./components/cookies/CookieBanner.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AccountsListPage from "./pages/accounts/AccountsListPage.jsx";
import AccountDetailPage from "./pages/accounts/AccountDetailPage.jsx";
import PieDetailPage from "./pages/pies/PieDetailPage.jsx";
import SearchPage from "./pages/search/SearchPage.jsx";
import HoldingTickerPage from "./pages/holdings/HoldingTickerPage.jsx";
import CookiePolicyPage from "./pages/CookiePolicyPage.jsx";
import { initAnalytics, trackPageview } from "./utils/analytics.js";

function App() {
  const location = useLocation();

  useEffect(() => {
    initAnalytics();
  }, []);

  useEffect(() => {
    trackPageview(location.pathname + location.search);
  }, [location]);

  return (
    <>
      <Routes>
        <Route path="/cookie-policy" element={<CookiePolicyPage />} />
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
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
      <CookieBanner />
    </>
  );
}

export default App;
