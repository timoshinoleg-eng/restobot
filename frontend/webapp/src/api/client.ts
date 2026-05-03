import type {
  MenuCategory,
  MenuItem,
  OrderCreatePayload,
  OrderResponse,
  PaymentSession,
  WidgetSession,
} from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('rb_access_token');
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (res.status === 401) {
    // Token invalid or expired — clear session and force re-auth
    localStorage.removeItem('rb_access_token');
    Object.keys(localStorage).forEach((key) => {
      if (key.startsWith('rb_session_')) localStorage.removeItem(key);
    });
    window.location.reload();
    throw new Error('Session expired. Please sign in again.');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function createWidgetSession(
  tenant: string,
  externalId: string,
  name: string,
  phone: string | null,
  email?: string | null
): Promise<WidgetSession> {
  return fetchJson<WidgetSession>(`/widget/${tenant}/session`, {
    method: 'POST',
    body: JSON.stringify({ external_id: externalId, name, phone, email }),
  });
}

export async function fetchMenu(tenant: string): Promise<MenuItem[]> {
  return fetchJson<MenuItem[]>(`/widget/${tenant}/menu`);
}

export async function fetchCategories(tenant: string): Promise<MenuCategory[]> {
  return fetchJson<MenuCategory[]>(`/widget/${tenant}/menu/categories`);
}

export async function createOrder(tenant: string, payload: OrderCreatePayload): Promise<OrderResponse> {
  return fetchJson<OrderResponse>(`/widget/${tenant}/orders`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchOrder(tenant: string, orderId: number): Promise<OrderResponse> {
  return fetchJson<OrderResponse>(`/widget/${tenant}/orders/${orderId}`);
}

export async function createOrderPayment(tenant: string, orderId: number): Promise<PaymentSession> {
  return fetchJson<PaymentSession>(`/api/v1/${tenant}/orders/${orderId}/payment`, {
    method: 'POST',
  });
}
