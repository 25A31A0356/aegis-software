import { CitizenReport, ReportMediaItem, ReportHazardType, ReportSeverity, ReportStatus } from '../types/report';
import { ApiClient } from './apiClient';

const STORAGE_KEY = 'aegis_cached_citizen_reports';

export class ReportService {
  private static cachedReports: CitizenReport[] = [];
  private static listeners: Array<(reports: CitizenReport[]) => void> = [];

  private static mapBackendToCitizenReport(r: any): CitizenReport {
    const rawHazard = (r.hazard_type || r.category || 'other').toLowerCase();
    let mappedHazard: ReportHazardType = 'other';
    if (rawHazard.includes('flood') || rawHazard.includes('waterlog')) mappedHazard = 'flood';
    else if (rawHazard.includes('fire')) mappedHazard = 'fire';
    else if (rawHazard.includes('earthquake')) mappedHazard = 'earthquake';
    else if (rawHazard.includes('cyclone') || rawHazard.includes('storm')) mappedHazard = 'cyclone';
    else if (rawHazard.includes('landslide')) mappedHazard = 'landslide';
    else if (rawHazard.includes('road') || rawHazard.includes('tree') || rawHazard.includes('blocked')) mappedHazard = 'road_blockage';
    else if (rawHazard.includes('rain')) mappedHazard = 'heavy_rainfall';
    else if (rawHazard.includes('lightning')) mappedHazard = 'lightning';

    const rawSev = (r.severity || 'moderate').toLowerCase();
    let mappedSeverity: ReportSeverity = 'medium';
    if (rawSev === 'critical' || rawSev === 'extreme') mappedSeverity = 'critical';
    else if (rawSev === 'high' || rawSev === 'warning') mappedSeverity = 'high';
    else if (rawSev === 'low' || rawSev === 'minor') mappedSeverity = 'low';

    const rawStatus = (r.status || 'active').toLowerCase();
    let mappedStatus: ReportStatus = 'pending_review';
    if (rawStatus === 'verified' || r.is_verified) mappedStatus = 'verified';
    else if (rawStatus === 'dispatched') mappedStatus = 'dispatched';
    else if (rawStatus === 'resolved') mappedStatus = 'resolved';

    const mediaUrls: string[] = Array.isArray(r.media_urls) ? r.media_urls : [];
    const mediaItems: ReportMediaItem[] = mediaUrls.map((url: string, idx: number) => ({
      id: `med-${r.id}-${idx}`,
      mediaReference: url,
      url,
      fileType: url.endsWith('.mp4') ? 'video/mp4' : 'image/jpeg',
      fileSize: 1024 * 1024,
      fileName: url.split('/').pop() || 'media.jpg',
      uploadedAt: r.created_at || 'Recently',
    }));

    return {
      id: r.id,
      hazardType: mappedHazard,
      hazardLabel: r.title || `${mappedHazard.replace('_', ' ').toUpperCase()} Incident`,
      location: {
        lat: Number(r.latitude) || 0,
        lng: Number(r.longitude) || 0,
        address: r.location_name || `${r.city || 'Local Area'}, ${r.state || 'India'}`,
        city: r.city || '',
        state: r.state || 'India',
        pincode: '',
      },
      media: mediaItems,
      description: r.description || '',
      severity: mappedSeverity,
      optionalDetails: {
        peopleAffectedEstimate: '5-20',
        isRoadBlocked: mappedHazard === 'road_blockage' || mappedHazard === 'landslide',
        isImmediateDanger: mappedSeverity === 'critical',
      },
      reporter: {
        name: r.reporter_name || 'Citizen Observer',
        isAnonymous: !r.reporter_name || r.reporter_name === 'Citizen Observer',
      },
      timestamp: r.created_at ? new Date(r.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : 'Just now',
      status: mappedStatus,
      verificationNotes: r.verification_status || 'Community Submission',
    };
  }

  /**
   * Upload media item to backend object storage vault
   */
  public static async uploadMediaToObjectStorage(file: File): Promise<ReportMediaItem> {
    const validImageTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/heic'];
    const validVideoTypes = ['video/mp4', 'video/quicktime', 'video/webm'];
    const isImage = validImageTypes.includes(file.type);
    const isVideo = validVideoTypes.includes(file.type);

    if (!isImage && !isVideo) {
      throw new Error(`Unsupported media format: ${file.type}. Please upload JPG, PNG, or MP4.`);
    }

    const maxSizeBytes = isVideo ? 50 * 1024 * 1024 : 15 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      throw new Error(`File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds maximum limit (${isVideo ? '50MB' : '15MB'}).`);
    }

    // Convert to base64 for local preview or server upload
    let previewUrl = '';
    if (typeof FileReader !== 'undefined') {
      previewUrl = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result as string);
        reader.readAsDataURL(file);
      });
    }

    // Try backend upload
    try {
      const uploadResp = await ApiClient.post<{ mediaUrl: string; fileId: string }>('/reports/media/upload', {
        fileName: file.name,
        fileType: file.type,
        fileSizeBytes: file.size,
        base64Content: previewUrl,
      });

      if (uploadResp?.mediaUrl) {
        return {
          id: uploadResp.fileId || `med-${Date.now()}`,
          mediaReference: uploadResp.mediaUrl,
          url: previewUrl || uploadResp.mediaUrl,
          fileType: file.type,
          fileSize: file.size,
          fileName: file.name,
          uploadedAt: 'Just now',
        };
      }
    } catch {
      // fallback to preview url
    }

    const mediaId = `med-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    return {
      id: mediaId,
      mediaReference: `aegis-storage://incidents/${mediaId}-${file.name.replace(/\s+/g, '_')}`,
      url: previewUrl,
      fileType: file.type,
      fileSize: file.size,
      fileName: file.name,
      uploadedAt: 'Just now',
    };
  }

  /**
   * Submit citizen incident report to the central PostgreSQL database
   */
  public static async submitReport(
    payload: Omit<CitizenReport, 'id' | 'timestamp' | 'status'>
  ): Promise<CitizenReport> {
    if (!payload.hazardType) {
      throw new Error('Hazard type is required.');
    }
    if (!payload.location || !payload.location.address) {
      throw new Error('Valid location and address are required.');
    }
    if (!payload.description || payload.description.trim().length < 10) {
      throw new Error('Please provide at least 10 characters describing the incident.');
    }
    if (!payload.severity) {
      throw new Error('Severity classification is required.');
    }

    const backendPayload = {
      category: payload.hazardType.toUpperCase(),
      hazard_type: payload.hazardType.toUpperCase(),
      title: payload.hazardLabel || `${payload.hazardType} incident reported`,
      description: payload.description,
      severity: payload.severity.toUpperCase(),
      latitude: payload.location.lat,
      longitude: payload.location.lng,
      accuracy_meters: 10.0,
      location_name: payload.location.address,
      city: payload.location.city || '',
      state: payload.location.state || 'India',
      country: 'India',
      media_urls: payload.media ? payload.media.map((m) => m.url || m.mediaReference) : [],
      reporter_name: payload.reporter.isAnonymous ? 'Citizen Observer' : (payload.reporter.name || 'Citizen Observer'),
      idempotency_key: `rep-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
    };

    try {
      const resp = await ApiClient.post<any>('/reports', backendPayload);
      if (resp) {
        const mapped = this.mapBackendToCitizenReport(resp);
        this.cachedReports.unshift(mapped);
        this.saveToStorage();
        this.notifyListeners();
        return mapped;
      }
    } catch (err) {
      console.warn('[ReportService] Backend submit error:', err);
    }

    // Local state fallback if backend temporarily unreachable
    const fallbackId = `AEGIS-REP-${Math.floor(100000 + Math.random() * 900000)}`;
    const newReport: CitizenReport = {
      ...payload,
      id: fallbackId,
      timestamp: new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }),
      status: 'pending_review',
    };
    this.cachedReports.unshift(newReport);
    this.saveToStorage();
    this.notifyListeners();
    return newReport;
  }

  /**
   * Fetch all citizen reports from PostgreSQL backend
   */
  public static async fetchAllReports(): Promise<CitizenReport[]> {
    try {
      const rows = await ApiClient.get<any[]>('/reports', { limit: 50 });
      if (rows && Array.isArray(rows)) {
        const mapped = rows.map((r) => this.mapBackendToCitizenReport(r));
        this.cachedReports = mapped;
        this.saveToStorage();
        this.notifyListeners();
        return mapped;
      }
    } catch (err) {
      console.warn('[ReportService] fetchAllReports error:', err);
    }
    return this.getAllReports();
  }

  /**
   * Synchronous cached getter
   */
  public static getAllReports(): CitizenReport[] {
    if (this.cachedReports.length > 0) {
      return [...this.cachedReports];
    }
    try {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          this.cachedReports = JSON.parse(stored);
          return [...this.cachedReports];
        }
      }
    } catch {}
    return [];
  }

  public static getReportById(id: string): CitizenReport | undefined {
    return this.getAllReports().find((r) => r.id === id);
  }

  private static saveToStorage() {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.cachedReports));
      }
    } catch {}
  }

  public static subscribe(listener: (reports: CitizenReport[]) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private static notifyListeners() {
    const clone = [...this.cachedReports];
    this.listeners.forEach((l) => l(clone));
  }
}
