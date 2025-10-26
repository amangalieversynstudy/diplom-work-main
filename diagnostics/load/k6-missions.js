import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  vus: __ENV.VUS ? parseInt(__ENV.VUS) : 5,
  duration: __ENV.DURATION || '30s',
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const USERNAME = __ENV.API_USERNAME || 'testuser';
const PASSWORD = __ENV.API_PASSWORD || 'testpass';

function login() {
  const res = http.post(`${BASE_URL}/api/auth/login/`, JSON.stringify({ username: USERNAME, password: PASSWORD }), {
    headers: { 'Content-Type': 'application/json' },
  });
  if (res.status === 200 && res.json('access')) {
    return `Bearer ${res.json('access')}`;
  }
  return '';
}

export default function () {
  const token = login();
  const headers = token ? { Authorization: token } : {};

  // Read-heavy: missions list
  const list = http.get(`${BASE_URL}/api/missions/`, { headers });
  check(list, { 'missions list 200': (r) => r.status === 200 });

  // Optionally pick a mission id and call complete (write)
  const missions = list.json();
  if (Array.isArray(missions) && missions.length > 0) {
    const id = missions[0].id;
    const complete = http.post(`${BASE_URL}/api/missions/${id}/complete/`, JSON.stringify({}), {
      headers: { ...headers, 'Content-Type': 'application/json' },
    });
    check(complete, { 'complete 200': (r) => r.status === 200 || r.status === 400 || r.status === 403 });
  }

  sleep(1);
}
