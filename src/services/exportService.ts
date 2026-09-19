/**
 * AEGIS ALERT - Export Service
 * Handles real client-side export to CSV, printable PDF Report, and Word Document.
 */

export interface ExportDataPayload {
  title: string;
  subtitle: string;
  generatedAt: string;
  location: string;
  hazard: string;
  dateRange: string;
  stats: {
    peakIntensity: string;
    totalEvents: number;
    peopleAffected: string;
    trend: string;
  };
  timeline: Array<{ date: string; intensityIndex: number; peopleAffected: number; alertCount: number }>;
  regionalImpact: Array<{ region: string; events: number; affected: number; severity: string }>;
  severityDistribution: Array<{ name: string; value: number; color: string }>;
}

export class ExportService {
  /**
   * Generates and downloads a clean CSV spreadsheet
   */
  public static exportToCSV(payload: ExportDataPayload): void {
    const headers = ['Date / Region', 'Intensity Index', 'People Affected', 'Active Alerts', 'Severity Category'];
    const rows: string[][] = [];

    // Timeline entries
    payload.timeline.forEach((item) => {
      rows.push([item.date, String(item.intensityIndex), String(item.peopleAffected), String(item.alertCount), 'Timeline Entry']);
    });

    // Regional impact entries
    rows.push(['--- Regional Impact Breakdown ---', '', '', '', '']);
    payload.regionalImpact.forEach((reg) => {
      rows.push([reg.region, `${reg.events} Events`, String(reg.affected), String(reg.events), reg.severity.toUpperCase()]);
    });

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [
        `"AEGIS ALERT - HAZARD ANALYTICS INTELLIGENCE REPORT"`,
        `"Location: ${payload.location} | Hazard: ${payload.hazard} | Period: ${payload.dateRange}"`,
        `"Generated: ${payload.generatedAt}"`,
        `"Peak Intensity: ${payload.stats.peakIntensity} | Total Events: ${payload.stats.totalEvents} | People Affected: ${payload.stats.peopleAffected} | Trend: ${payload.stats.trend}"`,
        '',
        headers.map((h) => `"${h}"`).join(','),
        ...rows.map((row) => row.map((cell) => `"${cell}"`).join(',')),
      ].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `AEGIS_Analytics_${payload.location.replace(/\s+/g, '_')}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  /**
   * Generates a styled, high-fidelity printable HTML document for PDF export
   */
  public static exportToPDF(payload: ExportDataPayload): void {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      alert('Pop-up blocked. Please allow pop-ups to generate printable report.');
      return;
    }

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>AEGIS ALERT - Hazard Analytics Briefing</title>
        <style>
          body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #18364A; background: #FFF; }
          .header { border-bottom: 2px solid #075B8A; padding-bottom: 15px; margin-bottom: 25px; }
          .logo { font-size: 22px; font-weight: 900; color: #075B8A; letter-spacing: 1px; }
          .logo span { color: #18C3D0; }
          .subtitle { font-size: 13px; color: #708696; margin-top: 4px; }
          .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: bold; background: #EDFAFC; color: #075B8A; border: 1px solid #AEEBF0; }
          .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 25px 0; }
          .stat-card { border: 1px solid #DCEBED; border-radius: 12px; padding: 15px; background: #F4F8FA; }
          .stat-title { font-size: 11px; font-weight: bold; color: #708696; text-transform: uppercase; }
          .stat-val { font-size: 22px; font-weight: 900; color: #075B8A; margin-top: 5px; }
          table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 12px; }
          th { background: #075B8A; color: white; text-align: left; padding: 10px; }
          td { padding: 9px 10px; border-bottom: 1px solid #DCEBED; }
          tr:nth-child(even) { background: #F4F8FA; }
          .footer { margin-top: 40px; font-size: 11px; color: #708696; border-top: 1px solid #DCEBED; padding-top: 10px; text-align: center; }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="logo">AEGIS <span>ALERT</span></div>
          <div class="subtitle">MULTI-HAZARD EARLY WARNING SYSTEM • SECURE COMMAND INTELLIGENCE</div>
          <div style="margin-top: 10px;">
            <span class="badge">LOCATION: ${payload.location.toUpperCase()}</span>
            <span class="badge">HAZARD: ${payload.hazard.toUpperCase()}</span>
            <span class="badge">DATE RANGE: ${payload.dateRange.toUpperCase()}</span>
          </div>
        </div>

        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-title">Peak Intensity</div>
            <div class="stat-val">${payload.stats.peakIntensity}</div>
          </div>
          <div class="stat-card">
            <div class="stat-title">Total Events</div>
            <div class="stat-val">${payload.stats.totalEvents}</div>
          </div>
          <div class="stat-card">
            <div class="stat-title">People Affected</div>
            <div class="stat-val">${payload.stats.peopleAffected}</div>
          </div>
          <div class="stat-card">
            <div class="stat-title">Risk Trend</div>
            <div class="stat-val">${payload.stats.trend}</div>
          </div>
        </div>

        <h3>Regional Impact Assessment</h3>
        <table>
          <thead>
            <tr>
              <th>Region / Jurisdiction</th>
              <th>Incident Count</th>
              <th>Estimated Affected Citizens</th>
              <th>Assigned Severity</th>
            </tr>
          </thead>
          <tbody>
            ${payload.regionalImpact
              .map(
                (r) => `
              <tr>
                <td><strong>${r.region}</strong></td>
                <td>${r.events} Events</td>
                <td>${r.affected.toLocaleString()}</td>
                <td><span style="color: ${r.severity === 'critical' ? '#E94B68' : '#F4C84A'}; font-weight: bold;">${r.severity.toUpperCase()}</span></td>
              </tr>
            `
              )
              .join('')}
          </tbody>
        </table>

        <div class="footer">
          Generated on ${payload.generatedAt} IST • AEGIS Alert Disaster Analytics Engine
        </div>
        <script>
          window.onload = function() { window.print(); }
        </script>
      </body>
      </html>
    `;

    printWindow.document.write(html);
    printWindow.document.close();
  }

  /**
   * Generates downloadable Word Document (.doc format)
   */
  public static exportToWord(payload: ExportDataPayload): void {
    const header = `<html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
    <head><title>AEGIS ALERT Analytics</title></head><body>`;
    const footer = `</body></html>`;
    const content = `
      <h2>AEGIS ALERT - HAZARD ANALYTICS REPORT</h2>
      <p><strong>Location:</strong> ${payload.location} | <strong>Hazard:</strong> ${payload.hazard} | <strong>Period:</strong> ${payload.dateRange}</p>
      <p><strong>Generated At:</strong> ${payload.generatedAt}</p>
      <hr/>
      <h3>Key Metrics:</h3>
      <ul>
        <li><strong>Peak Intensity:</strong> ${payload.stats.peakIntensity}</li>
        <li><strong>Total Events Recorded:</strong> ${payload.stats.totalEvents}</li>
        <li><strong>Estimated People Affected:</strong> ${payload.stats.peopleAffected}</li>
        <li><strong>Observed Trend:</strong> ${payload.stats.trend}</li>
      </ul>
      <h3>Regional Impact Summary:</h3>
      <table border="1" style="border-collapse: collapse; width: 100%;">
        <tr>
          <th>Region</th><th>Events</th><th>People Affected</th><th>Severity</th>
        </tr>
        ${payload.regionalImpact
          .map(
            (r) => `<tr>
              <td>${r.region}</td><td>${r.events}</td><td>${r.affected.toLocaleString()}</td><td>${r.severity}</td>
            </tr>`
          )
          .join('')}
      </table>
    `;

    const blob = new Blob([header + content + footer], { type: 'application/msword' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `AEGIS_Analytics_${payload.location.replace(/\s+/g, '_')}.doc`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}
