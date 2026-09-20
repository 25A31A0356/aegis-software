import React, { useState, useEffect, useRef } from 'react';
import { Search, X, AlertTriangle, MapPin, PhoneCall, Building, ChevronRight, ShieldAlert } from 'lucide-react';
import { HazardService } from '../../services/hazardService';
import { LocationService, LocationSearchResult, INDIAN_CITIES_REGISTRY } from '../../services/locationService';
import { SOSService } from '../../services/sosService';
import { ApiClient } from '../../services/apiClient';
import { useLocation } from '../../context/LocationContext';
import { HazardItem } from '../../types/hazard';
import { SOSBeacon } from '../../types/sos';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: string) => void;
  onSelectHazard?: (hazardId: string) => void;
  onSelectSOS?: (sosId: string) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onSelectHazard,
  onSelectSOS,
}) => {
  const [query, setQuery] = useState('');
  const [shelters, setShelters] = useState<any[]>([]);
  const { selectLocationItem } = useLocation();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      // Fetch live shelters from backend
      ApiClient.get<any[]>('/shelters', { limit: 10 }).then((res) => {
        if (res && Array.isArray(res)) setShelters(res);
      }).catch(console.warn);
    } else {
      setQuery('');
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onClose();
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const q = query.trim().toLowerCase();
  const allHazards: HazardItem[] = HazardService.getAllHazards();
  const allBeacons: SOSBeacon[] = SOSService.getBeacons();

  // Filter Hazards
  const matchingHazards = q
    ? allHazards
        .filter(
          (h) =>
            h.title.toLowerCase().includes(q) ||
            h.categoryName.toLowerCase().includes(q) ||
            h.location.state.toLowerCase().includes(q) ||
            h.location.district.toLowerCase().includes(q)
        )
        .slice(0, 4)
    : allHazards.slice(0, 3);

  // Filter States & Cities from Registry
  const matchingLocations: LocationSearchResult[] = q
    ? INDIAN_CITIES_REGISTRY.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.stateName.toLowerCase().includes(q) ||
          s.district.toLowerCase().includes(q) ||
          s.stateId.toLowerCase() === q
      ).slice(0, 4)
    : INDIAN_CITIES_REGISTRY.slice(0, 4);

  // Filter SOS Beacons
  const matchingSOS = q
    ? allBeacons
        .filter(
          (b) =>
            b.id.toLowerCase().includes(q) ||
            b.emergencyTitle.toLowerCase().includes(q) ||
            b.district.toLowerCase().includes(q) ||
            b.state.toLowerCase().includes(q)
        )
        .slice(0, 3)
    : allBeacons.slice(0, 2);

  // Filter Shelters
  const matchingShelters = q
    ? shelters
        .filter(
          (sh) =>
            (sh.name || '').toLowerCase().includes(q) ||
            (sh.state || '').toLowerCase().includes(q) ||
            (sh.district || '').toLowerCase().includes(q)
        )
        .slice(0, 3)
    : shelters.slice(0, 3);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-[#075B8A]/60 backdrop-blur-xs animate-in fade-in">
      <div
        className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-[24px] shadow-float border border-[#DCEBED] dark:border-slate-800 overflow-hidden flex flex-col max-h-[80vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-5 py-4 border-b border-[#DCEBED] dark:border-slate-800 bg-[#F4F8FA] dark:bg-slate-800/60">
          <Search className="w-5 h-5 text-[#075B8A] dark:text-sky-400 mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search hazards, Indian cities, states, SOS IDs, or shelters..."
            className="w-full bg-transparent text-xs sm:text-sm text-[#18364A] dark:text-white placeholder:text-[#708696] dark:placeholder:text-slate-400 focus:outline-none font-sans"
          />
          {query && (
            <button onClick={() => setQuery('')} className="p-1 text-[#708696] dark:text-slate-400 hover:text-[#18364A] dark:hover:text-white">
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={onClose}
            className="ml-2 text-[10px] font-mono bg-white dark:bg-slate-700 hover:bg-[#EEF5F8] dark:hover:bg-slate-600 text-[#708696] dark:text-slate-200 px-2 py-1 rounded-lg border border-[#DCEBED] dark:border-slate-600"
          >
            ESC
          </button>
        </div>

        {/* Results List */}
        <div className="overflow-y-auto p-4 space-y-5 divide-y divide-[#DCEBED]/60 dark:divide-slate-800">
          {/* Hazards Section */}
          {matchingHazards.length > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#708696] dark:text-slate-400 font-mono mb-2 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-[#F4C84A]" />
                <span>Active Hazards & Advisories ({matchingHazards.length})</span>
              </div>
              <div className="space-y-1.5">
                {matchingHazards.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => {
                      onClose();
                      if (onSelectHazard) onSelectHazard(item.id);
                      onNavigate('hazards');
                    }}
                    className="p-3 rounded-2xl hover:bg-[#F4F8FA] dark:hover:bg-slate-800 border border-transparent hover:border-[#18C3D0] cursor-pointer flex items-center justify-between group transition-all"
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${
                          item.severity === 'critical'
                            ? 'bg-[#E94B68] animate-pulse'
                            : item.severity === 'warning'
                            ? 'bg-[#F4C84A]'
                            : 'bg-[#18C3D0]'
                        }`}
                      />
                      <div>
                        <div className="text-xs font-bold text-[#18364A] dark:text-white group-hover:text-[#075B8A] dark:group-hover:text-sky-400 transition-colors">
                          {item.title}
                        </div>
                        <div className="text-[10.5px] text-[#708696] dark:text-slate-400 flex items-center gap-2 mt-0.5 font-mono">
                          <span>{item.location.state} • {item.location.district}</span>
                          <span>•</span>
                          <span className="bg-[#EDFAFC] dark:bg-sky-950/60 text-[#075B8A] dark:text-sky-300 px-1.5 py-0.5 rounded text-[9px] font-bold">
                            {item.categoryName}
                          </span>
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[#708696] dark:text-slate-400 group-hover:text-[#075B8A] dark:group-hover:text-sky-400 transition-transform group-hover:translate-x-1" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* States & Urban Centers Section */}
          {matchingLocations.length > 0 && (
            <div className="pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#708696] dark:text-slate-400 font-mono mb-2 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-[#075B8A] dark:text-sky-400" />
                <span>Cities & Monitored Regions ({matchingLocations.length})</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {matchingLocations.map((st) => (
                  <div
                    key={st.id}
                    onClick={() => {
                      selectLocationItem(st);
                      onClose();
                      onNavigate('homepage');
                    }}
                    className="p-3 rounded-2xl hover:bg-[#F4F8FA] dark:hover:bg-slate-800 border border-[#DCEBED] dark:border-slate-800 hover:border-[#18C3D0] cursor-pointer flex items-center justify-between group transition-colors"
                  >
                    <div>
                      <div className="text-xs font-bold text-[#18364A] dark:text-white group-hover:text-[#075B8A] dark:group-hover:text-sky-400">
                        {st.name} ({st.stateId})
                      </div>
                      <div className="text-[10px] text-[#708696] dark:text-slate-400 font-mono">
                        {st.district}, {st.stateName}
                      </div>
                    </div>
                    <span
                      className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-bold uppercase border ${
                        st.riskLevel === 'Critical'
                          ? 'bg-[#FEF1F3] text-[#E94B68] border-[#FDC8D1]'
                          : st.riskLevel === 'High' || st.riskLevel === 'Medium'
                          ? 'bg-[#FFFBF0] text-[#B78809] border-[#FDE8A4]'
                          : 'bg-[#EFFCF6] text-[#1E8A63] border-[#B7F1DC]'
                      }`}
                    >
                      {st.riskLevel}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* SOS Distress Beacons */}
          {matchingSOS.length > 0 && (
            <div className="pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#708696] dark:text-slate-400 font-mono mb-2 flex items-center gap-1.5">
                <PhoneCall className="w-3.5 h-3.5 text-[#E94B68]" />
                <span>Emergency SOS Beacons ({matchingSOS.length})</span>
              </div>
              <div className="space-y-1.5">
                {matchingSOS.map((sos) => (
                  <div
                    key={sos.id}
                    onClick={() => {
                      if (onSelectSOS) onSelectSOS(sos.id);
                      onClose();
                      onNavigate('sos');
                    }}
                    className="p-3 rounded-2xl hover:bg-[#FEF1F3]/40 dark:hover:bg-red-950/20 border border-[#DCEBED] dark:border-slate-800 hover:border-[#E94B68] cursor-pointer flex items-center justify-between group transition-colors"
                  >
                    <div>
                      <div className="text-xs font-bold text-[#18364A] dark:text-white flex items-center gap-2">
                        <span className="font-mono text-[#E94B68] bg-[#FEF1F3] border border-[#FDC8D1] px-1.5 py-0.5 rounded text-[9px] font-bold">
                          {sos.id}
                        </span>
                        <span>{sos.emergencyTitle}</span>
                      </div>
                      <div className="text-[10.5px] text-[#708696] dark:text-slate-400 mt-0.5 font-mono">
                        {sos.locationName} • Triage: {sos.triageStatus.toUpperCase()}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-[#708696] dark:text-slate-400 group-hover:text-[#E94B68]" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Shelters */}
          {matchingShelters.length > 0 && (
            <div className="pt-4">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[#708696] dark:text-slate-400 font-mono mb-2 flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-[#075B8A] dark:text-sky-400" />
                <span>Evacuation Shelters & Relief Camps</span>
              </div>
              <div className="space-y-1.5">
                {matchingShelters.map((sh) => (
                  <div
                    key={sh.id}
                    onClick={() => {
                      onClose();
                      onNavigate('live-map');
                    }}
                    className="p-3 rounded-2xl hover:bg-[#F4F8FA] dark:hover:bg-slate-800 border border-[#DCEBED] dark:border-slate-800 cursor-pointer flex items-center justify-between"
                  >
                    <div>
                      <div className="text-xs font-bold text-[#18364A] dark:text-white">{sh.name}</div>
                      <div className="text-[10px] text-[#708696] dark:text-slate-400 font-mono">
                        {sh.district || sh.location_name}, {sh.state} • Cap: {sh.capacity || sh.capacityPersons || 500}
                      </div>
                    </div>
                    <span className="text-[9px] font-mono bg-[#EDFAFC] dark:bg-sky-950/60 text-[#075B8A] dark:text-sky-300 border border-[#AEEBF0] dark:border-sky-800 px-2 py-0.5 rounded-full font-bold">
                      {sh.type || 'SHELTER'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 bg-[#F4F8FA] dark:bg-slate-800/80 border-t border-[#DCEBED] dark:border-slate-800 text-[10px] text-[#708696] dark:text-slate-400 flex items-center justify-between font-mono">
          <span>Navigate with ↵ or click item</span>
          <span>Unified Spatial Search • Real AEGIS Grid</span>
        </div>
      </div>
    </div>
  );
};
