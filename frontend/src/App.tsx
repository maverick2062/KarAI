import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { NavBar } from "./components/NavBar";
import { GuidedTour } from "./components/GuidedTour";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Dashboard } from "./pages/Dashboard";
import { TransactionIngestion } from "./pages/TransactionIngestion";
import { TDSEvents } from "./pages/TDSEvents";
import { AdvanceTaxPlanner } from "./pages/AdvanceTaxPlanner";
import { Reports } from "./pages/Reports";
import { Settings } from "./pages/Settings";

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <NavBar />
      <main className="app-layout__content">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <AppLayout>
                <Dashboard />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/transactions"
          element={
            <ProtectedRoute>
              <AppLayout>
                <TransactionIngestion />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/tds-events"
          element={
            <ProtectedRoute>
              <AppLayout>
                <TDSEvents />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/advance-tax"
          element={
            <ProtectedRoute>
              <AppLayout>
                <AdvanceTaxPlanner />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <AppLayout>
                <Reports />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <AppLayout>
                <Settings />
              </AppLayout>
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
      <GuidedTour />
    </AuthProvider>
  );
}
