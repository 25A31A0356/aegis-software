import React, { useState, useEffect } from 'react';
import { DataProvider } from './context/DataProviderContext';
import { LocationProvider } from './context/LocationContext';
import { NotificationProvider } from './context/NotificationContext';
import { SOSProvider } from './context/SOSContext';
import { ProfileProvider } from './context/ProfileContext';

// Global Layout Shell & Common Components
import {
  Sidebar,
  Header,
  AlertTicker,
  FloatingAskAGIES,
  DataModeModal,
} from './components/common';

// Existing Overlays & Modals
import { SearchModal } from './components/layout/SearchModal';
import { NotificationDrawer } from './components/layout/NotificationDrawer';
import { UserProfileModal } from './components/profile/UserProfileModal';

// Pages
import { DashboardPage } from './pages/DashboardPage';
import { LiveMapPage } from './pages/LiveMapPage';
import { ForecastsPage } from './pages/ForecastsPage';
import { SafetyPage } from './pages/SafetyPage';
import { ReportsPage } from './pages/ReportsPage';
import { HazardsPage } from './pages/HazardsPage';
import { SOSPage } from './pages/SOSPage';
import { ActivityPage } from './pages/ActivityPage';
import { DataCoreAdminPage } from './pages/DataCoreAdminPage';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('homepage');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [isProfileOpen, setIsProfileOpen] = useState<boolean>(false);
  const [selectedHazardId, setSelectedHazardId] = useState<string | null>(null);
  const [selectedSOSId, setSelectedSOSId] = useState<string | null>(null);
  const [initialHazardCategory, setInitialHazardCategory] = useState<string | undefined>(undefined);

  // Keyboard shortcut for Search (Ctrl+K / Cmd+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelectHazardFromTickerOrSearch = (hazardId: string) => {
    setSelectedHazardId(hazardId);
    setActiveTab('hazards');
  };

  const handleSelectSOSFromSearch = (sosId: string) => {
    setSelectedSOSId(sosId);
    setActiveTab('sos');
  };

  const handleFilterHazardsCategory = (category: string) => {
    setInitialHazardCategory(category);
    setActiveTab('hazards');
  };

  return (
    <DataProvider>
      <LocationProvider>
        <NotificationProvider>
          <SOSProvider>
            <ProfileProvider>
              <div className="min-h-screen flex bg-[#F4F8FA] text-[#18364A] antialiased font-sans selection:bg-[#18C3D0]/30 selection:text-[#075B8A]">
                {/* DESKTOP / TABLET FIXED SIDEBAR */}
                <div className="hidden lg:block shrink-0 sticky top-0 h-screen z-30">
                  <Sidebar
                    activeTab={activeTab}
                    setActiveTab={setActiveTab}
                    isCollapsed={isSidebarCollapsed}
                    onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                  />
                </div>

                {/* MOBILE SLIDE-OUT DRAWER SIDEBAR */}
                {isMobileSidebarOpen && (
                  <div className="fixed inset-0 z-50 lg:hidden flex">
                    {/* Backdrop */}
                    <div
                      onClick={() => setIsMobileSidebarOpen(false)}
                      className="fixed inset-0 bg-[#075B8A]/50 backdrop-blur-xs transition-opacity"
                    />
                    {/* Sidebar Drawer */}
                    <div className="relative z-10 w-[240px] h-full shadow-2xl animate-in slide-in-from-left duration-200">
                      <Sidebar
                        activeTab={activeTab}
                        setActiveTab={setActiveTab}
                        isMobileDrawer={true}
                        onCloseMobileDrawer={() => setIsMobileSidebarOpen(false)}
                      />
                    </div>
                  </div>
                )}

                {/* MAIN CONTENT COLUMN */}
                <div className="flex-1 flex flex-col min-w-0">
                  {/* Top Header */}
                  <Header
                    onOpenSearch={() => setIsSearchOpen(true)}
                    onOpenProfile={() => setIsProfileOpen(true)}
                    onToggleMobileSidebar={() => setIsMobileSidebarOpen(true)}
                  />

                  {/* Below Header: Live Alerts Marquee Ticker */}
                  <AlertTicker onSelectHazard={handleSelectHazardFromTickerOrSearch} />

                  {/* Main Content Viewport */}
                  <main className="flex-1 p-4 sm:p-6 lg:p-8">
                    {(activeTab === 'homepage' || activeTab === 'dashboard') && (
                      <DashboardPage
                        onNavigate={setActiveTab}
                        onSelectHazardById={handleSelectHazardFromTickerOrSearch}
                        onFilterHazardsCategory={handleFilterHazardsCategory}
                      />
                    )}

                    {(activeTab === 'analytics' || activeTab === 'forecasts') && (
                      <ForecastsPage />
                    )}

                    {activeTab === 'safety' && (
                      <SafetyPage onNavigateToSOS={() => setActiveTab('sos')} />
                    )}

                    {activeTab === 'reports' && (
                      <ReportsPage />
                    )}

                    {activeTab === 'sos' && (
                      <SOSPage preSelectedSOSId={selectedSOSId} />
                    )}

                    {activeTab === 'hazards' && (
                      <HazardsPage
                        onNavigate={setActiveTab}
                        preSelectedHazardId={selectedHazardId}
                        initialCategory={initialHazardCategory}
                      />
                    )}

                    {activeTab === 'activity' && (
                      <ActivityPage
                        onNavigate={setActiveTab}
                        onSelectHazardById={handleSelectHazardFromTickerOrSearch}
                      />
                    )}

                    {activeTab === 'live-map' && (
                      <LiveMapPage
                        onNavigate={setActiveTab}
                        onSelectHazardById={handleSelectHazardFromTickerOrSearch}
                      />
                    )}

                    {activeTab === 'datacore' && (
                      <DataCoreAdminPage />
                    )}
                  </main>
                </div>

                {/* GLOBALLY PERSISTENT FLOATING ASK AGIES CHATBOT (Bottom Right Corner) */}
                <FloatingAskAGIES
                  activeTab={activeTab}
                  selectedHazard={selectedHazardId}
                  onNavigate={setActiveTab}
                />

                {/* Global Search Dialog (Ctrl+K) */}
                <SearchModal
                  isOpen={isSearchOpen}
                  onClose={() => setIsSearchOpen(false)}
                  onNavigate={setActiveTab}
                  onSelectHazard={handleSelectHazardFromTickerOrSearch}
                  onSelectSOS={handleSelectSOSFromSearch}
                />

                {/* Emergency Notification Drawer */}
                <NotificationDrawer
                  onNavigate={setActiveTab}
                  onSelectHazard={handleSelectHazardFromTickerOrSearch}
                />

                {/* Citizen Safety Profile Modal */}
                <UserProfileModal
                  isOpen={isProfileOpen}
                  onClose={() => setIsProfileOpen(false)}
                />

                {/* Data Provider Inspector & Mode Switcher Modal */}
                <DataModeModal />
              </div>
            </ProfileProvider>
          </SOSProvider>
        </NotificationProvider>
      </LocationProvider>
    </DataProvider>
  );
};
