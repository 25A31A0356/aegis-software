export type ReportHazardType =
  | 'flood'
  | 'fire'
  | 'earthquake'
  | 'cyclone'
  | 'landslide'
  | 'road_blockage'
  | 'heavy_rainfall'
  | 'lightning'
  | 'other';

export type ReportSeverity = 'low' | 'medium' | 'high' | 'critical';

export type ReportStatus = 'pending_review' | 'verified' | 'dispatched' | 'resolved' | 'dismissed';

export interface ReportMediaItem {
  id: string;
  mediaReference: string; // Object storage bucket key e.g. "s3://aegis-media/2026/09/rep-xxx.jpg"
  url: string; // Preview data URL or CDN URL
  fileType: 'image/jpeg' | 'image/png' | 'video/mp4' | 'video/quicktime' | string;
  fileSize: number; // in bytes
  fileName: string;
  uploadedAt: string;
}

export interface CitizenReport {
  id: string;
  hazardType: ReportHazardType;
  hazardLabel: string;
  location: {
    lat: number;
    lng: number;
    address: string;
    city: string;
    state: string;
    pincode?: string;
  };
  media: ReportMediaItem[];
  description: string;
  severity: ReportSeverity;
  optionalDetails: {
    peopleAffectedEstimate?: string;
    isRoadBlocked: boolean | 'partial';
    isImmediateDanger: boolean;
    contactPhone?: string;
  };
  reporter: {
    name?: string;
    isAnonymous: boolean;
    deviceFingerprint?: string;
  };
  timestamp: string;
  status: ReportStatus;
  verificationNotes?: string;
}
