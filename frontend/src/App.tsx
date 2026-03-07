import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Portal from './pages/Portal';
import DashboardLayout from './pages/DashboardLayout';
import Ranking from './pages/Ranking';
import Analysis from './pages/Analysis';
import { useState } from 'react';

// Global State shape
export interface AppState {
  spatialData: any | null;       // The raw GeoJSON from the backend
  globalMetadata: any | null;    // Center lat/lon, area, etc.
  /**
   * moduleCache: almacena resultados de APIs ya calculados para evitar
   * re-fetches al navegar entre módulos.
   */
  moduleCache: {
    rankingData?: any[];                        // Resultados del ranking IDECOR
    benchmarkData?: Record<string, any[]>;      // key = startDate|endDate|index
    analysisTimeSeries?: Record<string, any[]>; // key = lotId|startDate|endDate, value = data
    weatherData?: Record<string, any>;          // key = lotId, value = weatherData
  };
}

function App() {
  const [appState, setAppState] = useState<AppState>({
    spatialData: null,
    globalMetadata: null,
    moduleCache: {},
  });

  return (
    <Router>
      <Routes>
        <Route path="/" element={<Portal setAppState={setAppState} />} />

        {/* Protected Dashboard Routes */}
        <Route path="/dashboard" element={<DashboardLayout appState={appState} setAppState={setAppState} />}>
          <Route index element={<Navigate to="ranking" replace />} />
          <Route path="ranking" element={<Ranking appState={appState} setAppState={setAppState} />} />
          <Route path="analysis" element={<Analysis appState={appState} setAppState={setAppState} />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
