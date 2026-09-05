import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import AccountsListPage from "./pages/accounts/AccountsListPage.jsx";
import AccountDetailPage from "./pages/accounts/AccountDetailPage.jsx";
import PieDetailPage from "./pages/pies/PieDetailPage.jsx";
import HoldingTickerPage from "./pages/holdings/HoldingTickerPage.jsx";

function App() {
  return (
    <Routes>
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
        <Route path="/holdings/:ticker" element={<HoldingTickerPage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
