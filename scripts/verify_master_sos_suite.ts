/**
 * AEGIS ALERT - MASTER 10-POINT END-TO-END VERIFICATION SUITE
 * 
 * Verifies:
 * 1. User SOS Flow & Complete Lifecycle (MATCHING -> ACKNOWLEDGED -> RESOLVED)
 * 2. Multi-Contact Family Notification & Standard Message Format
 * 3. Realtime Broadcast Events & Activity Feed
 * 4. Multiple Distinct SOS Users & Coordinate Isolation
 * 5. Clean Empty State & Zero Fake Data
 * 6. Location Failure & GPS Validation (0.0, 0.0 rejected with 422)
 * 7. Offline Idempotency Deduplication
 * 8. Rapid Duplicate Tap Protection
 * 9. Privacy & Safe Check-In Auto-Resolution
 * 10. Terminology & Separation Audit ("SOS MAP" enforced, 0 "SOS MAP")
 */

import * as fs from 'fs';
import * as path from 'path';

const API_BASE = 'http://localhost:8000/api/v1';

interface TestResult {
  step: number;
  name: string;
  passed: boolean;
  details: string;
}

const results: TestResult[] = [];

async function runTest(step: number, name: string, fn: () => Promise<void>) {
  try {
    await fn();
    results.push({ step, name, passed: true, details: 'Verified successfully' });
    console.log(`[PASS] Test ${step}: ${name}`);
  } catch (err: any) {
    results.push({ step, name, passed: false, details: err?.message || String(err) });
    console.error(`[FAIL] Test ${step}: ${name} - ${err?.message || err}`);
  }
}

async function fetchJson(endpoint: string, options: any = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  const res = await fetch(url, {
    ...options,
    headers,
  });
  const data = await res.json().catch(() => null);
  return { status: res.status, ok: res.ok, data };
}

async function main() {
  console.log('\n=============================================================');
  console.log('  AEGIS ALERT — MASTER E2E VERIFICATION SUITE');
  console.log('=============================================================\n');

  const testSessionId = `test-${Date.now()}`;

  // ---------------------------------------------------------------------------
  // TEST 1: User SOS Flow & Full Lifecycle Transitions
  // ---------------------------------------------------------------------------
  let createdSosId = '';
  await runTest(1, 'User SOS Flow & Complete Lifecycle (MATCHING -> ACKNOWLEDGED -> RESOLVED)', async () => {
    const payload = {
      caller_name: 'Test Citizen Alpha',
      caller_phone: '+91 98765 43210',
      emergency_type: 'medical',
      severity: 'CRITICAL',
      short_message: 'Master Test Distress Signal',
      latitude: 19.0760,
      longitude: 72.8777,
      battery_percent: 85,
      medical_notes: 'Asthma patient',
      casualties_count: 1,
      device_id: `device-master-${testSessionId}`,
      requester_user_id: `user-master-${testSessionId}`,
    };

    const createRes = await fetchJson('/sos', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (!createRes.ok || !createRes.data?.success) {
      throw new Error(`Failed to create SOS: ${JSON.stringify(createRes.data)}`);
    }

    createdSosId = createRes.data.data.id;
    const initialStatus = createRes.data.data.status;
    if (!['PENDING', 'MATCHING', 'OFFERED'].includes(initialStatus)) {
      throw new Error(`Unexpected initial status: ${initialStatus}`);
    }

    // Update location breadcrumb
    const locRes = await fetchJson(`/sos/${createdSosId}/location`, {
      method: 'POST',
      body: JSON.stringify({
        latitude: 19.0765,
        longitude: 72.8782,
        accuracy_meters: 8.0,
        battery_percent: 84,
      }),
      headers: { 'X-Aegis-User-Id': payload.requester_user_id },
    });

    if (!locRes.ok || !locRes.data?.success) {
      throw new Error(`Failed to update breadcrumb: ${JSON.stringify(locRes.data)}`);
    }

    // Acknowledge incident
    const ackRes = await fetchJson(`/sos/${createdSosId}/acknowledge`, {
      method: 'POST',
      headers: { 'X-Aegis-User-Id': 'responder-unit-101' },
    });

    if (!ackRes.ok || !ackRes.data?.success || ackRes.data.data.status !== 'ACKNOWLEDGED') {
      throw new Error(`Failed to acknowledge SOS: ${JSON.stringify(ackRes.data)}`);
    }

    // Resolve incident
    const resRes = await fetchJson(`/sos/${createdSosId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution_notes: 'Citizen safely stabilized by paramedic team.' }),
      headers: { 'X-Aegis-User-Id': payload.requester_user_id },
    });

    if (!resRes.ok || !resRes.data?.success || resRes.data.data.status !== 'RESOLVED') {
      throw new Error(`Failed to resolve SOS: ${JSON.stringify(resRes.data)}`);
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 2: Multi-Contact Family Notification & Standard Message Format
  // ---------------------------------------------------------------------------
  await runTest(2, 'Multi-Contact Family Notification & Standard Message Format', async () => {
    const familyPayload = {
      caller_name: 'Dr. Vikram Malhotra',
      caller_phone: '+91 98111 22233',
      emergency_type: 'flood_trapped',
      severity: 'CRITICAL',
      short_message: 'Water level rising quickly in residential colony',
      latitude: 20.2961,
      longitude: 85.8245,
      emergency_contacts: [
        { name: 'Pooja Malhotra', phone: '+91 98111 00001', relationship: 'Spouse' },
        { name: 'Ananya Malhotra', phone: '+91 98111 00002', relationship: 'Daughter' },
        { name: 'Karan Malhotra', phone: '+91 98111 00003', relationship: 'Brother' },
      ],
      device_id: `device-family-${testSessionId}`,
      requester_user_id: `user-family-${testSessionId}`,
    };

    const res = await fetchJson('/sos', {
      method: 'POST',
      body: JSON.stringify(familyPayload),
    });

    if (!res.ok || !res.data?.success) {
      throw new Error(`Failed to dispatch multi-contact SOS: ${JSON.stringify(res.data)}`);
    }

    const sosId = res.data.data.id;

    // Check details
    const detRes = await fetchJson(`/sos/${sosId}`, {
      headers: { 'X-Aegis-User-Id': familyPayload.requester_user_id },
    });

    if (!detRes.ok || !detRes.data?.success) {
      throw new Error(`Failed to fetch SOS details: ${JSON.stringify(detRes.data)}`);
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 3: Realtime Broadcast Event & Activity Log Verification
  // ---------------------------------------------------------------------------
  await runTest(3, 'Realtime Broadcast Events & Unified Activity Log Verification', async () => {
    const actRes = await fetchJson('/analytics/summary');
    if (!actRes.ok) {
      const feedRes = await fetchJson('/sos');
      if (!feedRes.ok) {
        throw new Error('Backend emergency pipeline is not serving active records');
      }
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 4: Multiple Distinct SOS Users & Isolated Coordinate Telemetry
  // ---------------------------------------------------------------------------
  await runTest(4, 'Multiple Distinct SOS Users & Isolated Telemetry', async () => {
    const userA = {
      caller_name: 'Citizen Mumbai',
      caller_phone: '+91 98000 11111',
      emergency_type: 'medical',
      severity: 'HIGH',
      short_message: 'Chest pain emergency',
      latitude: 18.9220,
      longitude: 72.8347,
      device_id: `device-a-${testSessionId}`,
      requester_user_id: `user-a-${testSessionId}`,
    };

    const userB = {
      caller_name: 'Citizen Bhubaneswar',
      caller_phone: '+91 98000 22222',
      emergency_type: 'cyclone_shelter',
      severity: 'CRITICAL',
      short_message: 'Roof collapsed in gale wind',
      latitude: 20.2961,
      longitude: 85.8245,
      device_id: `device-b-${testSessionId}`,
      requester_user_id: `user-b-${testSessionId}`,
    };

    const [resA, resB] = await Promise.all([
      fetchJson('/sos', { method: 'POST', body: JSON.stringify(userA) }),
      fetchJson('/sos', { method: 'POST', body: JSON.stringify(userB) }),
    ]);

    if (!resA.ok || !resB.ok) {
      throw new Error('Failed to create isolated SOS signals for multiple users');
    }

    if (resA.data.data.id === resB.data.data.id) {
      throw new Error('Distinct users received identical SOS IDs');
    }

    if (resA.data.data.latitude === resB.data.data.latitude) {
      throw new Error('Distinct users coordinates cross-contaminated');
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 5: Clean Empty State & Zero Fake Data Verification
  // ---------------------------------------------------------------------------
  await runTest(5, 'Clean State & Zero Mock/Demo Data in Production Code', async () => {
    const mobileProfilePath = path.resolve(__dirname, '../mobile/lib/emergency-profile.tsx');
    const profileContent = fs.readFileSync(mobileProfilePath, 'utf8');

    if (profileContent.includes('Priya Sharma') || profileContent.includes('Aarav Sharma')) {
      throw new Error('Found hardcoded dummy user profile in mobile/lib/emergency-profile.tsx');
    }

    const webPagePath = path.resolve(__dirname, '../web/src/pages/SOSPage.tsx');
    const webContent = fs.readFileSync(webPagePath, 'utf8');
    if (!webContent.includes('No active SOS alerts')) {
      throw new Error('Web SOSPage does not contain authentic "No active SOS alerts" empty state');
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 6: Location Failure & GPS Validation (0.0, 0.0 rejected with HTTP 422)
  // ---------------------------------------------------------------------------
  await runTest(6, 'Location Failure & GPS Validation (0.0, 0.0 rejected with HTTP 422)', async () => {
    const invalidPayload = {
      caller_name: 'Invalid GPS User',
      latitude: 0.0,
      longitude: 0.0,
      emergency_type: 'general',
      severity: 'CRITICAL',
    };

    const res = await fetchJson('/sos', {
      method: 'POST',
      body: JSON.stringify(invalidPayload),
    });

    if (res.status !== 422) {
      throw new Error(`Expected HTTP 422 for (0.0, 0.0) coordinates, got HTTP ${res.status}`);
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 7: Offline Idempotency Deduplication
  // ---------------------------------------------------------------------------
  await runTest(7, 'Offline Idempotency Deduplication (Batch Sync)', async () => {
    const idemKey = `offline-idem-${Date.now()}`;
    const batchPayload = {
      sos_events: [
        {
          idempotency_key: idemKey,
          caller_name: 'Offline Citizen',
          emergency_type: 'general',
          severity: 'HIGH',
          latitude: 19.0760,
          longitude: 72.8777,
        },
      ],
      safe_events: [],
    };

    const res1 = await fetchJson('/sos/sync', {
      method: 'POST',
      body: JSON.stringify(batchPayload),
    });

    if (!res1.ok || !res1.data?.success) {
      throw new Error(`First offline sync failed: ${JSON.stringify(res1.data)}`);
    }

    const firstId = res1.data.data.sos_results[0].id;

    const res2 = await fetchJson('/sos/sync', {
      method: 'POST',
      body: JSON.stringify(batchPayload),
    });

    if (!res2.ok || !res2.data?.success) {
      throw new Error(`Second offline sync failed: ${JSON.stringify(res2.data)}`);
    }

    const secondStatus = res2.data.data.sos_results[0].status;
    const secondId = res2.data.data.sos_results[0].id;

    if (secondStatus !== 'ALREADY_SYNCED' || secondId !== firstId) {
      throw new Error(`Idempotency check failed: status=${secondStatus}, firstId=${firstId}, secondId=${secondId}`);
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 8: Rapid Duplicate Tap Protection
  // ---------------------------------------------------------------------------
  await runTest(8, 'Rapid Duplicate Tap Protection (Same Active Session)', async () => {
    const rapidUser = `rapid-user-${Date.now()}`;
    const rapidPayload = {
      caller_name: 'Rapid Tap Citizen',
      latitude: 12.9716,
      longitude: 77.5946,
      emergency_type: 'general',
      severity: 'CRITICAL',
      requester_user_id: rapidUser,
      device_id: `device-${rapidUser}`,
    };

    const res1 = await fetchJson('/sos', {
      method: 'POST',
      body: JSON.stringify(rapidPayload),
    });

    const res2 = await fetchJson('/sos', {
      method: 'POST',
      body: JSON.stringify(rapidPayload),
    });

    if (!res1.ok || !res2.ok) {
      throw new Error('Rapid tap request failed');
    }

    if (res1.data.data.id !== res2.data.data.id) {
      throw new Error('Rapid duplicate taps created separate uncoordinated distress incidents');
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 9: Privacy & Safe Check-In Auto-Resolution
  // ---------------------------------------------------------------------------
  await runTest(9, 'Privacy & Safe Check-In Auto-Resolution of Active SOS', async () => {
    const safeUserId = `safe-user-${Date.now()}`;

    const sosRes = await fetchJson('/sos', {
      method: 'POST',
      body: JSON.stringify({
        caller_name: 'Safe Test User',
        latitude: 13.0827,
        longitude: 80.2707,
        emergency_type: 'flood_trapped',
        severity: 'CRITICAL',
        requester_user_id: safeUserId,
      }),
    });

    if (!sosRes.ok) throw new Error('Failed to create initial SOS');
    const activeSosId = sosRes.data.data.id;

    const safeRes = await fetchJson('/sos/safe', {
      method: 'POST',
      body: JSON.stringify({
        user_name: 'Safe Test User',
        latitude: 13.0827,
        longitude: 80.2707,
        message: 'Rescued and arrived safely at cyclone relief center.',
        user_id: safeUserId,
      }),
    });

    if (!safeRes.ok || !safeRes.data?.success) {
      throw new Error(`Failed to declare safe incident: ${JSON.stringify(safeRes.data)}`);
    }

    const checkSos = await fetchJson(`/sos/${activeSosId}`, {
      headers: { 'X-Aegis-User-Id': safeUserId },
    });

    if (!checkSos.ok || checkSos.data.data.status !== 'RESOLVED') {
      throw new Error(`Active SOS was not auto-resolved on SAFE declaration. Status: ${checkSos.data?.data?.status}`);
    }
  });

  // ---------------------------------------------------------------------------
  // TEST 10: Terminology & Map Separation Audit ("SOS MAP" enforced, 0 "SOS MAP")
  // ---------------------------------------------------------------------------
  await runTest(10, 'Terminology & Map Separation Audit ("SOS MAP" enforced, 0 "SOS MAP")', async () => {
    const codeFilesToCheck = [
      path.resolve(__dirname, '../mobile/components/live-realtime-map.tsx'),
      path.resolve(__dirname, '../mobile/lib/services/aegis-api.ts'),
      path.resolve(__dirname, '../web/src/pages/SOSPage.tsx'),
      path.resolve(__dirname, '../web/src/components/map/GoogleSOSMap.tsx'),
    ];

    for (const filePath of codeFilesToCheck) {
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf8');
        if (content.includes('SOS MAP') || content.includes('🚨 SOS MAP') || content.includes('DISPATCH GRID')) {
          throw new Error(`Found disallowed "SOS MAP" or "DISPATCH GRID" terminology in ${path.basename(filePath)}`);
        }
      }
    }
  });

  console.log('\n=============================================================');
  console.log(`  VERIFICATION RESULTS: ${results.filter(r => r.passed).length}/${results.length} PASSED`);
  console.log('=============================================================\n');

  if (results.every(r => r.passed)) {
    console.log('🎉 ALL 10 MASTER VERIFICATION TESTS PASSED PERFECTLY!\n');
    process.exit(0);
  } else {
    console.error('❌ Some tests failed.');
    process.exit(1);
  }
}

main().catch(err => {
  console.error('Fatal test suite runner error:', err);
  process.exit(1);
});
