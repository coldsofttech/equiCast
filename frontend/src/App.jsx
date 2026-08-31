import { Navigate, Route, Routes } from "react-router-dom";
import RequireAuth from "./auth/RequireAuth.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
