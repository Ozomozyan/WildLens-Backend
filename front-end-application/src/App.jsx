import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext.jsx';
import LoginPage from './pages/LoginPage.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import AdminPanel from './pages/AdminPanel.jsx';
import NotFound from './pages/NotFound.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import SpeciesSummaryPage from "./pages/SpeciesSummaryPage.jsx"; 
import PredictionPage from "./pages/PredictionPage.jsx";
import MapPage from "./pages/MapPage.jsx";
import DataQualityPage from "./pages/DataQualityPage.jsx"; // new
import LogsPage from "./pages/LogsPage.jsx"; // new

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* Authenticated user routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/predict"   element={<PredictionPage />} />   {/* new */}
            <Route path="/map"       element={<MapPage />} />  
            <Route path="/species-summary" element={<SpeciesSummaryPage />} />
          </Route>

          {/* Admin‑only routes */}
          <Route element={<ProtectedRoute role="admin" />}>
            <Route path="/admin" element={<AdminPanel />} />
            <Route path="/admin/qc"     element={<DataQualityPage />} />
            <Route path="/logs" element={<LogsPage />} />   
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}