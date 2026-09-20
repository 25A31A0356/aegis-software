import React, { useState, useEffect } from 'react';
import { ActivityFeed } from '../components/activity/ActivityFeed';
import { ActivityFeedItem } from '../types/activity';
import { ShieldCheck, Radio, RefreshCw } from 'lucide-react';
import { ApiClient } from '../services/apiClient';

interface ActivityPageProps {
  onNavigate: (tab: string) => void;
  onSelectHazardById?: (id: string) => void;
}

export const ActivityPage: React.FC<ActivityPageProps> = ({
  onNavigate,
  onSelectHazardById,
}) => {
  const [activities, setActivities] = useState<ActivityFeedItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const fetchActivities = async () => {
    try {
      const data = await ApiClient.get<any[]>('/activity', { limit: 50 });
      if (data && Array.isArray(data)) {
        const mapped: ActivityFeedItem[] = data.map((item) => {
          let category: ActivityFeedItem['category'] = 'official_bulletin';
          const catLower = (item.category || item.event_type || '').toLowerCase();
          if (catLower.includes('sos')) category = 'sos_dispatch';
          else if (catLower.includes('radar') || catLower.includes('weather')) category = 'radar_alert';
          else if (catLower.includes('shelter')) category = 'shelter_update';
          else if (catLower.includes('report') || item.source === 'COMMUNITY') category = 'incident_detected';
          else if (catLower.includes('advisory')) category = 'advisory_escalation';

          const sevLower = (item.severity || 'moderate').toLowerCase();
          const sev: ActivityFeedItem['severity'] =
            sevLower === 'critical' || sevLower === 'extreme'
              ? 'critical'
              : sevLower === 'warning' || sevLower === 'high'
              ? 'warning'
              : sevLower === 'info'
              ? 'info'
              : sevLower === 'safe'
              ? 'safe'
              : 'moderate';

          return {
            id: item.id || `act-${Math.random().toString(36).substring(2, 7)}`,
            timestamp: item.created_at
              ? new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : 'Live',
            relativeTime: 'Live Telemetry',
            category,
            severity: sev,
            title: item.title || 'Emergency Telemetry Activity',
            description: item.description || 'Active operational event registered on AEGIS Unified Stream.',
            locationTag: item.location_name || `${item.city ? item.city + ', ' : ''}${item.state || 'India'}`,
            sourceAgency: item.source === 'COMMUNITY' ? 'Citizen Verified Report' : 'Official Emergency Network',
            scope: 'india',
            isVerified: item.verification_status === 'VERIFIED' || item.source !== 'COMMUNITY',
            coordinates: item.latitude && item.longitude ? [item.latitude, item.longitude] : undefined,
          };
        });
        setActivities(mapped);
      } else {
        setActivities([]);
      }
    } catch (err) {
      console.warn('[ActivityPage] fetchActivities error:', err);
      setActivities([]);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchActivities();

    // Connect SSE stream for real-time live events
    let eventSource: EventSource | null = null;
    try {
      const sseUrl = `${ApiClient.getBaseUrl('v1')}/activity/stream`;
      eventSource = new EventSource(sseUrl);
      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed && parsed.id) {
            fetchActivities();
          }
        } catch {
          // ignore keepalive
        }
      };
    } catch (err) {
      console.warn('[ActivityPage] SSE connection error:', err);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    fetchActivities();
  };

  const handleSelectActivity = (item: ActivityFeedItem) => {
    if (item.category === 'sos_dispatch') {
      onNavigate('sos');
    } else if (item.category === 'radar_alert') {
      onNavigate('forecasts');
    } else if (item.category === 'shelter_update') {
      onNavigate('live-map');
    } else {
      onNavigate('hazards');
    }
  };

  return (
    <div className="max-w-[1720px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-card">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="font-extrabold text-base text-slate-900 dark:text-white font-mono uppercase tracking-wider">
              Real-Time Emergency Intelligence & Telemetry Feed
            </h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">
            Continuous Multi-Source Audit Stream: IMD • CWC • INCOIS • NDMA • SDMAs
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-xl">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Multi-Agency Stream: Active</span>
          </div>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1 text-xs font-mono text-slate-700 dark:text-slate-200 hover:text-slate-900 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 px-3 py-1.5 rounded-xl transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Activity Feed Container */}
      {isLoading ? (
        <div className="p-12 text-center text-xs font-mono text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
          Loading authentic activity stream from AEGIS unified core...
        </div>
      ) : activities.length === 0 ? (
        <div className="p-12 text-center text-xs font-mono text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
          No active emergency telemetry activities reported at this moment.
        </div>
      ) : (
        <ActivityFeed
          activities={activities}
          onSelectActivity={handleSelectActivity}
        />
      )}
    </div>
  );
};
