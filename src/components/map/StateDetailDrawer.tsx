import React from 'react';
import { X, ShieldAlert, Phone, MapPin, AlertTriangle, Users, Compass, ChevronRight, Activity } from 'lucide-react';
import { StateRiskData } from '../../types/location';
import { HazardService } from '../../services/hazardService';

interface StateDetailDrawerProps {
  state: StateRiskData | null;
  onClose: () => void;
  onSelectHazard?: (hazardId: string) => void;
  onNavigate: (tab: string) => void;
}

export const StateDetailDrawer: React.FC<StateDetailDrawerProps> = ({
  state,
  onClose,
  onSelectHazard,
  onNavigate,
}) => {
  if (!state) return null;

  // Find hazards related to this state from live HazardService
  const allHazards = HazardService.getAllHazards();
  const stateHazards = allHazards.filter(
    (h) =>
      h.location.state.toLowerCase().includes(state.name.toLowerCase()) ||
      state.name.toLowerCase().includes(h.location.state.toLowerCase())
  );

  return (
    <div className="fixed inset-y-0 right-0 z-40 max-w-full flex pl-10">
      <div className="w-screen max-w-md bg-white shadow-2xl border-l border-slate-200 flex flex-col animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-4 bg-slate-900 text-white flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700">
                {state.id}
              </span>
              <span
                className={`text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded ${
                  state.riskLevel === 'critical'
                    ? 'bg-red-600 text-white'
                    : state.riskLevel === 'warning'
                    ? 'bg-amber-600 text-white'
                    : 'bg-emerald-600 text-white'
                }`}
              >
                {state.riskLevel.toUpperCase()} RISK
              </span>
            </div>
            <h3 className="text-lg font-extrabold text-white">{state.name}</h3>
            <p className="text-xs text-slate-400 font-mono">
              Capital: {state.capital} • Population: {state.populationCrores} Cr
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Primary Threat Banner */}
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] font-mono uppercase font-bold text-slate-400 mb-1">
              Primary Threat Assessment
            </div>
            <div className="text-xs font-semibold text-slate-900 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
              <span>{state.primaryThreat}</span>
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Current Conditions: {state.currentTemp}°C, {state.condition}
            </div>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-3 gap-2 text-center font-mono">
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-[10px] text-slate-400">RISK INDEX</div>
              <div className="text-base font-extrabold text-slate-900">{state.riskScore}/100</div>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-[10px] text-slate-400">ACTIVE HAZARDS</div>
              <div className="text-base font-extrabold text-red-600">{state.activeHazardsCount}</div>
            </div>
            <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-[10px] text-slate-400">SOS BEACONS</div>
              <div className="text-base font-extrabold text-amber-600">{state.activeSOSCount}</div>
            </div>
          </div>

          {/* Key Vulnerable Districts */}
          <div>
            <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider font-mono mb-2 flex items-center justify-between">
              <span>Monitored District Zones</span>
              <span className="text-[10px] text-slate-400">({state.keyDistricts.length} Listed)</span>
            </h4>
            <div className="space-y-1.5">
              {state.keyDistricts.map((dst, idx) => (
                <div
                  key={idx}
                  className="p-2 rounded-lg bg-white border border-slate-200 flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-semibold text-slate-800">{dst.name}</span>
                    {dst.hazardType && (
                      <span className="text-[10px] text-slate-500 block">
                        Threat: {dst.hazardType}
                      </span>
                    )}
                  </div>
                  <span
                    className={`text-[9px] font-mono px-2 py-0.5 rounded font-bold uppercase ${
                      dst.risk === 'critical'
                        ? 'bg-red-100 text-red-700'
                        : dst.risk === 'warning'
                        ? 'bg-amber-100 text-amber-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}
                  >
                    {dst.risk}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Active Hazards in this State */}
          {stateHazards.length > 0 && (
            <div>
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider font-mono mb-2">
                Active Bulletins in {state.name}
              </h4>
              <div className="space-y-2">
                {stateHazards.map((hz) => (
                  <div
                    key={hz.id}
                    onClick={() => {
                      if (onSelectHazard) onSelectHazard(hz.id);
                      onNavigate('hazards');
                    }}
                    className="p-3 rounded-xl bg-slate-50 hover:bg-red-50/50 border border-slate-200 hover:border-red-200 cursor-pointer transition-colors"
                  >
                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 mb-1">
                      <span>{hz.categoryName}</span>
                      <span className="font-bold text-red-600 uppercase">{hz.severity}</span>
                    </div>
                    <div className="text-xs font-bold text-slate-900">{hz.title}</div>
                    <div className="text-[11px] text-slate-600 line-clamp-2 mt-1">
                      {hz.headline}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SDMA Emergency Helplines */}
          <div className="p-3.5 rounded-xl bg-slate-900 text-white">
            <div className="flex items-center gap-2 text-xs font-bold text-red-400 uppercase font-mono mb-2">
              <Phone className="w-4 h-4" />
              <span>State Disaster Operations Desk</span>
            </div>
            <div className="text-xs font-mono text-slate-300 mb-1">
              SDMA Hotline: <strong className="text-white">{state.sdmaHelpline}</strong>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">
              National Emergency: 112 | Fire: 101 | Medical: 108
            </div>
          </div>
        </div>

        {/* Drawer Footer Actions */}
        <div className="p-3 bg-slate-50 border-t border-slate-200 flex items-center gap-2">
          <button
            onClick={() => {
              onClose();
              onNavigate('forecasts');
            }}
            className="flex-1 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold py-2 rounded-lg transition-colors flex items-center justify-center gap-1"
          >
            <span>Predictive Forecast</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
