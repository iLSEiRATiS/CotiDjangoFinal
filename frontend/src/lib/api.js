// src/lib/api.js
// Cliente API único + shim apiFetch

// Lee variable para Vite o CRA, con fallback correcto a 5000 en dev.
const RAW_ENV =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
  ((typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_URL) || '') ||
  '';

const NODE_ENV = (typeof process !== 'undefined' && process.env && process.env.NODE_ENV) || '';

const RAW_BASE =
  (RAW_ENV || (NODE_ENV === 'production'
    ? 'https://final-ecommerce-b.onrender.com'
    : 'http://localhost:8000')).trim(); // backend local va en 8000

function normalizeBase(url) {
  let base = String(url || '').trim();
  base = base.replace(/\/+$/, '');     // quita / final
  base = base.replace(/\/api$/i, '');  // quita /api si lo pusieron en la env
  return base;
}

export const API_BASE = normalizeBase(RAW_BASE);

async function http(path, { method = 'GET', body, token, headers: extra = {} } = {}) {
  const headers = { Accept: 'application/json', ...extra };
  const isFormData = (typeof FormData !== 'undefined') && (body instanceof FormData);
  if (body != null && !isFormData && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body != null ? (isFormData ? body : JSON.stringify(body)) : undefined,
    credentials: 'omit'
  });

  const ct = res.headers.get('content-type') || '';
  const payload = ct.includes('application/json')
    ? await res.json().catch(() => ({}))
    : await res.text().catch(() => '');

  if (!res.ok) {
    const msg = (payload && (payload.error || payload.message)) || `${res.status} ${res.statusText}`;
    const err = new Error(msg);
    err.status = res.status;
    err.payload = payload;
    throw err;
  }
  return payload;
}

function qs(params = {}) {
  const entries = Object.entries(params).filter(([_, v]) => v !== undefined && v !== null && v !== '');
  if (!entries.length) return '';
  const sp = new URLSearchParams(entries);
  const s = sp.toString();
  return s ? `?${s}` : '';
}

export const api = {
  auth: {
    register: (data) => http('/api/auth/register', { method: 'POST', body: data }),
    login:    (data) => http('/api/auth/login',    { method: 'POST', body: data }),
    me:       (token) => http('/api/auth/me', { token })
  },
  products: {
    list: (params) => http(`/api/products${qs(params)}`),
    get:  (id)     => http(`/api/products/${encodeURIComponent(id)}`),
    categories: () => http('/api/categories'),
    offers: () => http('/api/offers')
  },
  account: {
    profile: (token)            => http('/api/account/profile', { token }),
    updateProfile: (token, d)   => http('/api/account/profile', { method: 'PATCH', token, body: d }),
    changePassword: (token, d)  => http('/api/account/password', { method: 'PATCH', token, body: d })
  },
  orders: {
    create: (token, data) => http('/api/orders', { method: 'POST', token, body: data }),
    mine:   (token)       => http('/api/orders/mine', { token }),
    get:    (token, id)   => http(`/api/orders/${encodeURIComponent(id)}`, { token }),
    pay:    (token, id)   => http(`/api/orders/${encodeURIComponent(id)}/pay`, { method: 'PATCH', token })
  },
  admin: {
    listUsers:     (token, params)      => http(`/api/admin/users${qs(params)}`, { token }),
    createUser:    (token, data)        => http('/api/admin/users', { method: 'POST', token, body: data }),
    updateUser:    (token, id, d)       => http(`/api/admin/users/${encodeURIComponent(id)}`, { method: 'PATCH', token, body: d }),
    deleteUser:    (token, userId)      => http(`/api/admin/users/${encodeURIComponent(userId)}`, { method: 'DELETE', token }),
    listOrders:    (token, params)      => http(`/api/admin/orders${qs(params)}`, { token }),
    updateOrder:   (token, id, d)       => http(`/api/admin/orders/${encodeURIComponent(id)}`, { method: 'PATCH', token, body: d }),
    listProducts:  (token, params)      => http(`/api/admin/products${qs(params)}`, { token }),
    createProduct: (token, d)           => http('/api/admin/products', { method: 'POST', token, body: d }), // soporta JSON o FormData
    updateProduct: (token, id, d)       => http(`/api/admin/products/${encodeURIComponent(id)}`, { method: 'PATCH', token, body: d }),
    deleteProduct: (token, id)          => http(`/api/admin/products/${encodeURIComponent(id)}`, { method: 'DELETE', token }),
    uploadImage:   (token, formData)    => http('/api/admin/upload-image', { method: 'POST', token, body: formData }),
    overview:      (token)              => http('/api/admin/overview', { token }),
    listOffers:    (token)              => http('/api/admin/offers', { token }),
    createOffer:   (token, d)           => http('/api/admin/offers', { method: 'POST', token, body: d }),
    updateOffer:   (token, id, d)       => http(`/api/admin/offers/${encodeURIComponent(id)}`, { method: 'PATCH', token, body: d }),
    deleteOffer:   (token, id)          => http(`/api/admin/offers/${encodeURIComponent(id)}`, { method: 'DELETE', token }),
    importProductsXlsx: (token, formData) => http('/api/admin/products/import-xlsx', { method: 'POST', token, body: formData })
  }
};

// compat legado
export { http as apiFetch };
export default api;
