import React, { useState } from 'react';
import {
  Shield,
  MapPin,
  Search,
  Bell,
  Radio,
  ChevronDown,
  Activity,
  AlertTriangle,
  Flame,
  CloudRain,
  Compass,
  PhoneCall,
  Menu,
  X,
  User,
  CheckCircle2,
} from 'lucide-react';
import { useLocation } from '../../context/LocationContext';
import { useNotifications } from '../../context/NotificationContext';
import { useSOS } from '../../context/SOSContext';
import { useProfile } from '../../context/ProfileContext';
import { WeatherService } from '../../services/weatherService';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onOpenSearch: () => void;
  onOpenProfile: () => void;
  onSelectHazard?: (hazardId: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  onOpenSearch,
  onOpenProfile,
}) => {
  const { selectedCityKey, weather, setSelectedCity, selectedState, isGpsActive, detectCurrentLocation } = useLocation();
  const { unreadCount, setIsDrawerOpen } = useNotifications();
  const { beacons } = useSOS();
  const { profile } = useProfile();
  const [isCityDropdownOpen, setIsCityDropdownOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const availableCities = WeatherService.getAvailableCities();
  const activeSOSCount = beacons.filter((b) => b.triageStatus !== 'resolved' && b.triageStatus !== 'cancelled').length;

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Compass },
    { id: 'live-map', label: 'Live Map', icon: Radio, badge: 'GIS' },
    { id: 'forecasts', label: 'Forecasts', icon: CloudRain },
    { id: 'hazards', label: 'Hazards & Intel', icon: AlertTriangle, badge: '08' },
    { id: 'sos', label: 'SOS Hub', icon: PhoneCall, badge: `${activeSOSCount}`, badgeColor: 'bg-red-600 text-white' },
    { id: 'activity', label: 'Activity Stream', icon: Activity },
  ];

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200/90 shadow-subtle">
      {/* Primary Brand & Actions Bar */}
      <div className="max-w-[1720px] mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 gap-4">
          {/* Logo and Tagline */}
          <div className="flex items-center gap-3 shrink-0">
            <div
              onClick={() => setActiveTab('dashboard')}
              className="cursor-pointer flex items-center gap-2.5 group"
            >
              <div className="w-10 h-10 rounded-xl bg-slate-900 flex items-center justify-center text-white shadow-md shadow-slate-900/20 group-hover:bg-red-600 transition-colors">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-extrabold tracking-tight text-lg text-slate-900 font-sans">
                    AEGIS<span className="text-red-600 ml-1">ALERT</span>
                  </span>
                  <span className="text-[10px] font-mono font-semibold bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200">
                    V2.4 INTEL
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 font-medium hidden sm:block">
                  Know the Risk. Stay Prepared.
                </p>
              </div>
            </div>
          </div>

          {/* Center: Desktop Navigation Tabs */}
          <nav className="hidden xl:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`relative flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-sky-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-mono font-bold px-1.5 py-0.2 rounded ${
                        item.badgeColor
                          ? item.badgeColor
                          : isActive
                          ? 'bg-slate-800 text-sky-300'
                          : 'bg-slate-200/80 text-slate-700'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Right Section: Location Selector, Search, Notifications, Profile Button */}
          <div className="flex items-center gap-2.5">
            {/* Quick Location Switcher Dropdown */}
            <div className="relative">
              <button
                onClick={() => setIsCityDropdownOpen(!isCityDropdownOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200/80 border border-slate-200 text-xs font-medium text-slate-800 transition-colors"
                title="Switch Monitored Location"
              >
                <MapPin className="w-3.5 h-3.5 text-red-600 shrink-0" />
                <div className="text-left hidden md:block">
                  <div className="font-semibold text-[11px] leading-tight text-slate-900">
                    {weather.cityName}, {selectedState?.id || 'IN'}
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono leading-none">
                    {weather.temp}°C • {weather.conditionCode}
                  </div>
                </div>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {/* City Dropdown Menu */}
              {isCityDropdownOpen && (
                <div className="absolute right-0 mt-2 w-72 bg-white rounded-xl shadow-elevated border border-slate-200 py-2 z-50 animate-in fade-in slide-in-from-top-2">
                  <div className="p-2 border-b border-slate-100">
                    <button
                      onClick={() => {
                        detectCurrentLocation();
                        setIsCityDropdownOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                        isGpsActive
                          ? 'bg-sky-100 text-sky-900 border border-sky-300'
                          : 'bg-slate-900 text-white hover:bg-sky-600'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
                        <span>{isGpsActive ? '📍 Real GPS Active' : '📍 Use My Real GPS Location'}</span>
                      </div>
                      <span className="text-[10px] font-mono uppercase bg-white/20 px-1.5 py-0.5 rounded">
                        India
                      </span>
                    </button>
                  </div>

                  <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">
                    Or Select Indian Urban Station
                  </div>
                  <div className="max-h-60 overflow-y-auto divide-y divide-slate-100">
                    {availableCities.map((city) => (
                      <button
                        key={city.key}
                        onClick={() => {
                          setSelectedCity(city.key);
                          setIsCityDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 transition-colors ${
                          !isGpsActive && selectedCityKey === city.key ? 'bg-sky-50 font-bold text-sky-900' : 'text-slate-700'
                        }`}
                      >
                        <div>
                          <div className="font-medium text-slate-900">{city.name}</div>
                          <div className="text-[10px] text-slate-500">{city.state}</div>
                        </div>
                        <span className="font-mono text-xs text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                          {city.temp}°C
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Global Search Shortcut Button */}
            <button
              onClick={onOpenSearch}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200/80 border border-slate-200 text-xs text-slate-500 hover:text-slate-800 transition-colors"
              title="Search Hazards, Cities, SOS (Ctrl+K)"
            >
              <Search className="w-3.5 h-3.5 text-slate-500" />
              <span className="hidden lg:inline text-[11px]">Search...</span>
              <kbd className="hidden lg:inline font-mono text-[10px] bg-white text-slate-500 px-1.5 py-0.5 rounded border border-slate-200 shadow-xs">
                ⌘K
              </kbd>
            </button>

            {/* Notification Drawer Trigger */}
            <button
              onClick={() => setIsDrawerOpen(true)}
              className="relative p-2 rounded-lg bg-slate-100 hover:bg-slate-200/80 border border-slate-200 text-slate-700 hover:text-slate-900 transition-colors"
              title="Emergency Notifications"
            >
              <Bell className="w-4 h-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-600 text-white text-[9px] font-bold font-mono flex items-center justify-center animate-pulse">
                  {unreadCount}
                </span>
              )}
            </button>

            {/* Citizen Profile / Settings Button (Matching Mobile App on 8081) */}
            <button
              onClick={onOpenProfile}
              className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-800 text-xs font-semibold shadow-xs transition-all active:scale-95 group"
              title="Open AEGIS Settings & Emergency Profile"
            >
              <div className="w-6 h-6 rounded-full bg-[#075B8A] flex items-center justify-center text-white text-[11px] font-black shadow-xs">
                {profile.fullName?.trim() ? profile.fullName.trim()[0].toUpperCase() : 'A'}
              </div>
              <div className="text-left hidden sm:block">
                <div className="text-[11px] font-extrabold text-slate-900 leading-tight flex items-center gap-1">
                  <span>{profile.fullName || 'Aarav Sharma'}</span>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
                </div>
                <div className="text-[9px] text-slate-500 font-medium leading-none mt-0.5">
                  Settings & Safety
                </div>
              </div>
            </button>

            {/* Mobile Menu Toggle */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="xl:hidden p-2 rounded-lg bg-slate-100 border border-slate-200 text-slate-700"
            >
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Responsive Nav Drawer */}
      {isMobileMenuOpen && (
        <div className="xl:hidden bg-white border-b border-slate-200 px-4 py-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setIsMobileMenuOpen(false);
                }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-semibold ${
                  isActive ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-200 text-slate-800">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
          <div className="pt-2 border-t border-slate-100">
            <button
              onClick={() => {
                onOpenProfile();
                setIsMobileMenuOpen(false);
              }}
              className="w-full bg-slate-900 text-white py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2"
            >
              <User className="w-4 h-4 text-sky-400" />
              <span>My Citizen Safety Account</span>
            </button>
          </div>
        </div>
      )}
    </header>
  );
};
