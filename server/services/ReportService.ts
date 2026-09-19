/**
 * AEGIS ALERT - Backend ReportService
 * Handles citizen disaster reporting, verification workflows, and media attachment references with strict server-side validation.
 */

import { IncidentReportSubmission } from '../types/api';
import { FileValidationMiddleware } from '../middleware/fileValidationMiddleware';
import { SanitizationMiddleware } from '../middleware/sanitizationMiddleware';
import { AuditLogger } from './AuditLogger';

export interface IncidentReportRecord {
  id: string;
  trackingId: string;
  hazardType: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending_review' | 'verified' | 'dispatched' | 'resolved';
  location: {
    lat: number;
    lng: number;
    address: string;
    city: string;
    state: string;
  };
  mediaUrls: string[];
  contactInfo?: {
    name?: string;
    phone?: string;
    isAnonymous?: boolean;
  };
  submittedAt: string;
  reviewedBy?: string;
  dispatchUnitsAssigned?: string[];
}

export class ReportService {
  private static reports: IncidentReportRecord[] = [
    {
      id: 'rep-001',
      trackingId: 'AEGIS-REP-894215',
      hazardType: 'Flood',
      title: 'Waterlogging & Vehicle Submersion at Underpass',
      description: 'Water level reached 3 feet inside the subway. Two vehicles stalled, traffic completely halted.',
      severity: 'high',
      status: 'verified',
      location: {
        lat: 19.0760,
        lng: 72.8777,
        address: 'Milan Subway East Junction, Santacruz, Mumbai',
        city: 'Mumbai',
        state: 'Maharashtra',
      },
      mediaUrls: ['https://images.unsplash.com/photo-1547683905-f686c993aae5?w=600'],
      contactInfo: { isAnonymous: true },
      submittedAt: new Date(Date.now() - 35 * 60000).toISOString(),
      dispatchUnitsAssigned: ['Brihanmumbai Stormwater Team 04', 'Traffic Unit 12'],
    },
    {
      id: 'rep-002',
      trackingId: 'AEGIS-REP-641209',
      hazardType: 'Road Blockage',
      title: 'Large Banyan Tree Uprooted over Arterial Highway',
      description: 'Heavy wind gust brought down an ancient tree across both northbound lanes, damaging power cables.',
      severity: 'medium',
      status: 'dispatched',
      location: {
        lat: 19.0596,
        lng: 72.8656,
        address: 'Bandra-Kurla Complex Connecting Link Road',
        city: 'Mumbai',
        state: 'Maharashtra',
      },
      mediaUrls: [],
      contactInfo: { name: 'Kunal M.', phone: '+91 98201 XXXXX', isAnonymous: false },
      submittedAt: new Date(Date.now() - 70 * 60000).toISOString(),
      dispatchUnitsAssigned: ['Disaster Response Tree Clearing Unit'],
    },
  ];

  /**
   * Submit new citizen incident report
   */
  public static async createReport(
    submission: IncidentReportSubmission,
    clientIp: string = '127.0.0.1'
  ): Promise<IncidentReportRecord> {
    const trackingId = `AEGIS-REP-${Math.floor(100000 + Math.random() * 900000)}`;

    const newRecord: IncidentReportRecord = {
      id: `rep-${Date.now()}`,
      trackingId,
      hazardType: SanitizationMiddleware.stripHtmlTags(submission.hazardType),
      title: submission.title
        ? SanitizationMiddleware.stripHtmlTags(submission.title)
        : `${SanitizationMiddleware.stripHtmlTags(submission.hazardType)} incident reported near ${SanitizationMiddleware.stripHtmlTags(submission.location.city || 'local sector')}`,
      description: SanitizationMiddleware.stripHtmlTags(submission.description),
      severity: submission.severity,
      status: 'pending_review',
      location: {
        lat: submission.location.lat,
        lng: submission.location.lng,
        address: SanitizationMiddleware.stripHtmlTags(submission.location.address),
        city: SanitizationMiddleware.stripHtmlTags(submission.location.city || 'Local Area'),
        state: SanitizationMiddleware.stripHtmlTags(submission.location.state || 'India'),
      },
      mediaUrls: submission.mediaUrls || [],
      contactInfo: submission.contactInfo
        ? {
            name: submission.contactInfo.name ? SanitizationMiddleware.stripHtmlTags(submission.contactInfo.name) : undefined,
            phone: submission.contactInfo.phone ? SanitizationMiddleware.stripHtmlTags(submission.contactInfo.phone) : undefined,
            isAnonymous: submission.contactInfo.isAnonymous,
          }
        : undefined,
      submittedAt: new Date().toISOString(),
    };

    this.reports.unshift(newRecord);

    AuditLogger.log({
      action: 'INCIDENT_REPORT_CREATED',
      severity: 'INFO',
      clientIp,
      resourceId: trackingId,
      details: {
        hazardType: newRecord.hazardType,
        severity: newRecord.severity,
        city: newRecord.location.city,
      },
    });

    return newRecord;
  }

  /**
   * Get all filed incident reports
   */
  public static async getReports(limit: number = 50): Promise<IncidentReportRecord[]> {
    return this.reports.slice(0, limit);
  }

  /**
   * Upload incident media attachment with strict server-side validation
   */
  public static async processMediaUpload(
    fileData: { fileName: string; fileType?: string; fileSizeBytes?: number; base64Content?: string },
    clientIp: string = '127.0.0.1'
  ): Promise<{ mediaUrl: string; fileId: string; sanitizedFileName: string; mimeType: string }> {
    const validation = FileValidationMiddleware.validateMediaUpload(fileData);

    if (!validation.valid) {
      AuditLogger.log({
        action: 'FILE_UPLOAD_REJECTED',
        severity: 'SECURITY_ALERT',
        clientIp,
        details: {
          attemptedFileName: fileData.fileName,
          error: validation.error,
        },
      });
      throw new Error(validation.error || 'Invalid media attachment.');
    }

    const fileId = `media-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const mediaUrl = `/storage/incidents/${fileId}-${validation.sanitizedFileName}`;

    AuditLogger.log({
      action: 'FILE_UPLOAD_ACCEPTED',
      severity: 'INFO',
      clientIp,
      resourceId: fileId,
      details: {
        fileName: validation.sanitizedFileName,
        mimeType: validation.detectedMimeType,
        sizeBytes: validation.fileSizeBytes,
      },
    });

    return {
      fileId,
      mediaUrl,
      sanitizedFileName: validation.sanitizedFileName,
      mimeType: validation.detectedMimeType || 'image/jpeg',
    };
  }
}
