// API client for RestoBot Admin (cookie-based auth)
(function() {
  const ADMIN_API_BASE = '/admin';

  function getTenant() {
    const hash = location.hash.replace('#', '');
    if (hash) return hash;
    const stored = localStorage.getItem('tenant_id');
    if (stored) return stored;
    location.href = '/admin/login.html';
    throw new Error('Tenant not set');
  }

  async function api(path, opts = {}) {
    const tenant = getTenant();
    const url = `${ADMIN_API_BASE}/${tenant}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      ...opts.headers,
    };
    const res = await fetch(url, {
      ...opts,
      headers,
      credentials: 'same-origin',
    });
    if (res.status === 401) {
      localStorage.removeItem('tenant_id');
      location.href = '/admin/login.html';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        msg = data.detail || data.message || msg;
      } catch {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  window.API = {
    get: (path) => api(path, { method: 'GET' }),
    post: (path, body) => api(path, { method: 'POST', body: JSON.stringify(body) }),
    put: (path, body) => api(path, { method: 'PUT', body: JSON.stringify(body) }),
    patch: (path, body) => api(path, { method: 'PATCH', body: JSON.stringify(body) }),
    del: (path) => api(path, { method: 'DELETE' }),
    getTenant,
  };
})();
