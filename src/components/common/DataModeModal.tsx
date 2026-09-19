/**
 * AEGIS ALERT - Data Provider Inspector & Mode Switcher Modal
 * Displays real-time health, latency, authoritative sources, and controls for the 7 provider interfaces.
 */

import React from 'react';
import { useDataProvider } from '../../context/DataProviderContext';
import {
  X,
  Radio,
  CloudRain,
  AlertTriangle,
  MapPin,
  Map,
  Activity,
  Satellite,
  Zap,
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  Server,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';

export const DataModeModal: React.FC = () => {
  const { isInspectorOpen, closeInspector, dataMode, isLiveMode, setDataMode, providersHealth } =
    useDataProvider();

  if (!isInspectorOpen) return null;

  const getServiceIcon = (type: string) => {
    switch (type) {
      case 'weather':
        return <CloudRain className="w-5 h-5 text-sky-400" />;
      case 'alerts':
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      case 'geocoding':
        return <MapPin className="w-5 h-5 text-emerald-400" />;
      case 'maps':
        return <Map className="w-5 h-5 text-cyan-400" />;
      case 'radar':
        return <Activity className="w-5 h-5 text-indigo-400" />;
      case 'satellite':
        return <Satellite className="w-5 h-5 text-purple-400" />;
      case 'lightning':
        return <Zap className="w-5 h-5 text-yellow-400" />;
      default:
        return <Server className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn">
      <div className="bg-[#052338] border border-cyan-500/30 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-5 bg-[#072f4a] border-b border-cyan-500/20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-wide flex items-center gap-2">
                AEGIS Data-Provider Architecture
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase ${
                    isLiveMode
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                  }`}
                >
                  {dataMode} MODE
                </span>
              </h2>
              <p className="text-xs text-cyan-200/70">
                Authoritative Multi-Hazard Telemetry & Remote Sensing Provider Grid
              </p>
            </div>
          </div>
          <button
            onClick={closeInspector}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Switcher Banner */}
        <div className="px-6 py-4 bg-[#0a3959]/50 border-b border-cyan-500/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-white">Active Data Stream Setting</h3>
            <p className="text-xs text-slate-300 mt-0.5">
              {isLiveMode
                ? '🟢 LIVE MODE is active. Telemetry connects to real-world Indian meteorological, satellite & CAP alert networks.'
                : '⚠️ DEMO MODE is active. Uses structured simulation data for disaster drills and UI preview. Never silently presented as live.'}
            </p>
          </div>

          <div className="flex items-center gap-2 bg-[#051c2c] p-1 rounded-xl border border-cyan-500/20 self-start sm:self-auto">
            <button
              onClick={() => setDataMode('DEMO')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                !isLiveMode
                  ? 'bg-amber-500 text-slate-950 shadow-md font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              DEMO (Simulation)
            </button>
            <button
              onClick={() => setDataMode('LIVE')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                isLiveMode
                  ? 'bg-emerald-500 text-slate-950 shadow-md font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              LIVE (External APIs)
            </button>
          </div>
        </div>

        {/* Disclaimer Box */}
        <div className="px-6 py-3 bg-[#07243a]">
          <div
            className={`p-3 rounded-xl border flex items-start gap-3 text-xs ${
              isLiveMode
                ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-200'
                : 'bg-amber-950/30 border-amber-500/30 text-amber-200'
            }`}
          >
            {isLiveMode ? (
              <ShieldCheck className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            )}
            <div>
              <span className="font-bold">
                {isLiveMode ? 'Authoritative Verification:' : 'Safety & Compliance Notice:'}
              </span>{' '}
              {isLiveMode
                ? 'All emergency alerts and weather observations are routed from certified external providers (IMD, CWC, NDMA CAP gateway, MOSDAC, Open-Meteo). Fallbacks gracefully transition to baseline with explicit notice.'
                : 'AEGIS Alert strictly separates simulated disaster drill datasets from real-world emergency broadcasts. All displayed parameters are for system training and interface verification.'}
            </div>
          </div>
        </div>

        {/* Providers Health List */}
        <div className="px-6 py-4 overflow-y-auto space-y-3 flex-1">
          <div className="flex items-center justify-between text-xs text-cyan-300/70 font-semibold uppercase tracking-wider mb-1">
            <span>Configured Provider Interfaces (7 Channels)</span>
            <span>Real-time Status</span>
          </div>

          {providersHealth.map((provider) => (
            <div
              key={provider.providerId}
              className="p-3.5 rounded-xl bg-[#072840] border border-cyan-500/20 hover:border-cyan-400/40 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-[#051c2c] border border-cyan-500/20 shrink-0">
                  {getServiceIcon(provider.serviceType)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-white">{provider.name}</h4>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                      {provider.serviceType}
                    </span>
                  </div>
                  <p className="text-xs text-cyan-100/70 mt-0.5">{provider.description}</p>
                  <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
                    <span className="text-cyan-400 font-medium">Source:</span> {provider.authoritySource}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 sm:flex-col sm:items-end shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-white/5">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      provider.status === 'ONLINE'
                        ? 'bg-emerald-400 animate-pulse'
                        : 'bg-amber-400'
                    }`}
                  />
                  <span
                    className={`text-xs font-bold ${
                      provider.status === 'ONLINE' ? 'text-emerald-300' : 'text-amber-300'
                    }`}
                  >
                    {provider.status}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" /> {provider.latencyMs}ms
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-[#072f4a] border-t border-cyan-500/20 flex items-center justify-between">
          <div className="text-xs text-slate-300">
            Environment Mode Config: <code className="text-cyan-300 font-mono">DATA_MODE={dataMode.toLowerCase()}</code>
          </div>
          <button
            onClick={closeInspector}
            className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-colors shadow-lg"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
