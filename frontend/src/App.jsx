import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth.jsx";
import AccountsListPage from "./pages/accounts/AccountsListPage.jsx";
import AccountDetailPage from "./pages/accounts/AccountDetailPage.jsx";
import PieDetailPage from "./pages/pies/PieDetailPage.jsx";

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
        <Route path="/" element={<Navigate to="/accounts" replace />} />
        <Route path="/accounts" element={<AccountsListPage />} />
        <Route path="/accounts/:accountId" element={<AccountDetailPage />} />
        <Route path="/accounts/:accountId/pies/:pieId" element={<PieDetailPage />} />
        <Route path="*" element={<Navigate to="/accounts" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
