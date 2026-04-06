const API = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || 'http://localhost:8000';
const STORAGE_KEYS = {
  token: 'qc_session_token',
  username: 'qc_username',
  role: 'qc_role',
  tlName: 'qc_tl_name',
};

let adminState = {
  users: [],
  files: [],
};

function $(id) {
  return document.getElementById(id);
}

function getToken() {
  return localStorage.getItem(STORAGE_KEYS.token) || '';
}

function getRole() {
  return localStorage.getItem(STORAGE_KEYS.role) || '';
}

function clearAuth() {
  Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
}

function authHeaders(extra = {}) {
  return {
    ...extra,
    'X-Session-Token': getToken(),
  };
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      message = data?.detail || message;
    } catch (_) {
      // ignore
    }
    throw new Error(message);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function rolePill(role) {
  const cssClass = role === 'admin' ? 'admin' : 'tl';
  return `<span class="role-pill ${cssClass}">${escapeHtml(role)}</span>`;
}

function fmtNum(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num.toLocaleString('id-ID') : '-';
}

function formatDate(value) {
  if (!value) return '-';
  return new Date(value).toLocaleString('id-ID');
}

async function loadDashboard() {
  const stats = await api('/admin/dashboard');
  $('stat-total-users').textContent = stats.total_users;
  $('stat-total-tl').textContent = stats.total_tl;
  $('stat-total-admin-files').textContent = stats.total_files;
  $('stat-total-rows').textContent = stats.total_rows;
}

async function loadUsers() {
  adminState.users = await api('/admin/users');
  $('users-tbody').innerHTML = adminState.users.map((user) => `
    <tr>
      <td>
        <strong>${escapeHtml(user.username)}</strong><br />
        <span class="admin-muted">dibuat: ${formatDate(user.created_at)}</span>
      </td>
      <td>${rolePill(user.role)}</td>
      <td>${escapeHtml(user.tl_name || '-')}</td>
      <td>
        <div class="admin-actions">
          <button class="btn-admin-secondary" data-action="edit-user" data-id="${user.id}">Edit</button>
          ${user.username === 'Admin' ? '' : `<button class="btn-admin-danger" data-action="delete-user" data-id="${user.id}">Hapus</button>`}
        </div>
      </td>
    </tr>
  `).join('');
}

async function loadFiles() {
  adminState.files = await api('/admin/files');
  $('files-tbody').innerHTML = adminState.files.map((file) => `
    <tr>
      <td>
        <strong>${escapeHtml(file.file_name)}</strong><br />
        <span class="admin-muted">${fmtNum(file.row_count)} baris • ${fmtNum(file.tl_count)} TL • ${fmtNum(file.agent_count)} agent</span>
      </td>
      <td>${escapeHtml(file.uploaded_by_username || '-')}</td>
      <td>${escapeHtml(file.start_date || '-')} s/d ${escapeHtml(file.end_date || '-')}</td>
      <td>
        <div class="admin-actions">
          <button class="btn-admin-secondary" data-action="rename-file" data-id="${file.id}">Rename</button>
          <button class="btn-admin-danger" data-action="delete-file" data-id="${file.id}">Hapus</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function resetUserForm() {
  $('user-id').value = '';
  $('user-username').value = '';
  $('user-password').value = '';
  $('user-role').value = 'tl';
  $('user-tl-name').value = '';
}

function fillUserForm(user) {
  $('user-id').value = user.id;
  $('user-username').value = user.username || '';
  $('user-password').value = '';
  $('user-role').value = user.role || 'tl';
  $('user-tl-name').value = user.tl_name || '';
}

async function refreshAll() {
  await Promise.all([loadDashboard(), loadUsers(), loadFiles()]);
}

$('users-tbody').addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const userId = Number(button.dataset.id);
  const action = button.dataset.action;
  const user = adminState.users.find((item) => item.id === userId);
  if (!user) return;

  if (action === 'edit-user') {
    fillUserForm(user);
    return;
  }

  if (action === 'delete-user') {
    if (!confirm(`Hapus user ${user.username}?`)) return;
    await api(`/admin/users/${userId}`, { method: 'DELETE' });
    await refreshAll();
  }
});

$('files-tbody').addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const fileId = Number(button.dataset.id);
  const action = button.dataset.action;
  const file = adminState.files.find((item) => item.id === fileId);
  if (!file) return;

  if (action === 'rename-file') {
    const next = prompt('Nama file baru:', file.file_name);
    if (!next || !next.trim()) return;
    await api(`/admin/files/${fileId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_name: next.trim() }),
    });
    await refreshAll();
    return;
  }

  if (action === 'delete-file') {
    if (!confirm(`Hapus file ${file.file_name}?`)) return;
    await api(`/admin/files/${fileId}`, { method: 'DELETE' });
    await refreshAll();
  }
});

$('reset-user-form-btn').addEventListener('click', resetUserForm);

$('user-role').addEventListener('change', () => {
  const isTL = $('user-role').value === 'tl';
  $('user-tl-name').disabled = !isTL;
  if (!isTL) {
    $('user-tl-name').value = '';
  }
});

$('user-form').addEventListener('submit', async (event) => {
  event.preventDefault();

  const userId = $('user-id').value;
  const payload = {
    username: $('user-username').value.trim(),
    password: $('user-password').value.trim(),
    role: $('user-role').value,
    tl_name: $('user-tl-name').value.trim() || null,
  };

  if (userId) {
    if (!payload.password) delete payload.password;
    await api(`/admin/users/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } else {
    await api('/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  }

  resetUserForm();
  await refreshAll();
});

$('file-form').addEventListener('submit', async (event) => {
  event.preventDefault();

  const fileInput = $('file-upload');
  const file = fileInput.files[0];
  if (!file) {
    alert('Pilih file dulu.');
    return;
  }

  const displayName = $('file-display-name').value.trim();
  if (!displayName) {
    alert('Nama file wajib diisi.');
    return;
  }

  const formData = new FormData();
  formData.append('file_name', displayName);
  formData.append('file', file);

  await api('/admin/files', {
    method: 'POST',
    body: formData,
  });

  $('file-display-name').value = '';
  fileInput.value = '';
  await refreshAll();
});

$('admin-logout-btn').addEventListener('click', async () => {
  try {
    await api('/logout', { method: 'POST' });
  } catch (_) {
    // ignore
  }
  clearAuth();
  window.location.href = 'index.html';
});

$('go-user-page-btn').addEventListener('click', () => {
  window.location.href = 'index.html';
});

window.addEventListener('load', async () => {
  if (!getToken() || getRole() !== 'admin') {
    window.location.href = 'index.html';
    return;
  }

  try {
    await refreshAll();
  } catch (error) {
    alert(error.message || 'Gagal memuat halaman admin.');
    if (/401|403|token|sesi|kedaluwarsa/i.test(error.message || '')) {
      clearAuth();
      window.location.href = 'index.html';
    }
  }
});
