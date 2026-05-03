// Auth utilities (cookie-based)
(function() {
  function isLoggedIn() {
    return !!localStorage.getItem('tenant_id');
  }

  async function logout() {
    try {
      await fetch(API.getTenant() ? `/admin/${API.getTenant()}/auth/logout` : '/admin/demo/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
      });
    } catch {}
    localStorage.removeItem('tenant_id');
    location.href = '/admin/login.html';
  }

  function requireAuth() {
    if (!isLoggedIn()) {
      location.href = '/admin/login.html';
    }
  }

  async function checkSession() {
    try {
      const tenant = API.getTenant();
      const res = await fetch(`/admin/${tenant}/auth/me`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('Unauthorized');
      return await res.json();
    } catch {
      localStorage.removeItem('tenant_id');
      location.href = '/admin/login.html';
      return null;
    }
  }

  function initAuth() {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', logout);
  }

  window.Auth = { isLoggedIn, logout, requireAuth, checkSession, initAuth };
})();
