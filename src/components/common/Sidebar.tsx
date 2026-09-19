import React from 'react';
import {
  Shield,
  Home,
  BarChart3,
  ShieldCheck,
  FileText,
  MapPin,
  Radio,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Database,
} from 'lucide-react';
import { AGIES_TOKENS } from '../../theme/tokens';
import { useDataProvider } from '../../context/DataProviderContext';

export interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isMobileDrawer?: boolean;
  onCloseMobileDrawer?: () => void;
}

export const navItems: NavItem[] = [
  { id: 'homepage', label: 'Homepage', icon: Home },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, badge: 'LIVE' },
  { id: 'safety', label: 'Safety', icon: ShieldCheck },
  { id: 'reports', label: 'Reports', icon: FileText },
  { id: 'live-map', label: 'Live Map', icon: Radio, badge: 'GIS' },
  { id: 'datacore', label: 'Data Core', icon: Database, badge: 'v1' },
];

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  isCollapsed = false,
  onToggleCollapse,
  isMobileDrawer = false,
  onCloseMobileDrawer,
}) => {
  const handleItemClick = (id: string) => {
    setActiveTab(id);
    if (isMobileDrawer && onCloseMobileDrawer) {
      onCloseMobileDrawer();
    }
  };

  const { dataMode, isLiveMode, openInspector } = useDataProvider();

  return (
    <aside
      className={`relative flex flex-col justify-between h-full bg-[#075B8A] text-white select-none transition-all duration-300 ease-in-out z-30 shadow-xl ${
        isCollapsed ? 'w-18' : 'w-[216px]'
      }`}
    >
      {/* Top Header & Logo */}
      <div>
        <div className="flex items-center justify-between px-4 py-5 border-b border-white/10">
          <div
            onClick={() => handleItemClick('homepage')}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <div className="w-9 h-9 rounded-xl bg-white/10 border border-white/20 flex items-center justify-center shrink-0 group-hover:bg-[#18C3D0] transition-colors">
              <Shield className="w-5 h-5 text-white group-hover:text-[#075B8A] transition-colors" />
            </div>
            {!isCollapsed && (
              <div className="overflow-hidden">
                <h1 className="font-extrabold text-sm tracking-wider uppercase font-sans text-white leading-tight">
                  AGIES <span className="text-[#18C3D0]">ALERT</span>
                </h1>
                <p className="text-[9px] tracking-wider text-[#A7D7E8] font-semibold uppercase leading-tight mt-0.5 truncate">
                  MULTI-HAZARD EARLY WARNING
                </p>
              </div>
            )}
          </div>

          {/* Desktop Collapse Toggle */}
          {!isMobileDrawer && onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="p-1 rounded-md text-white/60 hover:text-white hover:bg-white/10 transition-colors hidden lg:block"
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="p-3 space-y-1.5 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            // Map either exact match or alias (e.g. dashboard -> homepage)
            const isActive =
              activeTab === item.id ||
              (item.id === 'homepage' && activeTab === 'dashboard') ||
              (item.id === 'analytics' && activeTab === 'forecasts') ||
              (item.id === 'safety' && (activeTab === 'sos' || activeTab === 'hazards')) ||
              (item.id === 'reports' && activeTab === 'activity');

            return (
              <button
                key={item.id}
                onClick={() => handleItemClick(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-full text-xs font-semibold tracking-wide transition-all duration-150 cursor-pointer ${
                  isActive
                    ? 'bg-[#18C3D0] text-[#075B8A] shadow-md shadow-[#18C3D0]/20 font-bold scale-[1.02]'
                    : 'text-[#D3E8F4] hover:text-white hover:bg-white/10'
                } ${isCollapsed ? 'justify-center px-2' : ''}`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#075B8A]' : 'text-[#A7D7E8]'}`} />
                {!isCollapsed && (
                  <span className="truncate flex-1 text-left">{item.label}</span>
                )}
                {!isCollapsed && item.badge && (
                  <span
                    className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-full uppercase ${
                      isActive
                        ? 'bg-[#075B8A] text-[#18C3D0]'
                        : 'bg-white/15 text-[#D3E8F4]'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Bottom: Data Provider Stream Status Card */}
      <div className="p-3">
        {!isCollapsed ? (
          <button
            onClick={openInspector}
            className="w-full rounded-2xl bg-white/10 hover:bg-white/15 border border-white/15 p-3 text-left transition-all cursor-pointer group"
            title="Click to inspect 7 Data Provider streams"
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  {isLiveMode ? (
                    <>
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#45C79A] opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#45C79A]"></span>
                    </>
                  ) : (
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-400"></span>
                  )}
                </span>
                <span className="text-[10px] font-mono uppercase font-bold text-[#A7D7E8] tracking-wider">
                  {dataMode} STREAM
                </span>
              </div>
              <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-white/10 group-hover:bg-white/20 text-white/80">
                Inspect
              </span>
            </div>
            <div className="text-[11px] font-bold text-white leading-tight">
              {isLiveMode ? 'SYSTEMS OPERATIONAL' : 'SIMULATION MODE'}
            </div>
            <p className="text-[9px] text-[#A7D7E8] mt-0.5 leading-snug">
              {isLiveMode ? 'IMD, CWC & Satellite live telemetry nominal.' : 'Structured NDMA disaster drill dataset.'}
            </p>
          </button>
        ) : (
          <button
            onClick={openInspector}
            className="w-full flex flex-col items-center justify-center p-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-[#45C79A] cursor-pointer transition-colors"
            title={`Data Stream: ${dataMode} (Click to inspect)`}
          >
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isLiveMode ? 'bg-[#45C79A] animate-pulse' : 'bg-amber-400'
              }`}
            />
          </button>
        )}
      </div>
    </aside>
  );
};
