import { BrowserRouter, Link, Navigate, Route, Routes } from 'react-router-dom';
import { Shell } from './components/layout/Shell';
import { ControlRoomPage } from './pages/ControlRoomPage';
import { RunCockpitPage } from './pages/RunCockpitPage';
import { LiveDemoPage } from './pages/LiveDemoPage';
import {
  DemoLabPage,
} from './pages/WorkspacePages';
import { DecisionsPage } from './pages/DecisionsPage';
import { SimpleSettingsPage } from './pages/SimpleSettingsPage';
import { EnterpriseSimulationProvider } from './hooks/useEnterpriseSimulation';

export default function App() {
  return (
    <BrowserRouter>
      <EnterpriseSimulationProvider>
        <Shell>
        <Routes>
          <Route path="/" element={<ControlRoomPage />} />
          <Route path="/decision-flow" element={<Navigate to="/" replace />} />
          <Route path="/run/:runId" element={<RunCockpitPage />} />
          <Route path="/history" element={<DecisionsPage />} />
          <Route path="/demo-lab" element={<DemoLabPage />} />
          <Route path="/judge" element={<LiveDemoPage />} />
          <Route path="/live-demo" element={<Navigate to="/judge" replace />} />
          <Route path="/settings" element={<SimpleSettingsPage />} />
          <Route
            path="*"
            element={(
              <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 text-center px-6">
                <p className="text-5xl">404</p>
                <p className="text-sm text-ink-muted">Page not found.</p>
                <Link to="/" className="text-xs font-mono text-ops-amber hover:underline">
                  ← Return to Today
                </Link>
              </div>
            )}
          />
        </Routes>
        </Shell>
      </EnterpriseSimulationProvider>
    </BrowserRouter>
  );
}
