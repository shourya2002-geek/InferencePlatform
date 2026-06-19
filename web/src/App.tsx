import { Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import { TopControlBar } from "./components/layout/TopControlBar";
import Overview from "./pages/Overview";
import Architecture from "./pages/Architecture";
import TrafficSimulator from "./pages/TrafficSimulator";
import DynamicBatching from "./pages/DynamicBatching";
import WorkerPool from "./pages/WorkerPool";
import RuntimeLab from "./pages/RuntimeLab";
import RuntimeComparison from "./pages/RuntimeComparison";
import OptimizationJourney from "./pages/OptimizationJourney";
import FailureInjection from "./pages/FailureInjection";
import ModelRegistry from "./pages/ModelRegistry";
import Observability from "./pages/Observability";
import ReplayCenter from "./pages/ReplayCenter";

export default function App() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-ink-900">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopControlBar />
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/traffic" element={<TrafficSimulator />} />
            <Route path="/batching" element={<DynamicBatching />} />
            <Route path="/workers" element={<WorkerPool />} />
            <Route path="/runtime-lab" element={<RuntimeLab />} />
            <Route path="/runtime-comparison" element={<RuntimeComparison />} />
            <Route path="/optimization" element={<OptimizationJourney />} />
            <Route path="/failures" element={<FailureInjection />} />
            <Route path="/registry" element={<ModelRegistry />} />
            <Route path="/observability" element={<Observability />} />
            <Route path="/replays" element={<ReplayCenter />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
