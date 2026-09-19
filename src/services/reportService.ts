import { CitizenReport, ReportMediaItem, ReportHazardType, ReportSeverity, ReportStatus } from '../types/report';

const STORAGE_KEY = 'aegis_citizen_reports';

export const INITIAL_DEMO_REPORTS: CitizenReport[] = [
  {
    id: 'AEGIS-REP-849102',
    hazardType: 'flood',
    hazardLabel: 'Urban Flooding',
    location: {
      lat: 17.4483,
      lng: 78.3915,
      address: 'Madhapur Main Road near Cyber Towers Underpass',
      city: 'Hyderabad',
      state: 'Telangana',
      pincode: '500081',
    },
    media: [
      {
        id: 'med-101',
        mediaReference: 's3://aegis-media-vault/2026/09/rep-849102-1.jpg',
        url: 'https://images.unsplash.com/photo-1547683905-f686c993aae5?auto=format&fit=crop&w=600&q=80',
        fileType: 'image/jpeg',
        fileSize: 1420500,
        fileName: 'underpass_waterlogging.jpg',
        uploadedAt: '18 mins ago',
      },
    ],
    description: 'Underpass completely submerged with 3.5 feet of rushing storm runoff. Multiple four-wheelers stalled in water.',
    severity: 'high',
    optionalDetails: {
      peopleAffectedEstimate: '20-50',
      isRoadBlocked: true,
      isImmediateDanger: true,
    },
    reporter: {
      name: 'Priya Reddy',
      isAnonymous: false,
    },
    timestamp: 'Today, 02:45 PM IST',
    status: 'verified',
    verificationNotes: 'GHMC Disaster Response Force deployed 2 dewatering suction pumps.',
  },
  {
    id: 'AEGIS-REP-731945',
    hazardType: 'road_blockage',
    hazardLabel: 'Fallen Tree & Grid Line',
    location: {
      lat: 19.0760,
      lng: 72.8777,
      address: 'SVT Road, Bandra West',
      city: 'Mumbai',
      state: 'Maharashtra',
      pincode: '400050',
    },
    media: [
      {
        id: 'med-102',
        mediaReference: 's3://aegis-media-vault/2026/09/rep-731945-1.jpg',
        url: 'https://images.unsplash.com/photo-1527482797697-8795b05a13fe?auto=format&fit=crop&w=600&q=80',
        fileType: 'image/jpeg',
        fileSize: 2104000,
        fileName: 'fallen_tree.jpg',
        uploadedAt: '1 hour ago',
      },
    ],
    description: 'Centuries-old banyan tree uprooted across dual carriageway during gale winds, snapping domestic power wires.',
    severity: 'medium',
    optionalDetails: {
      peopleAffectedEstimate: '5-20',
      isRoadBlocked: 'partial',
      isImmediateDanger: false,
    },
    reporter: {
      isAnonymous: true,
    },
    timestamp: 'Today, 01:20 PM IST',
    status: 'dispatched',
    verificationNotes: 'Brihanmumbai Municipal Corporation tree-clearing crew on site.',
  },
  {
    id: 'AEGIS-REP-610283',
    hazardType: 'landslide',
    hazardLabel: 'Mudslide Debris',
    location: {
      lat: 30.7333,
      lng: 78.4333,
      address: 'NH-108 Milepost 42, near Dharasu Bend',
      city: 'Uttarkashi',
      state: 'Uttarakhand',
      pincode: '249193',
    },
    media: [
      {
        id: 'med-103',
        mediaReference: 's3://aegis-media-vault/2026/09/rep-610283-1.jpg',
        url: 'https://images.unsplash.com/photo-1542382156909-9ae37b3f56fd?auto=format&fit=crop&w=600&q=80',
        fileType: 'image/jpeg',
        fileSize: 3180000,
        fileName: 'mudslide_debris.jpg',
        uploadedAt: '3 hours ago',
      },
    ],
    description: 'Hillside rockfall and wet mud debris blocking single-lane mountain highway. Traffic halted on both sides.',
    severity: 'critical',
    optionalDetails: {
      peopleAffectedEstimate: '50+',
      isRoadBlocked: true,
      isImmediateDanger: true,
    },
    reporter: {
      name: 'Rohan Joshi',
      isAnonymous: false,
    },
    timestamp: 'Today, 11:30 AM IST',
    status: 'pending_review',
    verificationNotes: 'Border Roads Organisation (BRO) bulldozers en route.',
  },
];

export class ReportService {
  /**
   * Mock Object Storage abstraction for media uploads (e.g. S3 / GCS / Cloudflare R2)
   */
  public static async uploadMediaToObjectStorage(file: File): Promise<ReportMediaItem> {
    // Validate file type
    const validImageTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/heic'];
    const validVideoTypes = ['video/mp4', 'video/quicktime', 'video/webm'];
    const isImage = validImageTypes.includes(file.type);
    const isVideo = validVideoTypes.includes(file.type);

    if (!isImage && !isVideo) {
      throw new Error(`Unsupported media format: ${file.type}. Please upload JPG, PNG, or MP4.`);
    }

    // Check size limits (Image <= 15MB, Video <= 50MB)
    const maxSizeBytes = isVideo ? 50 * 1024 * 1024 : 15 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      throw new Error(`File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds maximum limit (${isVideo ? '50MB' : '15MB'}).`);
    }

    // Simulate async network upload to object storage bucket
    await new Promise((resolve) => setTimeout(resolve, 600));

    const mediaId = `med-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
    const objectStorageKey = `s3://aegis-media-vault/${new Date().getFullYear()}/${String(new Date().getMonth() + 1).padStart(2, '0')}/${mediaId}-${file.name.replace(/\s+/g, '_')}`;

    // Read preview URL
    let previewUrl = '';
    if (typeof FileReader !== 'undefined') {
      previewUrl = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result as string);
        reader.readAsDataURL(file);
      });
    } else if (typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
      previewUrl = URL.createObjectURL(file);
    } else {
      previewUrl = `blob:https://aegis.gov.in/${mediaId}`;
    }

    return {
      id: mediaId,
      mediaReference: objectStorageKey,
      url: previewUrl,
      fileType: file.type,
      fileSize: file.size,
      fileName: file.name,
      uploadedAt: 'Just now',
    };
  }

  /**
   * POST /api/reports API endpoint simulation
   */
  public static async submitReport(
    payload: Omit<CitizenReport, 'id' | 'timestamp' | 'status'>
  ): Promise<CitizenReport> {
    // Server-side validation
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

    // Simulate backend network latency
    await new Promise((resolve) => setTimeout(resolve, 800));

    const reportId = `AEGIS-REP-${Math.floor(100000 + Math.random() * 900000)}`;
    const now = new Date();
    const timestamp = `Today, ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} IST`;

    const newReport: CitizenReport = {
      ...payload,
      id: reportId,
      timestamp,
      status: 'pending_review',
    };

    // Persist report in LocalStorage
    const existing = this.getAllReports();
    const updated = [newReport, ...existing];
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      }
    } catch (e) {
      console.warn('[ReportService] Failed to save to localStorage:', e);
    }

    return newReport;
  }

  /**
   * Get all citizen reports
   */
  public static getAllReports(): CitizenReport[] {
    try {
      if (typeof localStorage !== 'undefined') {
        const stored = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('agies_citizen_reports');
        if (stored) {
          return JSON.parse(stored);
        }
      }
    } catch {
      // fallback
    }
    return INITIAL_DEMO_REPORTS;
  }

  /**
   * Retrieve report by ID
   */
  public static getReportById(id: string): CitizenReport | undefined {
    const all = this.getAllReports();
    return all.find((r) => r.id === id);
  }
}
