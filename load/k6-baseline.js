// Baseline load test: the read/write path a real user exercises, without the
// LLM (which is a third-party dependency and would measure their latency, not
// ours).
//
//   make load-test
//   BASE_URL=https://staging.example.com make load-test
//
// The thresholds are the SLOs from docs/SLO.md, so a failing run means the
// build would burn error budget in production — not that "it felt slow".

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost';

const noteCreateDuration = new Trend('note_create_duration', true);
const noteListDuration = new Trend('note_list_duration', true);
const businessErrors = new Rate('business_errors');

export const options = {
  scenarios: {
    // Ramp to a steady plateau and hold it: a spike alone tells you nothing
    // about pool exhaustion or a slow memory leak.
    baseline: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '2m', target: 10 },
        { duration: '30s', target: 25 },
        { duration: '1m', target: 25 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    // Availability SLO: under 0.5% failed requests.
    http_req_failed: ['rate<0.005'],
    // Latency SLO: 99% of non-AI requests under 250 ms.
    'http_req_duration{expected_response:true}': ['p(99)<250'],
    note_create_duration: ['p(95)<300'],
    note_list_duration: ['p(95)<250'],
    business_errors: ['rate<0.01'],
  },
};

function registerAndLogin() {
  const suffix = `${__VU}-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const credentials = {
    email: `loadtest+${suffix}@example.com`,
    password: 'LoadTest123!pass',
    nickname: `load${__VU}`,
  };

  http.post(`${BASE_URL}/api/auth/register`, JSON.stringify(credentials), {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'register' },
  });

  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ email: credentials.email, password: credentials.password }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'login' } },
  );

  if (res.status !== 200) {
    businessErrors.add(1);
    return null;
  }

  const token = res.json('access_token');
  businessErrors.add(!token);
  return token;
}

export default function () {
  const token = registerAndLogin();
  if (!token) {
    sleep(1);
    return;
  }

  const authHeaders = {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  };

  group('notes', () => {
    const create = http.post(
      `${BASE_URL}/api/notes`,
      JSON.stringify({
        title: `Load test note ${Date.now()}`,
        content: '# Heading\n\nSome markdown body used to exercise the write path.',
      }),
      { ...authHeaders, tags: { name: 'create_note' } },
    );
    noteCreateDuration.add(create.timings.duration);
    const created = check(create, { 'note created': (r) => r.status === 201 || r.status === 200 });
    businessErrors.add(!created);

    const list = http.get(`${BASE_URL}/api/notes?limit=20`, {
      ...authHeaders,
      tags: { name: 'list_notes' },
    });
    noteListDuration.add(list.timings.duration);
    const listed = check(list, { 'notes listed': (r) => r.status === 200 });
    businessErrors.add(!listed);

    const tags = http.get(`${BASE_URL}/api/tags`, { ...authHeaders, tags: { name: 'list_tags' } });
    check(tags, { 'tags listed': (r) => r.status === 200 });
  });

  // Think time — without it this measures how fast k6 can spin, not how the
  // service behaves under a realistic arrival pattern.
  sleep(Math.random() * 2 + 1);
}
