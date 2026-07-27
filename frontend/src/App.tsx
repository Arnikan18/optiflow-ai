import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Shell } from './components/layout/Shell';
import { ControlRoomPage } from './pages/ControlRoomPage';
import { RunCockpitPage } from './pages/RunCockpitPage';

export default function App() {
  return (
    <BrowserRouter>
      <Shell>
        <Routes>
          <Route path="/"           element={<ControlRoomPage />} />
          <Route path="/run/:runId" element={<RunCockpitPage />} />
          <Route path="*"           element={
            <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 text-center px-6">
              <p className="text-5xl">404</p>
              <p className="text-sm text-ink-muted">Page not found.</p>
              <a href="/" className="text-xs font-mono text-ops-amber hover:underline">← Control Room</a>
            </div>
          } />
        </Routes>
      </Shell>
    </BrowserRouter>
  );
}
