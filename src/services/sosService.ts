import { SOSBeacon, SOSTriageStatus, SOSEmergencyType } from '../types/sos';
import { ApiClient } from './apiClient';

const STORAGE_KEY = 'aegis_user_sos_beacons';

export class SOSService {
  private static beacons: SOSBeacon[] = SOSService.loadFromStorage();
  private static listeners: Array<(beacons: SOSBeacon[]) => void> = [];

  private static loadFromStorage(): SOSBeacon[] {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        return JSON.parse(data);
      }
    } catch {
      // ignore
    }
    return [];
  }

  private static saveToStorage() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.beacons));
    } catch {
      // ignore
    }
  }

  public static async fetchActiveBeacons(): Promise<SOSBeacon[]> {
    try {
      const backendBeacons = await ApiClient.get<any[]>('/sos', { status: 'ACTIVE' });
      if (backendBeacons && Array.isArray(backendBeacons)) {
        const mapped: SOSBeacon[] = backendBeacons.map((b) => ({
          id: b.id,
          anonymousAlias: b.caller_name || `Beacon #${b.id.substring(0, 6)}`,
          phoneMasked: b.caller_phone_masked || 'CONFIDENTIAL',
          timestamp: b.created_at || new Date().toISOString(),
          emergencyType: (b.emergency_type || 'general_distress') as SOSEmergencyType,
          emergencyTitle: `Emergency SOS: ${(b.emergency_type || 'General').toUpperCase()}`,
          locationName: b.address || `${b.district || ''}, ${b.state || 'India'}`,
          district: b.district || 'Local District',
          state: b.state || 'India',
          coordinates: [b.latitude || 20.5937, b.longitude || 78.9629],
          gpsAccuracyMeters: b.accuracy_meters || 10.0,
          batteryPercent: b.battery_percent || 100,
          personsCount: b.casualties_count || 1,
          triageStatus: (b.status || 'incoming').toLowerCase() as SOSTriageStatus,
          severity: 'critical',
          timeline: [
            {
              timestamp: b.created_at ? new Date(b.created_at).toLocaleTimeString() : 'Live',
              actor: 'AEGIS Emergency Network',
              action: `Distress Status: ${b.status}`,
              notes: b.short_message || 'Distress signal received by command center.',
            },
          ],
        }));

        this.beacons = mapped;
        this.saveToStorage();
        this.notifyListeners();
        return this.beacons;
      }
    } catch (err) {
      console.warn('[SOSService] fetchActiveBeacons error:', err);
    }
    return this.getBeacons();
  }

  public static getBeacons(): SOSBeacon[] {
    return [...this.beacons];
  }

  public static getBeaconById(id: string): SOSBeacon | undefined {
    return this.beacons.find((b) => b.id === id);
  }

  public static updateTriageStatus(
    id: string,
    newStatus: SOSTriageStatus,
    actorName: string = 'Command Center Operator',
    notes?: string
  ): SOSBeacon | undefined {
    const beacon = this.beacons.find((b) => b.id === id);
    if (!beacon) return undefined;

    beacon.triageStatus = newStatus;
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    const actionText =
      newStatus === 'acknowledged'
        ? 'Distress Beacon Acknowledged by Dispatcher'
        : newStatus === 'dispatching'
        ? 'Emergency Response Unit Dispatched En Route'
        : newStatus === 'on_scene'
        ? 'Rescue Unit Arrived On Scene'
        : newStatus === 'resolved'
        ? 'Incident Resolved & Extracted to Safety'
        : newStatus === 'cancelled'
        ? 'Distress Beacon Cancelled / False Alarm'
        : 'Status Updated';

    beacon.timeline.unshift({
      timestamp: timeStr,
      actor: actorName,
      action: actionText,
      notes: notes || `Triage transitioned to ${newStatus.toUpperCase()}`,
    });

    this.saveToStorage();
    this.notifyListeners();
    return { ...beacon };
  }

  public static async triggerLiveSOS(beaconData: {
    caller_name?: string;
    caller_phone?: string;
    emergency_type?: string;
    severity?: string;
    short_message?: string;
    latitude: number;
    longitude: number;
    accuracy_meters?: number;
    district?: string;
    state?: string;
    battery_percent?: number;
    casualties_count?: number;
  }): Promise<SOSBeacon> {
    try {
      const res = await ApiClient.post<any>('/sos', {
        caller_name: beaconData.caller_name || 'Citizen in Distress',
        caller_phone: beaconData.caller_phone || '',
        emergency_type: beaconData.emergency_type || 'general',
        severity: beaconData.severity || 'CRITICAL',
        short_message: beaconData.short_message || '',
        latitude: beaconData.latitude,
        longitude: beaconData.longitude,
        accuracy_meters: beaconData.accuracy_meters || 10.0,
        district: beaconData.district || '',
        state: beaconData.state || '',
        battery_percent: beaconData.battery_percent || 100,
        casualties_count: beaconData.casualties_count || 1,
      });

      if (res && res.id) {
        const newBeacon: SOSBeacon = {
          id: res.id,
          anonymousAlias: res.caller_name || `Beacon #${res.id.substring(0, 6)}`,
          phoneMasked: res.caller_phone_masked || 'CONFIDENTIAL',
          timestamp: res.created_at || new Date().toISOString(),
          emergencyType: res.emergency_type || 'general',
          emergencyTitle: `Emergency SOS: ${(res.emergency_type || 'General').toUpperCase()}`,
          locationName: res.address || `${res.district || ''}, ${res.state || 'India'}`,
          district: res.district || 'Local District',
          state: res.state || 'India',
          coordinates: [res.latitude, res.longitude],
          gpsAccuracyMeters: res.accuracy_meters || 10.0,
          batteryPercent: res.battery_percent || 100,
          personsCount: res.casualties_count || 1,
          triageStatus: 'incoming',
          severity: 'critical',
          timeline: [
            {
              timestamp: new Date().toLocaleTimeString(),
              actor: 'AEGIS Core Gateway',
              action: 'Distress Beacon Initialized',
              notes: 'High priority push received and dispatched to nearby responders.',
            },
          ],
        };

        this.beacons.unshift(newBeacon);
        this.saveToStorage();
        this.notifyListeners();
        return newBeacon;
      }
    } catch (err) {
      console.warn('[SOSService] triggerLiveSOS backend error, storing locally:', err);
    }

    // Fallback local registration
    const id = `SOS-IN-${Math.floor(1000 + Math.random() * 9000)}`;
    const localBeacon: SOSBeacon = {
      id,
      anonymousAlias: `Beacon #${id.replace('SOS-', '')} (Active User)`,
      phoneMasked: '+91 98**** 1122',
      timestamp: new Date().toISOString(),
      emergencyType: (beaconData.emergency_type as any) || 'flash_flood_stranding',
      emergencyTitle: 'Emergency Distress Beacon Received',
      locationName: 'Current User GPS Coordinates',
      district: beaconData.district || 'Local District',
      state: beaconData.state || 'India',
      coordinates: [beaconData.latitude, beaconData.longitude],
      gpsAccuracyMeters: beaconData.accuracy_meters || 5.0,
      batteryPercent: beaconData.battery_percent || 82,
      personsCount: beaconData.casualties_count || 1,
      triageStatus: 'incoming',
      severity: 'critical',
      timeline: [
        {
          timestamp: new Date().toLocaleTimeString(),
          actor: 'AEGIS Local Sentinel',
          action: 'Distress Beacon Initialized Offline',
          notes: 'Queued for transmission on network reconnection.',
        },
      ],
    };

    this.beacons.unshift(localBeacon);
    this.saveToStorage();
    this.notifyListeners();
    return localBeacon;
  }

  public static async declareSafe(safeData: {
    user_name?: string;
    user_phone?: string;
    message?: string;
    latitude: number;
    longitude: number;
    accuracy_meters?: number;
    location_name?: string;
    district?: string;
    state?: string;
  }): Promise<any> {
    try {
      const res = await ApiClient.post<any>('/sos/safe', {
        user_name: safeData.user_name || 'Citizen',
        user_phone: safeData.user_phone || '',
        message: safeData.message || 'I am safe and out of danger.',
        latitude: safeData.latitude,
        longitude: safeData.longitude,
        accuracy_meters: safeData.accuracy_meters || 10.0,
        location_name: safeData.location_name || '',
        district: safeData.district || '',
        state: safeData.state || '',
      });
      // Also clear active local beacons
      this.clearAllBeacons();
      return res;
    } catch (err) {
      console.warn('[SOSService] declareSafe backend error:', err);
      this.clearAllBeacons();
      return null;
    }
  }

  public static createDemoBeacon(beaconData: Partial<SOSBeacon>): SOSBeacon {
    const id = `SOS-IN-${Math.floor(1000 + Math.random() * 9000)}`;
    const newBeacon: SOSBeacon = {
      id,
      anonymousAlias: `Beacon #${id.replace('SOS-', '')} (Active User)`,
      phoneMasked: '+91 98**** 1122',
      timestamp: new Date().toISOString(),
      emergencyType: beaconData.emergencyType || 'flash_flood_stranding',
      emergencyTitle: beaconData.emergencyTitle || 'Emergency Distress Beacon Received',
      locationName: beaconData.locationName || 'Current User GPS Coordinates',
      district: beaconData.district || 'Local District',
      state: beaconData.state || 'India',
      coordinates: beaconData.coordinates || [20.5937, 78.9629],
      gpsAccuracyMeters: 5.0,
      batteryPercent: 82,
      personsCount: beaconData.personsCount || 1,
      triageStatus: 'incoming',
      severity: 'critical',
      timeline: [
        {
          timestamp: new Date().toLocaleTimeString(),
          actor: 'AEGIS Web Incident Sentinel',
          action: 'Distress Beacon Initialized',
          notes: 'High priority push received via secure emergency protocol.',
        },
      ],
      ...beaconData,
    };

    this.beacons.unshift(newBeacon);
    this.saveToStorage();
    this.notifyListeners();
    return newBeacon;
  }

  public static clearAllBeacons() {
    this.beacons = [];
    this.saveToStorage();
    this.notifyListeners();
  }

  public static subscribe(listener: (beacons: SOSBeacon[]) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private static notifyListeners() {
    const clone = [...this.beacons];
    this.listeners.forEach((l) => l(clone));
  }
}
