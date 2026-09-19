import React, { useState, useEffect } from 'react';
import {
  Bell,
  Globe,
  User,
  Menu,
  Shield,
  Search,
  Check,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { useNotifications } from '../../context/NotificationContext';
import { useProfile } from '../../context/ProfileContext';
import { AEGIS_TOKENS } from '../../theme/tokens';
import { DataStatusIndicator } from './DataStatusIndicator';

interface HeaderProps {
  onOpenNotifications?: () => void;
  onOpenProfile?: () => void;
  onOpenSearch?: () => void;
  onToggleMobileSidebar?: () => void;
}

const LANGUAGES = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'gu', label: 'Gujarati', native: 'ગુજરાતી' },
];

export const Header: React.FC<HeaderProps> = ({
  onOpenNotifications,
  onOpenProfile,
  onOpenSearch,
  onToggleMobileSidebar,
}) => {
  const { unreadCount, setIsDrawerOpen } = useNotifications();
  const { profile } = useProfile();
  const [selectedLang, setSelectedLang] = useState('en');
  const [isLangOpen, setIsLangOpen] = useState(false);
  const [greeting, setGreeting] = useState('Good afternoon');

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting('Good morning');
    else if (hour < 17) setGreeting('Good afternoon');
    else setGreeting('Good evening');
  }, []);

  const handleNotificationClick = () => {
    if (onOpenNotifications) {
      onOpenNotifications();
    } else {
      setIsDrawerOpen(true);
    }
  };

  const userName = profile?.fullName?.trim() || 'Command Officer';

  return (
    <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm border-b border-[#DCEBED] px-4 sm:px-6 py-3 shadow-subtle">
      <div className="flex items-center justify-between gap-4">
        {/* Left: Command Center Tag & Time Greeting */}
        <div className="flex items-center gap-3">
          {/* Mobile Menu Toggle Button */}
          {onToggleMobileSidebar && (
            <button
              onClick={onToggleMobileSidebar}
              className="lg:hidden p-2 rounded-xl bg-[#F4F8FA] border border-[#DCEBED] text-[#075B8A] hover:bg-[#EEF5F8] transition-colors"
              aria-label="Open Navigation Menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}

          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#EDFAFC] border border-[#AEEBF0] text-[#075B8A] text-[10px] font-mono font-bold tracking-wider uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-[#18C3D0] animate-pulse" />
              <span>{AEGIS_TOKENS.commandCenter}</span>
            </div>
            <h2 className="text-sm sm:text-base font-extrabold text-[#18364A] tracking-tight font-sans mt-0.5">
              {greeting}, <span className="text-[#075B8A]">{userName}</span>
            </h2>
          </div>
        </div>

        {/* Right: Search, Language, Data Mode Indicator, Notifications, Profile */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Real-time Data Mode Status Indicator (LIVE vs DEMO) */}
          <DataStatusIndicator />

          {/* Quick Search Shortcut */}
          {onOpenSearch && (
            <button
              onClick={onOpenSearch}
              className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#F4F8FA] hover:bg-[#EEF5F8] border border-[#DCEBED] text-xs text-[#708696] hover:text-[#18364A] transition-all"
              title="Search bulletins, states, alerts (Ctrl+K)"
            >
              <Search className="w-3.5 h-3.5 text-[#708696]" />
              <span className="text-[11px] font-medium">Search...</span>
              <kbd className="font-mono text-[9px] bg-white text-[#708696] px-1.5 py-0.5 rounded border border-[#DCEBED]">
                ⌘K
              </kbd>
            </button>
          )}

          {/* Language Selector Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsLangOpen(!isLangOpen)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-[#F4F8FA] hover:bg-[#EEF5F8] border border-[#DCEBED] text-xs font-semibold text-[#18364A] transition-colors"
              title="Change Language"
            >
              <Globe className="w-3.5 h-3.5 text-[#075B8A]" />
              <span className="uppercase text-[11px] font-mono">
                {selectedLang}
              </span>
              <ChevronDown className="w-3 h-3 text-[#708696]" />
            </button>

            {isLangOpen && (
              <div className="absolute right-0 mt-2 w-44 bg-white rounded-2xl shadow-elevated border border-[#DCEBED] py-2 z-50 animate-in fade-in slide-in-from-top-2">
                <div className="px-3 py-1 text-[10px] font-mono font-bold text-[#708696] uppercase border-b border-[#DCEBED] mb-1">
                  Language / भाषा
                </div>
                {LANGUAGES.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => {
                      setSelectedLang(lang.code);
                      setIsLangOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-1.5 text-xs text-left hover:bg-[#F4F8FA] transition-colors ${
                      selectedLang === lang.code
                        ? 'font-bold text-[#075B8A] bg-[#EDFAFC]'
                        : 'text-[#18364A]'
                    }`}
                  >
                    <span>{lang.label} ({lang.native})</span>
                    {selectedLang === lang.code && (
                      <Check className="w-3.5 h-3.5 text-[#18C3D0]" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Notifications Button */}
          <button
            onClick={handleNotificationClick}
            className="relative p-2 rounded-full bg-[#F4F8FA] hover:bg-[#EEF5F8] border border-[#DCEBED] text-[#18364A] transition-colors group"
            title="Emergency Notifications"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4 text-[#075B8A] group-hover:scale-110 transition-transform" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-[#E94B68] text-white text-[10px] font-bold font-mono flex items-center justify-center animate-pulse shadow-sm">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {/* Profile Trigger */}
          <button
            onClick={onOpenProfile}
            className="flex items-center gap-2 p-1 sm:px-2.5 sm:py-1 rounded-full bg-[#F4F8FA] hover:bg-[#EEF5F8] border border-[#DCEBED] text-xs font-semibold text-[#18364A] transition-all group"
            title="User Profile & Preferences"
          >
            <div className="w-7 h-7 rounded-full bg-[#075B8A] text-white flex items-center justify-center text-xs font-bold shadow-xs">
              {userName[0]?.toUpperCase() || 'U'}
            </div>
            <div className="text-left hidden sm:block">
              <div className="text-[11px] font-extrabold text-[#18364A] leading-tight flex items-center gap-1">
                <span>{userName}</span>
                <span className="w-1.5 h-1.5 rounded-full bg-[#45C79A]" />
              </div>
              <div className="text-[9px] text-[#708696] font-medium leading-none mt-0.5">
                Command Ops
              </div>
            </div>
          </button>
        </div>
      </div>
    </header>
  );
};
