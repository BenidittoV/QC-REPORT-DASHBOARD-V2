/* =============================================
   QC AUDIO DASHBOARD — FRONTEND LOGIC
   ============================================= */

const API = (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || 'http://localhost:8000';

// =====================
// STATE
// =====================
let state = {
  username: null,
  role: null,
  tlName: '',
  sessionToken: null,
  lockedTL: '',
  activeFileId: null,
  activeFileName: '',
  availableFiles: [],
  mode: 'TL',            // 'Agent' | 'TL'
  selectedTL: '',
  selectedAgent: '',
  selectedMonth: null,
  metaData: null,        // {tl_list, agents_by_tl}
  dashData: null,        // last /process response
  charts: {},            // Chart.js instances keyed by id
};

// =====================
// UTILS
// =====================
const $ = (id) => document.getElementById(id);
const show = (el) => { if (el) el.classList.remove('hidden'); };
const hide = (el) => { if (el) el.classList.add('hidden'); };

const STORAGE_KEYS = {
  token: 'qc_session_token',
  username: 'qc_username',
  role: 'qc_role',
  tlName: 'qc_tl_name',
  availableFiles: 'qc_available_files',
};

function saveAuth(auth) {
  localStorage.setItem(STORAGE_KEYS.token, auth.session_token || '');
  localStorage.setItem(STORAGE_KEYS.username, auth.username || '');
  localStorage.setItem(STORAGE_KEYS.role, auth.role || '');
  localStorage.setItem(STORAGE_KEYS.tlName, auth.tl_name || '');
  localStorage.setItem(STORAGE_KEYS.availableFiles, JSON.stringify(auth.available_files || []));
}

function clearAuth() {
  Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
}

function getStoredAuth() {
  let availableFiles = [];
  try {
    availableFiles = JSON.parse(localStorage.getItem(STORAGE_KEYS.availableFiles) || '[]');
  } catch (_) {
    availableFiles = [];
  }
  return {
    sessionToken: localStorage.getItem(STORAGE_KEYS.token) || '',
    username: localStorage.getItem(STORAGE_KEYS.username) || '',
    role: localStorage.getItem(STORAGE_KEYS.role) || '',
    tlName: localStorage.getItem(STORAGE_KEYS.tlName) || '',
    availableFiles,
  };
}

function setEmptyStateMessage(html) {
  const box = $('empty-state');
  if (!box) return;
  box.innerHTML = html;
  show(box);
}


const showLoader = (msg = 'Memuat data...', options = {}) => {
  const overlay = $('loader-overlay');
  if (!overlay) return;
  overlay.classList.remove('hidden');
  startLoaderAnimation(msg, options);
};

const hideLoader = (options = {}) => {
  const overlay = $('loader-overlay');
  if (!overlay || overlay.classList.contains('hidden')) return;
  finishLoaderAnimation(options);
};

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (state.sessionToken) {
    headers['X-Session-Token'] = state.sessionToken;
  }
  if (state.activeFileId) {
    headers['X-Active-File-Id'] = String(state.activeFileId);
  }
  return headers;
}

function fmtNum(n) {
  if (n == null || Number.isNaN(Number(n))) return '-';
  return Number(n).toLocaleString('id-ID', { maximumFractionDigits: 2 });
}

function formatDurationMmSs(value) {
  if (value == null || Number.isNaN(Number(value))) return '-';
  const totalSeconds = Math.max(0, Math.round(Number(value)));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function numericOrNull(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function fmtFraction(hit, total) {
  const hitText = fmtNum(hit);
  const totalNum = Number(total);
  if (!Number.isFinite(totalNum) || totalNum < 0) return hitText;
  return `${hitText} / ${fmtNum(totalNum)}`;
}

function minatTooltipLine(row, label = 'Jumlah Minat') {
  const minat = row?.minat ?? row?.wm ?? row?.jumlah_minat ?? null;
  const total = row?.rekaman ?? row?.jumlah_rekaman ?? null;
  if (minat == null) return `${label}: -`;
  return `${label}: ${fmtFraction(minat, total)}`;
}

function gradeHtml(g) {
  if (!g || g === '-') return `<span class="grade-badge">-</span>`;
  return `<span class="grade-badge grade-${g}">${g}</span>`;
}

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function destroyChart(id) {
  if (state.charts[id]) {
    state.charts[id].destroy();
    delete state.charts[id];
  }
}

function makeChart(id, config) {
  destroyChart(id);
  const ctx = $(id);
  if (!ctx) return;
  state.charts[id] = new Chart(ctx, config);
  scheduleChartResize(0);
}

let _chartResizeTimer = null;

function resizeAllCharts() {
  Object.values(state.charts || {}).forEach((chart) => {
    if (!chart) return;
    try {
      chart.resize();
      chart.update('none');
    } catch (_) {
      // ignore resize errors from stale canvases
    }
  });
}

function scheduleChartResize(delay = 120) {
  if (_chartResizeTimer) {
    clearTimeout(_chartResizeTimer);
  }
  _chartResizeTimer = setTimeout(() => {
    requestAnimationFrame(() => {
      resizeAllCharts();
    });
  }, delay);
}

function parseErrorDetail(detail) {
  if (detail == null) return 'Terjadi kesalahan di server.';

  if (typeof detail === 'string') return detail;

  if (Array.isArray(detail)) {
    return detail.map((item) => parseErrorDetail(item)).join(' | ');
  }

  if (typeof detail === 'object') {
    const parts = [];

    if (detail.msg) parts.push(detail.msg);
    if (detail.message) parts.push(detail.message);
    if (detail.detail && typeof detail.detail === 'string') parts.push(detail.detail);

    if (Array.isArray(detail.loc)) {
      parts.push(`Field: ${detail.loc.join('.')}`);
    }

    if (detail.input !== undefined && typeof detail.input !== 'object') {
      parts.push(`Input: ${String(detail.input)}`);
    }

    if (parts.length > 0) {
      return parts.join(' | ');
    }

    try {
      return JSON.stringify(detail);
    } catch (_) {
      return 'Terjadi kesalahan validasi payload.';
    }
  }

  return String(detail);
}

function resetDashboardView() {
  state.dashData = null;

  hide($('dashboard'));
  hide($('empty-state'));

  $('topbar-badges').innerHTML = '';
  $('interest-strip').innerHTML = '';
  $('month-bar').innerHTML = '';

  hide($('month-bar-wrap'));
  hide($('agent-comparison-section'));
  hide($('agent-interest-section'));
  hide($('tab-weekly-btn'));
  hide($('period-split-section'));
  hide($('routine-section'));
  hide($('nonroutine-section'));

  $('result-thead-row').innerHTML = '';
  $('result-tbody').innerHTML = '';
  $('worst-agent-tbody').innerHTML = '';
  $('best-agent-tbody').innerHTML = '';
  $('agent-interest-tbody').innerHTML = '';
  $('pt1-head').innerHTML = '';
  $('pt1-body').innerHTML = '';
  $('pt2-head').innerHTML = '';
  $('pt2-body').innerHTML = '';
  $('rutin-tbody').innerHTML = '';
  $('tidak-rutin-tbody').innerHTML = '';
  $('hourly-overall-legend').innerHTML = '';
  $('call-mix-legend').innerHTML = '';

  [
    'chart-weekly-overall',
    'chart-weekly-wm',
    'chart-daily-rate',
    'chart-daily-bar',
    'chart-period-comparison',
    'chart-rutin',
    'chart-tidak-rutin',
    'chart-hourly-overall',
    'chart-hourly-volume',
    'chart-hourly-interest',
    'chart-hourly-not-interest',
    'chart-call-mix',
    'chart-hourly-duration',
  ].forEach(destroyChart);

  switchTab('overview');
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch (_) {
    return null;
  }
}

async function readErrorResponse(res) {
  const text = await res.text();
  const parsed = safeJsonParse(text);

  if (parsed && parsed.detail !== undefined) {
    return parseErrorDetail(parsed.detail);
  }

  if (parsed) {
    return parseErrorDetail(parsed);
  }

  return text || `HTTP ${res.status}`;
}

// =====================
// AUTH
// =====================
$('login-btn')?.addEventListener('click', doLogin);

['login-user', 'login-pass'].forEach(id => {
  const el = $(id);
  if (!el) return;
  el.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doLogin();
  });
});

async function doLogin() {
  const username = $('login-user')?.value.trim() || '';
  const password = $('login-pass')?.value || '';
  if ($('login-error')) $('login-error').textContent = '';

  if (!username || !password) {
    if ($('login-error')) $('login-error').textContent = 'Username dan password harus diisi.';
    return;
  }

  showLoader('Memverifikasi...');
  try {
    const res = await fetch(`${API}/login`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const msg = await readErrorResponse(res);
      if ($('login-error')) $('login-error').textContent = msg || 'Login gagal.';
      hideLoader({ immediate: true });
      return;
    }

    const loginData = await res.json();
    saveAuth(loginData);

    if (loginData?.role === 'admin') {
      hideLoader({ message: 'Masuk sebagai admin...' });
      window.location.href = 'admin.html';
      return;
    }

    state.username = loginData?.username || username;
    state.role = loginData?.role || 'tl';
    state.tlName = loginData?.tl_name || '';
    state.sessionToken = loginData?.session_token || null;
    state.lockedTL = state.tlName || '';
    state.selectedTL = state.lockedTL || '';
    state.mode = 'TL';
    state.activeFileId = null;
    state.activeFileName = '';
    state.availableFiles = Array.isArray(loginData?.available_files) ? loginData.available_files : [];
    resetDashboardView();
    populateAvailableFiles();

    hide($('login-page'));
    show($('app'));

    setEmptyStateMessage(`
      <div class="empty-state-card">
        <h3>Pilih data dulu</h3>
        <p>Setelah login, dashboard belum mengambil data apa pun. Silakan pilih dataset pada dropdown di sidebar untuk mulai memuat dashboard.</p>
      </div>
    `);

    hideLoader();
  } catch (e) {
    if ($('login-error')) {
      $('login-error').textContent = 'Gagal saat loading, tekan tombol "Masuk" kembali.';
    }
    hideLoader({ immediate: true });
  }
}

$('logout-btn')?.addEventListener('click', async () => {
  try {
    if (state.sessionToken) {
      await fetch(`${API}/logout`, {
        method: 'POST',
        headers: authHeaders(),
      });
    }
  } catch (_) {
    // abaikan
  }

  clearAuth();

  state = {
    username: null,
    role: null,
    tlName: '',
    sessionToken: null,
    lockedTL: '',
    activeFileId: null,
    activeFileName: '',
    availableFiles: [],
    mode: 'TL',
    selectedTL: '',
    selectedAgent: '',
    selectedMonth: null,
    metaData: null,
    dashData: null,
    charts: state.charts || {},
  };

  resetDashboardView();

  hide($('app'));
  show($('login-page'));

  if ($('login-user')) $('login-user').value = '';
  if ($('login-pass')) $('login-pass').value = '';
  if ($('login-error')) $('login-error').textContent = '';
});

// =====================
// FILE SOURCE (ADMIN FILE + MANUAL UPLOAD)
// =====================
$('upload-area')?.addEventListener('click', () => $('file-input')?.click());

$('upload-area')?.addEventListener('dragover', (e) => {
  e.preventDefault();
  $('upload-area').style.borderColor = 'rgba(255,255,255,0.7)';
});

$('upload-area')?.addEventListener('dragleave', () => {
  $('upload-area').style.borderColor = '';
});

$('upload-area')?.addEventListener('drop', async (e) => {
  e.preventDefault();
  $('upload-area').style.borderColor = '';
  const file = e.dataTransfer?.files?.[0];
  if (file) await uploadFile(file);
});

$('file-input')?.addEventListener('change', async (e) => {
  const file = e.target?.files?.[0];
  if (file) await uploadFile(file);
});

$('admin-file-select')?.addEventListener('change', async (e) => {
  const value = e.target?.value ? Number(e.target.value) : null;
  state.activeFileId = value || null;
  state.activeFileName = e.target?.selectedOptions?.[0]?.textContent || '';
  state.selectedMonth = null;
  resetDashboardView();

  if (!state.activeFileId) {
    setEmptyStateMessage(`
      <div class="empty-state-card">
        <h3>Pilih data dulu</h3>
        <p>Pilih dataset admin dari dropdown terlebih dahulu.</p>
      </div>
    `);
    return;
  }

  await loadMeta();
});

async function loadAvailableFiles({ autoSelectFirst = false, manageLoader = true } = {}) {
  if (manageLoader) showLoader('Memuat daftar berkas admin...', { stage: 'generic' });
  try {
    const res = await fetch(`${API}/files/available`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      throw new Error(await readErrorResponse(res));
    }

    const files = await res.json();
    state.availableFiles = Array.isArray(files) ? files : [];
    populateAvailableFiles();

    if (autoSelectFirst && !state.activeFileId && state.availableFiles.length > 0) {
      if ($('admin-file-select')) $('admin-file-select').value = '';
    }
  } catch (e) {
    setEmptyStateMessage(`
      <div class="empty-state-card">
        <h3>Dataset admin belum tersedia</h3>
        <p>${escHtml(e.message || 'Belum ada dataset admin yang bisa dipilih.')}</p>
      </div>
    `);
  }
  if (manageLoader) hideLoader();
}

function populateAvailableFiles() {
  const select = $('admin-file-select');
  if (!select) return;

  select.innerHTML = '<option value="">-- Pilih Berkas / Tanggal --</option>';
  state.availableFiles.forEach((item) => {
    const option = document.createElement('option');
    option.value = String(item.id);
    const dateText = item.upload_date ? new Date(item.upload_date).toLocaleDateString('id-ID') : '-';
    option.textContent = `${item.file_name} — ${dateText}`;
    select.appendChild(option);
  });

  if (state.activeFileId) {
    select.value = String(state.activeFileId);
  }
}

async function uploadFile(file) {
  showLoader('Mengupload file...', { stage: 'upload', reset: true });

  const form = new FormData();
  form.append('file', file);

  try {
    const result = await uploadFileWithProgress(form);
    state.activeFileId = result?.file_id || null;
    state.activeFileName = result?.file_name || file.name;

    if ($('file-indicator')) $('file-indicator').classList.remove('hidden');
    if ($('file-name')) $('file-name').textContent = file.name;
    if ($('manual-file-caption')) $('manual-file-caption').textContent = `File aktif: ${state.activeFileName}`;

    state.selectedMonth = null;
    resetDashboardView();

    beginLoaderTail(88, 96);
    await loadMeta({ manageLoader: false });
    stopLoaderTail();
    hideLoader({ message: 'Selesai!' });
  } catch (e) {
    stopLoaderTail();
    hideLoader({ immediate: true });
    alert('Upload gagal: ' + e.message);
  }
}

// =====================
// META (TL + AGENT LISTS)
// =====================
async function loadMeta({ autoApply = true, manageLoader = true } = {}) {
  if (!state.activeFileId) {
    setEmptyStateMessage(`
      <div class="empty-state-card">
        <h3>Pilih data dulu</h3>
        <p>Pilih dataset admin dari dropdown sebelum dashboard diproses.</p>
      </div>
    `);
    return;
  }

  if (manageLoader) showLoader('Memuat daftar TL & Agent...', { stage: 'generic' });
  try {
    const res = await fetch(`${API}/meta`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      const msg = await readErrorResponse(res);
      throw new Error(msg || 'Gagal membaca metadata file.');
    }

    state.metaData = await res.json();
    populateSidebar();

    if (autoApply && state.selectedTL) {
      await applyFilter(null, { manageLoader: false });
    }
  } catch (e) {
    setEmptyStateMessage(`
      <div class="empty-state-card">
        <h3>Metadata file gagal dibaca</h3>
        <p>${escHtml(e.message || 'Periksa format file yang dipilih.')}</p>
      </div>
    `);
  }
  if (manageLoader) hideLoader();
}

function populateSidebar() {
  if (!state.metaData) return;

  const tlSel = $('tl-select');
  if (!tlSel) return;

  const lockedTL = state.metaData.locked_tl || state.lockedTL || state.selectedTL;
  state.lockedTL = lockedTL || '';
  state.selectedTL = lockedTL || '';

  tlSel.innerHTML = '';
  const opt = document.createElement('option');
  opt.value = state.selectedTL;
  opt.textContent = state.selectedTL || '-- TL tidak ditemukan --';
  tlSel.appendChild(opt);
  tlSel.value = state.selectedTL;
  tlSel.disabled = true;

  populateAgents(state.selectedTL);
}

function populateAgents(tl) {
  const agentSel = $('agent-select');
  if (!agentSel) return;

  agentSel.innerHTML = '<option value="">-- Pilih Agent --</option>';

  const list = state.metaData?.agents_by_tl?.[tl] || [];
  list.forEach((ag) => {
    const opt = document.createElement('option');
    opt.value = ag;
    opt.textContent = ag;
    agentSel.appendChild(opt);
  });

  if (list.length > 0) {
    agentSel.value = list[0];
    state.selectedAgent = agentSel.value;
  } else {
    state.selectedAgent = '';
  }
}

$('tl-select')?.addEventListener('change', () => {
  state.selectedTL = state.lockedTL;
  if ($('tl-select')) $('tl-select').value = state.lockedTL;
});

$('agent-select')?.addEventListener('change', async (e) => {
  state.selectedAgent = e.target.value;
  state.selectedMonth = null;
  resetDashboardView();

  if (state.mode === 'Agent' && state.selectedAgent) {
    await applyFilter();
  }
});

// MODE TOGGLE
$('mode-agent-btn')?.addEventListener('click', () => setMode('Agent'));
$('mode-tl-btn')?.addEventListener('click', () => setMode('TL'));

async function setMode(m) {
  state.mode = m;
  state.selectedMonth = null;
  resetDashboardView();

  $('mode-agent-btn')?.classList.toggle('active', m === 'Agent');
  $('mode-tl-btn')?.classList.toggle('active', m === 'TL');

  if (m === 'TL') {
    hide($('agent-field'));
  } else {
    show($('agent-field'));
  }

  if (!state.metaData || !state.selectedTL) return;

  if (m === 'TL') {
    await applyFilter();
    return;
  }

  if (state.selectedAgent) {
    await applyFilter();
  }
}

// =====================
// APPLY / PROCESS
// =====================

function normalizeMonthOverride(monthOverride) {
  if (typeof monthOverride === 'string') {
    const value = monthOverride.trim();
    return value || null;
  }

  // Kalau yang masuk event object dari click, buang.
  if (monthOverride && typeof monthOverride === 'object') {
    return null;
  }

  if (typeof state.selectedMonth === 'string' && state.selectedMonth.trim()) {
    return state.selectedMonth.trim();
  }

  return null;
}

async function applyFilter(monthOverride = null, options = {}) {
  const manageLoader = options.manageLoader !== false;
  if (!state.selectedTL) {
    alert('Pilih Team Leader terlebih dahulu.');
    return;
  }

  if (state.mode === 'Agent' && !state.selectedAgent) {
    alert('Pilih Agent terlebih dahulu.');
    return;
  }

  const selectedMonthValue = normalizeMonthOverride(monthOverride);

  if (manageLoader) showLoader('Memproses data...', { stage: 'generic' });
  try {
    const body = {
      mode: state.mode,
      selected_tl: state.selectedTL,
      selected_agent: state.mode === 'Agent' ? state.selectedAgent : null,
      selected_month: selectedMonthValue,
    };

    const res = await fetch(`${API}/process`, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const msg = await readErrorResponse(res);
      alert('Error: ' + (msg || 'Proses gagal'));
      if (manageLoader) hideLoader({ immediate: true });
      return;
    }

    state.dashData = await res.json();
    state.selectedMonth = state.dashData?.selected_month ?? selectedMonthValue ?? null;

    renderDashboard(state.dashData);
  } catch (e) {
    alert('Tidak dapat terhubung ke backend: ' + e.message);
  }
  if (manageLoader) hideLoader();
}

// =====================
// RENDER DASHBOARD
// =====================
function renderDashboard(d) {
  if (!d) return;

  hide($('empty-state'));
  show($('dashboard'));

  const badges = [];
  badges.push(`<span class="badge">User: ${escHtml(d.username || state.username || '-')}</span>`);
  badges.push(`<span class="badge">TL: ${escHtml(d.locked_tl || d.selected_tl || state.lockedTL || '-')}</span>`);

  if (d.mode === 'Agent') {
    badges.push(`<span class="badge">Agent: ${escHtml(d.selected_agent)}</span>`);
  } else if (d.agent_count != null) {
    badges.push(`<span class="badge">Total Agent: ${fmtNum(d.agent_count)}</span>`);
  }

  badges.push(`<span class="badge">Mode Waktu: ${escHtml(d.time_mode)}</span>`);
  if ($('topbar-badges')) $('topbar-badges').innerHTML = badges.join('');

  if ($('kpi-overall')) {
    $('kpi-overall').textContent = d.overall != null ? `${Number(d.overall).toFixed(2)}%` : '-';
  }
  if ($('kpi-overall-sub')) {
    $('kpi-overall-sub').textContent = d.time_mode === 'Bulanan' ? 'Overall Bulanan' : 'Overall Harian';
  }
  if ($('kpi-rekaman')) $('kpi-rekaman').textContent = fmtNum(d.total_rekaman);
  if ($('kpi-aspek')) $('kpi-aspek').textContent = fmtNum(d.aspect_count);

  const strip = $('interest-strip');
  if (strip) {
    strip.innerHTML = '';
    if (d.interest_kpi && Object.keys(d.interest_kpi).length) {
      const kpi = d.interest_kpi;
      if (kpi.mode === 'lov3') {
        strip.innerHTML =
          chipHtml('Warm Leads / Minat (AI Lov3)', kpi.warm_leads) +
          chipHtml('Tidak Minat (AI Lov3)', kpi.tidak_minat);
      } else {
        strip.innerHTML =
          chipHtml('Ragu/Minat menurut AI/Excel', kpi.ai_minat) +
          chipHtml('Minat menurut Call Result', kpi.agent_minat) +
          chipHtml('Minat Aktual (Rekonsiliasi)', kpi.aktual_minat);
      }
    }
  }

  const monthBarWrap = $('month-bar-wrap');
  const monthBar = $('month-bar');

  if (d.time_mode === 'Bulanan' && Array.isArray(d.month_list) && d.month_list.length > 1) {
    if (monthBar) {
      monthBar.innerHTML = '';
      d.month_list.forEach((m) => {
        const chip = document.createElement('button');
        chip.className = 'month-chip' + (m === d.selected_month ? ' active' : '');
        chip.textContent = m;
        chip.addEventListener('click', () => applyFilter(m));
        monthBar.appendChild(chip);
      });
    }
    show(monthBarWrap);
  } else {
    if (monthBar) monthBar.innerHTML = '';
    hide(monthBarWrap);
  }

  const weeklyTabBtn = $('tab-weekly-btn');
  if (d.time_mode === 'Bulanan') {
    show(weeklyTabBtn);
  } else {
    hide(weeklyTabBtn);
    if ($('tab-weekly')?.classList.contains('active')) {
      switchTab('overview');
    }
  }

  renderResultTable(d);
  renderAgentComparison(d);
  renderInterestSummary(d);
  renderPriorityTables(d);

  if (d.time_mode === 'Bulanan') {
    renderWeeklyTrend(d);
  } else {
    [
      'chart-weekly-overall', 'chart-weekly-wm', 'chart-daily-rate', 'chart-daily-bar',
      'chart-period-comparison', 'chart-rutin', 'chart-tidak-rutin'
    ].forEach(destroyChart);
    hide($('period-split-section'));
    hide($('routine-section'));
    hide($('nonroutine-section'));
  }

  renderHourlyTrend(d);
}

function chipHtml(label, value) {
  return `
    <div class="interest-chip">
      <div class="label">${escHtml(label)}</div>
      <div class="value">${fmtNum(value)}</div>
    </div>
  `;
}

// =====================
// RESULT TABLE
// =====================
function renderResultTable(d) {
  const rt = d?.result_table;
  if (!rt || !Array.isArray(rt.rows)) return;

  const rows = rt.rows;
  const thead = $('result-thead-row');
  const tbody = $('result-tbody');

  if (!thead || !tbody) return;

  if (rows.length === 0) {
    thead.innerHTML = '';
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align:center;color:#94a3b8;padding:24px">
          Tidak ada data
        </td>
      </tr>
    `;
    return;
  }

  const sampleRow = rows[0];
  const colKeys = Object.keys(sampleRow).filter((k) => !['col', 'pct'].includes(k));
  const colLabels = {
    aspek: 'Aspek',
    grade: 'Grade',
    bulanan: 'Bulanan',
    harian: 'Harian',
    minggu_1: 'Minggu 1',
    minggu_2: 'Minggu 2',
    minggu_3: 'Minggu 3',
    minggu_4: 'Minggu 4',
    minggu_5: 'Minggu 5',
    '08-10': '08-10',
    '10-12': '10-12',
    '12-13': '12-13',
    '13-15': '13-15',
    '15-16': '15-16',
    '16-18': '16-18',
    di_luar_08_18: 'Di luar 08-18',
  };
  const detailBuckets = new Set(['08-10', '10-12', '12-13', '13-15', '15-16', '16-18', 'harian', 'di_luar_08_18']);

  thead.innerHTML = colKeys.map((k) => `<th>${escHtml(colLabels[k] || k)}</th>`).join('');

  const weakSet = new Set(rows.slice(0, 5).map((r) => r.aspek));

  tbody.innerHTML = rows.map((r) => {
    const isWeak = weakSet.has(r.aspek);
    const cells = colKeys.map((k) => {
      if (k === 'grade') return `<td>${gradeHtml(r[k] || '-')}</td>`;

      const v = r[k];
      if (v == null) return '<td>-</td>';

      const breakdownKey = `${r.col}__${k}`;
      const hasBreakdown = d.time_mode === 'Harian'
        && detailBuckets.has(k)
        && Array.isArray(d.daily_aspect_breakdown?.[breakdownKey])
        && d.daily_aspect_breakdown[breakdownKey].length > 0;

      if (hasBreakdown) {
        return `
          <td>
            <button
              class="table-link-btn"
              onclick="openAspectBreakdownModal(decodeURIComponent('${encodeURIComponent(String(r.col))}'), decodeURIComponent('${encodeURIComponent(String(k))}'), decodeURIComponent('${encodeURIComponent(String(r.aspek))}'), decodeURIComponent('${encodeURIComponent(String(v))}'))"
            >${escHtml(String(v))}</button>
          </td>
        `;
      }

      return `<td>${escHtml(String(v))}</td>`;
    }).join('');
    const rowClass = r.grade === 'D' ? 'row-critical' : (isWeak ? 'row-weak' : '');
    return `<tr class="${rowClass}">${cells}</tr>`;
  }).join('');

  if ($('overview-title')) {
    $('overview-title').textContent =
      d.time_mode === 'Bulanan'
        ? 'Ringkasan Performa Bulanan per Aspek'
        : 'Ringkasan Performa Harian per Aspek';
  }
}

// =====================
// AGENT COMPARISON (TL mode)
// =====================
function renderAgentComparison(d) {
  const section = $('agent-comparison-section');
  if (d.mode !== 'TL' || !d.agent_comparison) {
    hide(section);
    return;
  }

  show(section);

  const { worst = [], best = [] } = d.agent_comparison;

  if ($('worst-agent-tbody')) {
    $('worst-agent-tbody').innerHTML = worst.map((r) => `
      <tr>
        <td><button class="table-link-btn" onclick="openAgentModal(decodeURIComponent('${encodeURIComponent(String(r.agent))}'))">${escHtml(r.agent)}</button></td>
        <td>${fmtNum(r.overall)}%</td>
        <td style="font-size:12px">${escHtml(r.aspek_lemah)}</td>
      </tr>
    `).join('');
  }

  if ($('best-agent-tbody')) {
    $('best-agent-tbody').innerHTML = best.map((r) => `
      <tr>
        <td><button class="table-link-btn" onclick="openAgentModal(decodeURIComponent('${encodeURIComponent(String(r.agent))}'))">${escHtml(r.agent)}</button></td>
        <td>${fmtNum(r.overall)}%</td>
        <td style="font-size:12px">${escHtml(r.aspek_kuat)}</td>
      </tr>
    `).join('');
  }
}

// =====================
// AGENT INTEREST SUMMARY
// =====================
function renderInterestSummary(d) {
  const section = $('agent-interest-section');
  if (d.mode !== 'TL' || !Array.isArray(d.agent_interest_summary)) {
    hide(section);
    return;
  }

  show(section);

  if ($('agent-interest-tbody')) {
    $('agent-interest-tbody').innerHTML = d.agent_interest_summary.map((r) => `
      <tr class="clickable" data-agent="${escHtml(r.agent)}" onclick="openAgentModal('${String(r.agent).replace(/'/g, "\\'")}')">
        <td>${escHtml(r.agent)}</td>
        <td>${fmtNum(r.minat)}</td>
        <td>${fmtNum(r.tidak_minat)}</td>
        <td>${fmtNum(r.rekaman)}</td>
      </tr>
    `).join('');
  }
}

// =====================
// PRIORITY TABLES
// =====================
function renderPriorityTable(headEl, bodyEl, rows, tableType) {
  if (!headEl || !bodyEl) return;

  if (!rows || rows.length === 0) {
    headEl.innerHTML = '<th>Info</th>';
    bodyEl.innerHTML = '<tr><td style="padding:16px;color:#94a3b8">Tidak ada data yang memenuhi kriteria.</td></tr>';
    return;
  }

  const labels = {
    agent: 'Nama Agent',
    jumlah_call: 'Jumlah Call',
    jumlah_customer: 'Customer Unik',
    ringkasan_aspek: tableType === 't1' ? 'Ringkasan Aspek Jarang Disebut' : 'Ringkasan Aspek Sudah Disebut',
    action: 'Action',
  };

  const columns = ['agent', 'jumlah_call', 'jumlah_customer', 'ringkasan_aspek', 'action'];
  headEl.innerHTML = columns.map((k) => `<th>${escHtml(labels[k] || k)}</th>`).join('');
  bodyEl.innerHTML = rows.map((r) => `
    <tr>
      <td>${escHtml(r.agent)}</td>
      <td>${fmtNum(r.jumlah_call)}</td>
      <td>${r.jumlah_customer == null ? '-' : fmtNum(r.jumlah_customer)}</td>
      <td style="font-size:12px">${escHtml(r.ringkasan_aspek || '-')}</td>
      <td>
        <button class="action-btn" onclick="openPriorityAgentModal('${tableType}', decodeURIComponent('${encodeURIComponent(String(r.agent))}'))">Detail</button>
      </td>
    </tr>
  `).join('');
}

function renderPriorityTables(d) {
  renderPriorityTable($('pt1-head'), $('pt1-body'), d.priority_t1, 't1');
  renderPriorityTable($('pt2-head'), $('pt2-body'), d.priority_t2, 't2');
}

// =====================
// WEEKLY TREND CHARTS
// =====================
function renderWeeklyTrend(d) {
  if (!d.weekly_trend) return;

  const wt = d.weekly_trend;
  const weeklyRows = Array.isArray(wt.weekly) ? wt.weekly : [];
  if (weeklyRows.length === 0) return;

  const labels = weeklyRows.map((w) => w.week);
  const overallData = weeklyRows.map((w) => w.overall);
  const wmData = weeklyRows.map((w) => w.wm);

  const datasets = [
    {
      label: 'Overall minggu terpilih',
      data: overallData,
      borderColor: '#002D72',
      backgroundColor: 'rgba(0,45,114,0.07)',
      borderWidth: 3,
      pointRadius: 5,
      pointHoverRadius: 5,
      pointBackgroundColor: '#002D72',
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      fill: true,
      tension: 0.35,
      spanGaps: true,
      datalabels: { display: false },
    }
  ];

  const referenceLines = [
    { key: 'min_line', label: 'Min seluruh pembanding', color: '#dc2626' },
    { key: 'max_line', label: 'Max seluruh pembanding', color: '#1d4ed8' },
    { key: 'kkm_line', label: 'KKM seluruh pembanding', color: '#16a34a' },
    { key: 'avg_selected', label: 'Rata-rata entitas terpilih', color: '#f59e0b' },
  ];
  referenceLines.forEach((item) => {
    if (wt[item.key] != null) {
      datasets.push({
        label: item.label,
        data: labels.map(() => wt[item.key]),
        borderColor: item.color,
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        fill: false,
        tension: 0,
      });
    }
  });

  makeChart('chart-weekly-overall', {
    type: 'line',
    data: { labels, datasets },
    options: chartBaseOpts('Overall (%)', true),
  });

  const weeklyWmOpts = chartBaseOpts('Jumlah', false);
  makeChart('chart-weekly-wm', {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Volume Minat / WM',
        data: wmData,
        backgroundColor: 'rgba(5,150,105,0.76)',
        hoverBackgroundColor: 'rgba(5,150,105,0.76)',
        borderRadius: 7,
        borderSkipped: false,
      }]
    },
    options: {
      ...weeklyWmOpts,
      plugins: {
        ...(weeklyWmOpts.plugins || {}),
        tooltip: {
          ...((weeklyWmOpts.plugins || {}).tooltip || {}),
          callbacks: {
            label(context) {
              const row = weeklyRows[context.dataIndex] || {};
              return minatTooltipLine(row, 'Jumlah Minat');
            },
            afterLabel(context) {
              const row = weeklyRows[context.dataIndex] || {};
              return row?.rekaman != null ? `Total rekaman: ${fmtNum(row.rekaman)}` : '';
            },
          },
        },
      },
    },
  });

  if (Array.isArray(wt.daily_interest) && wt.daily_interest.length > 0) {
    const dlabels = wt.daily_interest.map((r) => r.date);
    const drate = wt.daily_interest.map((r) => r.rate);
    const dminat = wt.daily_interest.map((r) => r.minat);

    const dailyRateOpts = chartBaseOpts('Rate Minat (%)', true);
    makeChart('chart-daily-rate', {
      type: 'line',
      data: {
        labels: dlabels,
        datasets: [{
          label: 'Rate Minat (%)',
          data: drate,
          borderColor: '#1d4ed8',
          backgroundColor: 'rgba(29,78,216,0.07)',
          borderWidth: 3,
          pointRadius: 4.5,
          pointHoverRadius: 4.5,
          pointBackgroundColor: '#1d4ed8',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          fill: true,
          tension: 0.35,
          spanGaps: true,
        }]
      },
      options: {
        ...dailyRateOpts,
        plugins: {
          ...(dailyRateOpts.plugins || {}),
          tooltip: {
            ...((dailyRateOpts.plugins || {}).tooltip || {}),
            callbacks: {
              label(context) {
                const value = numericOrNull(context.parsed?.y ?? context.raw);
                return `Rate Minat: ${value == null ? '-' : `${fmtNum(value)}%`}`;
              },
              afterLabel(context) {
                const row = wt.daily_interest?.[context.dataIndex] || {};
                return minatTooltipLine(row, 'Jumlah Minat');
              },
            },
          },
        },
      },
    });

    const dailyBarOpts = chartBaseOpts('Jumlah Minat', false);
    makeChart('chart-daily-bar', {
      type: 'bar',
      data: {
        labels: dlabels,
        datasets: [{
          label: 'Jumlah Minat',
          data: dminat,
          backgroundColor: 'rgba(168,85,247,0.76)',
          hoverBackgroundColor: 'rgba(168,85,247,0.76)',
          borderRadius: 6,
          borderSkipped: false,
        }]
      },
      options: {
        ...dailyBarOpts,
        plugins: {
          ...(dailyBarOpts.plugins || {}),
          tooltip: {
            ...((dailyBarOpts.plugins || {}).tooltip || {}),
            callbacks: {
              label(context) {
                const row = wt.daily_interest?.[context.dataIndex] || {};
                return minatTooltipLine(row, 'Jumlah Minat');
              },
              afterLabel(context) {
                const row = wt.daily_interest?.[context.dataIndex] || {};
                const rate = numericOrNull(row?.rate);
                return rate == null ? '' : `Rate Minat: ${fmtNum(rate)}%`;
              },
            },
          },
        },
      },
    });
  } else {
    destroyChart('chart-daily-rate');
    destroyChart('chart-daily-bar');
  }

  const ps = wt.period_split;
  if (ps && (Array.isArray(ps.period_1) || Array.isArray(ps.period_2))) {
    show($('period-split-section'));
    if ($('period-comparison-title')) $('period-comparison-title').textContent = `${ps.label_1 || 'Periode 1'} vs ${ps.label_2 || 'Periode 2'}`;
    renderPeriodComparisonChart('chart-period-comparison', ps.period_1 || [], ps.period_2 || [], ps.label_1 || 'Periode 1', ps.label_2 || 'Periode 2');
  } else {
    hide($('period-split-section'));
    destroyChart('chart-period-comparison');
  }

  const rutin = wt.rutin;
  if (rutin && (Array.isArray(rutin.table) && rutin.table.length)) {
    show($('routine-section'));
    renderCountRateCombo('chart-rutin', rutin.daily || [], 'minat', 'rate', 'Jumlah Minat', 'Rate Minat (%)');
    if ($('rutin-tbody')) {
      $('rutin-tbody').innerHTML = rutin.table.map((r) => `
        <tr>
          <td>${escHtml(r.agent)}</td>
          <td>${fmtNum(r.hari_hadir)}</td>
          <td>${fmtNum(r.hari_kosong)}</td>
          <td>${fmtNum(r.minat)}</td>
          <td>${fmtNum(r.tidak_minat)}</td>
          <td>${fmtNum(r.rekaman)}</td>
        </tr>
      `).join('');
    }
  } else {
    hide($('routine-section'));
    destroyChart('chart-rutin');
    if ($('rutin-tbody')) $('rutin-tbody').innerHTML = '';
  }

  const nonroutine = wt.tidak_rutin;
  if (nonroutine && (Array.isArray(nonroutine.table) && nonroutine.table.length)) {
    show($('nonroutine-section'));
    renderCountRateCombo('chart-tidak-rutin', nonroutine.daily || [], 'minat', 'rate', 'Jumlah Minat', 'Rate Minat (%)');
    if ($('tidak-rutin-tbody')) {
      $('tidak-rutin-tbody').innerHTML = nonroutine.table.map((r) => `
        <tr>
          <td>${escHtml(r.agent)}</td>
          <td>${fmtNum(r.hari_hadir)}</td>
          <td>${fmtNum(r.hari_kosong)}</td>
          <td>${fmtNum(r.minat)}</td>
          <td>${fmtNum(r.tidak_minat)}</td>
          <td>${fmtNum(r.rekaman)}</td>
        </tr>
      `).join('');
    }
  } else {
    hide($('nonroutine-section'));
    destroyChart('chart-tidak-rutin');
    if ($('tidak-rutin-tbody')) $('tidak-rutin-tbody').innerHTML = '';
  }
}

// =====================
// HOURLY TREND CHARTS
// =====================
function renderHourlyTrend(d) {
  if (!d.hourly_trend) return;

  const ht = d.hourly_trend;
  const overallRows = Array.isArray(ht.overall) ? ht.overall : [];
  const interestRows = Array.isArray(ht.interest) ? ht.interest : [];
  const notInterestRows = Array.isArray(ht.not_interest) ? ht.not_interest : [];
  const callMixRows = Array.isArray(ht.call_mix) ? ht.call_mix : [];
  const durRows = Array.isArray(ht.duration) ? ht.duration : [];
  const labels = overallRows.map((r) => r.jam);
  const ref = ht.reference_lines || {};

  renderLegendCards('hourly-overall-legend', [
    { label: 'Garis utama', desc: 'Overall dari TL / Agent yang sedang dipilih.' },
    { label: 'Max tertinggi', desc: `Batas performa terbaik dari ${ref.reference_basis || 'data pembanding'}.` },
    { label: 'Min terendah', desc: `Batas performa terendah dari ${ref.reference_basis || 'data pembanding'}.` },
    { label: 'KKM', desc: `Rata-rata umum dari ${ref.reference_basis || 'data pembanding'}.` },
    { label: 'Avg terpilih', desc: 'Rata-rata jam aktif dari entitas yang sedang dibuka.' },
  ]);

  if (overallRows.length === 0) {
    ['chart-hourly-overall', 'chart-hourly-volume', 'chart-hourly-interest', 'chart-hourly-not-interest', 'chart-call-mix', 'chart-hourly-duration'].forEach(destroyChart);
    return;
  }

  const overallDatasets = [
    {
      label: 'Overall terpilih (%)',
      data: overallRows.map((r) => r.overall),
      borderColor: '#002D72',
      backgroundColor: 'rgba(0,45,114,0.07)',
      borderWidth: 3,
      pointRadius: 4,
      pointHoverRadius: 4,
      pointBackgroundColor: '#002D72',
      pointBorderColor: '#fff',
      pointBorderWidth: 2,
      fill: true,
      tension: 0.35,
      spanGaps: true,
      datalabels: { display: false },
    }
  ];

  [
    { key: 'upper', label: 'Max tertinggi', shortLabel: 'Max', color: '#1d4ed8' },
    { key: 'lower', label: 'Min terendah', shortLabel: 'Min', color: '#dc2626' },
    { key: 'kkm', label: 'KKM', shortLabel: 'KKM', color: '#16a34a' },
    { key: 'avg_selected', label: 'Avg terpilih', shortLabel: 'Avg', color: '#f59e0b' },
  ].forEach((item) => {
    if (ref[item.key] != null) {
      overallDatasets.push({
        label: item.label,
        data: labels.map(() => ref[item.key]),
        borderColor: item.color,
        borderWidth: 1.5,
        borderDash: [6, 4],
        pointRadius: 0,
        pointHoverRadius: 0,
        pointHitRadius: 0,
        fill: false,
        tension: 0,
        showRightEdgeLabel: true,
        rightEdgeLabel: `${item.shortLabel} ${Number(ref[item.key]).toFixed(1)}`,
        datalabels: { display: false },
      });
    }
  });

  makeChart('chart-hourly-overall', {
    type: 'line',
    data: { labels, datasets: overallDatasets },
    options: {
      ...chartBaseOpts('Overall (%)', true),
      plugins: {
        ...(chartBaseOpts('Overall (%)', true).plugins || {}),
        lineKeyPoints: false,
        rightEdgeReferenceLabels: { display: true },
        datalabels: { display: false },
      },
      scales: {
        x: {
          grid: { color: 'rgba(226,232,240,0.7)', drawTicks: false },
          border: { display: false },
          ticks: { font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' }, color: '#64748b', padding: 6 }
        },
        y: {
          min: 0, max: 100,
          grid: { color: 'rgba(226,232,240,0.7)', drawTicks: false },
          border: { display: false },
          ticks: { font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' }, color: '#64748b', padding: 8 },
          title: { display: true, text: 'Overall (%)', font: { size: 11, family: 'Plus Jakarta Sans', weight: '600' }, color: '#94a3b8' }
        },
      },
    },
  });

  makeChart('chart-hourly-volume', {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Jumlah Rekaman',
        data: overallRows.map((r) => r.rekaman),
        backgroundColor: 'rgba(0,45,114,0.72)',
        hoverBackgroundColor: 'rgba(0,45,114,0.72)',
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: chartBaseOpts('Jumlah Rekaman', false),
  });

  renderCountRateCombo('chart-hourly-interest', interestRows, 'count', 'rate', 'Jumlah Minat', 'Rate Minat (%)', {
    barColor: 'rgba(29,78,216,0.72)',
    barHover: 'rgba(29,78,216,0.90)',
    lineColor: '#1d4ed8',
    lineFill: 'rgba(29,78,216,0.06)',
  });
  renderCountRateCombo('chart-hourly-not-interest', notInterestRows, 'count', 'rate', 'Jumlah Tidak Minat', 'Rate Tidak Minat (%)', {
    barColor: 'rgba(220,38,38,0.65)',
    barHover: 'rgba(220,38,38,0.85)',
    lineColor: '#dc2626',
    lineFill: 'rgba(220,38,38,0.06)',
  });

  renderLegendCards('call-mix-legend', [
    { label: 'Minat (M1/M2/M3)', desc: 'Semakin tinggi, semakin banyak call yang masuk kategori minat.' },
    { label: 'Tidak Minat', desc: 'Membantu melihat jam yang paling sering menghasilkan penolakan.' },
    { label: 'Appointment', desc: 'Memudahkan melihat jam yang paling sering menghasilkan appointment.' },
  ]);

  if (callMixRows.length > 0) {
    const mixLabels = callMixRows.map((r) => r.jam);
    makeChart('chart-call-mix', {
      type: 'line',
      data: {
        labels: mixLabels,
        datasets: [
          {
            label: 'Minat (M1/M2/M3)',
            data: callMixRows.map((r) => r.minat),
            borderColor: '#1d4ed8',
            backgroundColor: 'rgba(29,78,216,0.07)',
            borderWidth: 3,
            pointRadius: 4.5,
            pointHoverRadius: 4.5,
            pointBackgroundColor: '#1d4ed8',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            tension: 0.35,
          },
          {
            label: 'Tidak Minat',
            data: callMixRows.map((r) => r.tidak_minat),
            borderColor: '#dc2626',
            backgroundColor: 'rgba(220,38,38,0.07)',
            borderWidth: 3,
            pointRadius: 4.5,
            pointHoverRadius: 4.5,
            pointBackgroundColor: '#dc2626',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            tension: 0.35,
          },
          {
            label: 'Appointment',
            data: callMixRows.map((r) => r.appointment),
            borderColor: '#059669',
            backgroundColor: 'rgba(5,150,105,0.07)',
            borderWidth: 3,
            pointRadius: 4.5,
            pointHoverRadius: 4.5,
            pointBackgroundColor: '#059669',
            pointBorderColor: '#fff',
            pointBorderWidth: 2,
            tension: 0.35,
          }
        ]
      },
      options: chartBaseOpts('Jumlah Call', true),
    });
  } else {
    destroyChart('chart-call-mix');
  }

  if (durRows.length > 0) {
    const durLabels = durRows.map((r) => r.jam);
    const durData = durRows.map((r) => r.avg_sec);

    const durationBaseOpts = chartBaseOpts('Menit:Detik', true);

    makeChart('chart-hourly-duration', {
      type: 'line',
      data: {
        labels: durLabels,
        datasets: [{
          label: 'Durasi rata-rata (mm:ss)',
          data: durData,
          borderColor: '#059669',
          backgroundColor: 'rgba(5,150,105,0.07)',
          borderWidth: 3,
          pointRadius: 4.5,
          pointHoverRadius: 4.5,
          pointBackgroundColor: '#059669',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          fill: true,
          tension: 0.35,
          spanGaps: true,
          datalabels: { display: false },
        }]
      },
      options: {
        ...durationBaseOpts,
        plugins: {
          ...(durationBaseOpts.plugins || {}),
          datalabels: { display: false },
          tooltip: {
            ...((durationBaseOpts.plugins || {}).tooltip || {}),
            callbacks: {
              label(context) {
                const label = context.dataset?.label || 'Durasi';
                return `${label}: ${formatDurationMmSs(context.parsed?.y ?? context.raw)}`;
              },
            },
          },
        },
        scales: {
          ...durationBaseOpts.scales,
          y: {
            ...durationBaseOpts.scales.y,
            ticks: {
              ...durationBaseOpts.scales.y.ticks,
              callback(value) {
                return formatDurationMmSs(value);
              },
            },
          },
        },
      },
    });
  } else {
    destroyChart('chart-hourly-duration');
  }
}

function chartBaseOpts(yLabel, legend) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    resizeDelay: 160,
    animation: false,
    transitions: { active: { animation: { duration: 0 } } },
    layout: { padding: { top: 8, right: 10, bottom: 0, left: 0 } },
    plugins: {
      legend: {
        display: legend,
        position: 'top',
        align: 'start',
        labels: {
          font: { size: 11.5, family: 'Plus Jakarta Sans', weight: '600' },
          boxWidth: 12,
          boxHeight: 12,
          borderRadius: 3,
          usePointStyle: false,
          padding: 16,
          color: '#475569',
        }
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleFont: { size: 12, family: 'Plus Jakarta Sans', weight: '700' },
        bodyFont: { size: 12, family: 'Plus Jakarta Sans' },
        padding: 10,
        cornerRadius: 8,
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
        displayColors: true,
        boxWidth: 10,
        boxHeight: 10,
        boxPadding: 4,
      },
    },
    scales: {
      x: {
        grid: { color: 'rgba(226,232,240,0.7)', drawTicks: false },
        border: { display: false },
        ticks: {
          font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' },
          color: '#64748b',
          maxRotation: 45,
          padding: 6,
        }
      },
      y: {
        grid: { color: 'rgba(226,232,240,0.7)', drawTicks: false },
        border: { display: false },
        ticks: {
          font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' },
          color: '#64748b',
          padding: 8,
        },
        beginAtZero: true,
        title: {
          display: !!yLabel,
          text: yLabel,
          font: { size: 11, family: 'Plus Jakarta Sans', weight: '600' },
          color: '#94a3b8',
          padding: { bottom: 8 },
        }
      },
    },
  };
}

// Plugin: show value labels on top of bars
const barLabelPlugin = {
  id: 'barLabels',
  afterDatasetsDraw(chart) {
    const { ctx, data } = chart;
    chart.data.datasets.forEach((dataset, datasetIndex) => {
      const meta = chart.getDatasetMeta(datasetIndex);
      if (meta.hidden || dataset.type === 'line') return;
      meta.data.forEach((bar, index) => {
        const value = numericOrNull(dataset.data[index]);
        if (value == null || value === 0) return;
        ctx.save();
        ctx.font = '600 10px Plus Jakarta Sans';
        ctx.fillStyle = '#475569';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        const label = Number.isInteger(value) ? value : Number(value).toFixed(1);
        ctx.fillText(label, bar.x, bar.y - 3);
        ctx.restore();
      });
    });
  }
};

// Plugin: show key point labels on line charts (min, max, last)
const lineKeyPointPlugin = {
  id: 'lineKeyPoints',
  afterDatasetsDraw(chart) {
    const pluginOpt = chart?.options?.plugins?.lineKeyPoints;
    if (pluginOpt === false || pluginOpt?.display === false) return;

    const { ctx } = chart;
    chart.data.datasets.forEach((dataset, datasetIndex) => {
      if (dataset.type !== undefined && dataset.type !== 'line') return;
      const meta = chart.getDatasetMeta(datasetIndex);
      if (meta.hidden || !meta.data || meta.data.length === 0) return;
      // Only annotate the first (primary) dataset and skip reference/dash lines
      if (dataset.borderDash && dataset.borderDash.length) return;
      if (datasetIndex > 0) return; // Only main line

      const rawVals = Array.isArray(dataset.data) ? dataset.data : [];
      if (!rawVals.length) return;

      const vals = rawVals.map((v) => numericOrNull(v));
      const validVals = vals.filter((v) => v != null);
      if (!validVals.length) return;

      const maxVal = Math.max(...validVals);
      const minVal = Math.min(...validVals);
      const lastIndex = (() => {
        for (let i = vals.length - 1; i >= 0; i -= 1) {
          if (vals[i] != null) return i;
        }
        return -1;
      })();
      if (lastIndex < 0) return;

      const annotated = new Set();

      vals.forEach((v, i) => {
        if (v == null) return;
        const isMax  = v === maxVal;
        const isMin  = v === minVal;
        const isLast = i === lastIndex;

        if (!isMax && !isMin && !isLast) return;

        // Avoid double-label if indices overlap
        const key = `${i}`;
        if (annotated.has(key)) return;
        annotated.add(key);

        const point = meta.data[i];
        if (!point) return;

        const label = Number.isInteger(v) ? String(v) : Number(v).toFixed(1);
        const isTop = isMax || isLast;
        const yOffset = isTop ? -12 : 14;

        ctx.save();
        ctx.font = '700 10.5px Plus Jakarta Sans';
        ctx.textAlign = 'center';
        ctx.textBaseline = isTop ? 'bottom' : 'top';

        // Background pill
        const tw = ctx.measureText(label).width;
        const px = 5, py = 2;
        const rx = point.x - tw/2 - px;
        const ry = isTop ? point.y + yOffset - 14 : point.y + yOffset;
        const rw = tw + px*2;
        const rh = 14 + py;
        ctx.fillStyle = isLast ? '#002D72' : isMax ? '#059669' : '#dc2626';
        roundRect(ctx, rx, ry, rw, rh, 4);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, point.x, isTop ? point.y + yOffset : point.y + yOffset + py + 1);
        ctx.restore();
      });
    });
  }
};

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}


const rightEdgeReferenceLabelPlugin = {
  id: 'rightEdgeReferenceLabels',
  afterDatasetsDraw(chart) {
    const pluginOpt = chart?.options?.plugins?.rightEdgeReferenceLabels;
    if (pluginOpt === false || pluginOpt?.display === false) return;

    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    chart.data.datasets.forEach((dataset, datasetIndex) => {
      if (!dataset?.showRightEdgeLabel) return;

      const meta = chart.getDatasetMeta(datasetIndex);
      if (!meta || meta.hidden) return;

      const values = Array.isArray(dataset.data) ? dataset.data : [];
      const value = values.find((v) => v != null);
      if (value == null) return;

      const yScaleId = meta.yAxisID || dataset.yAxisID || 'y';
      const yScale = chart.scales?.[yScaleId];
      if (!yScale) return;

      const y = yScale.getPixelForValue(value);
      const text = dataset.rightEdgeLabel || `${Number(value).toFixed(1)}`;
      const x = chartArea.right - 6;

      ctx.save();
      ctx.font = '700 10.5px Plus Jakarta Sans';
      ctx.textAlign = 'right';
      ctx.textBaseline = 'middle';

      const textWidth = ctx.measureText(text).width;
      const boxWidth = textWidth + 10;
      const boxHeight = 18;
      const boxX = x - boxWidth;
      const boxY = y - boxHeight / 2;

      ctx.fillStyle = dataset.borderColor || '#475569';
      roundRect(ctx, boxX, boxY, boxWidth, boxHeight, 6);
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, x - 5, y);
      ctx.restore();
    });
  }
};

// Register custom plugins globally
Chart.register(barLabelPlugin, lineKeyPointPlugin, rightEdgeReferenceLabelPlugin);

function renderLegendCards(containerId, items) {
  const container = $(containerId);
  if (!container) return;
  if (!items || !items.length) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = items.map((item) => `
    <div class="legend-card">
      <div class="legend-label">${escHtml(item.label)}</div>
      <div class="legend-desc">${escHtml(item.desc || '')}</div>
    </div>
  `).join('');
}


function renderPeriodComparisonChart(canvasId, period1Rows, period2Rows, label1 = 'Periode 1', label2 = 'Periode 2') {
  const p1 = Array.isArray(period1Rows) ? period1Rows : [];
  const p2 = Array.isArray(period2Rows) ? period2Rows : [];
  const maxLen = Math.max(p1.length, p2.length);

  if (!maxLen) {
    destroyChart(canvasId);
    return;
  }

  const labels = Array.from({ length: maxLen }, (_, i) => `Hari ke-${i + 1}`);
  const period1Data = Array.from({ length: maxLen }, (_, i) => numericOrNull(p1[i]?.minat));
  const period2Data = Array.from({ length: maxLen }, (_, i) => numericOrNull(p2[i]?.minat));

  makeChart(canvasId, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: label1,
          data: period1Data,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37,99,235,0.08)',
          borderWidth: 3,
          pointRadius: 4.5,
          pointHoverRadius: 4.5,
          pointBackgroundColor: '#2563eb',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
          metaRows: p1,
        },
        {
          label: label2,
          data: period2Data,
          borderColor: '#dc2626',
          backgroundColor: 'rgba(220,38,38,0.08)',
          borderWidth: 3,
          pointRadius: 4.5,
          pointHoverRadius: 4.5,
          pointBackgroundColor: '#dc2626',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.35,
          spanGaps: true,
          fill: false,
          metaRows: p2,
        }
      ]
    },
    options: {
      ...chartBaseOpts('Jumlah Minat', true),
      interaction: { mode: 'index', intersect: false },
      plugins: {
        ...((chartBaseOpts('Jumlah Minat', true)).plugins || {}),
        lineKeyPoints: { display: false },
        tooltip: {
          ...(((chartBaseOpts('Jumlah Minat', true)).plugins || {}).tooltip || {}),
          callbacks: {
            label(context) {
              const row = context.dataset?.metaRows?.[context.dataIndex] || {};
              return `${context.dataset?.label || 'Periode'}: ${fmtFraction(row?.minat ?? context.raw, row?.rekaman)}`;
            },
            afterLabel(context) {
              const row = context.dataset?.metaRows?.[context.dataIndex] || {};
              const date = row?.date;
              return date ? `Tanggal asli: ${date}` : '';
            },
          },
        },
      },
    },
  });
}

function renderCountRateCombo(canvasId, rows, countKey, rateKey, countLabel, rateLabel, colors = {}) {
  if (!rows || rows.length === 0) {
    destroyChart(canvasId);
    return;
  }

  const labels = rows.map((r) => r.date || r.jam);
  makeChart(canvasId, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          type: 'bar',
          label: countLabel,
          data: rows.map((r) => numericOrNull(r[countKey])),
          backgroundColor: colors.barColor || 'rgba(14,116,144,0.76)',
          hoverBackgroundColor: colors.barColor || 'rgba(14,116,144,0.76)',
          borderRadius: 6,
          borderSkipped: false,
          yAxisID: 'y',
        },
        {
          type: 'line',
          label: rateLabel,
          data: rows.map((r) => numericOrNull(r[rateKey])),
          borderColor: colors.lineColor || '#7c3aed',
          backgroundColor: colors.lineFill || 'rgba(124,58,237,0.06)',
          borderWidth: 2.8,
          pointRadius: 4.5,
          pointHoverRadius: 4.5,
          pointBackgroundColor: colors.lineColor || '#7c3aed',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.35,
          fill: false,
          spanGaps: true,
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 160,
      animation: false,
      transitions: { active: { animation: { duration: 0 } } },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'start',
          labels: {
            font: { size: 11.5, family: 'Plus Jakarta Sans', weight: '600' },
            boxWidth: 12, boxHeight: 12, borderRadius: 3,
            padding: 16, color: '#475569',
          }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleFont: { size: 12, family: 'Plus Jakarta Sans', weight: '700' },
          bodyFont: { size: 12, family: 'Plus Jakarta Sans' },
          padding: 10, cornerRadius: 8,
          borderColor: 'rgba(255,255,255,0.08)', borderWidth: 1,
          callbacks: {
            label(context) {
              const row = rows[context.dataIndex] || {};
              if (context.dataset?.type === 'bar') {
                return `${countLabel}: ${fmtFraction(row?.[countKey] ?? context.raw, row?.rekaman)}`;
              }
              const rate = numericOrNull(row?.[rateKey] ?? context.raw);
              return `${rateLabel}: ${rate == null ? '-' : `${fmtNum(rate)}%`}`;
            },
            afterLabel(context) {
              const row = rows[context.dataIndex] || {};
              if (context.dataset?.type === 'line') {
                return `${countLabel}: ${fmtFraction(row?.[countKey], row?.rekaman)}`;
              }
              const rate = numericOrNull(row?.[rateKey]);
              return rate == null ? '' : `${rateLabel}: ${fmtNum(rate)}%`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(226,232,240,0.7)', drawTicks: false },
          border: { display: false },
          ticks: { font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' }, color: '#64748b', maxRotation: 45, padding: 6 }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(226,232,240,0.7)', drawTicks: false },
          border: { display: false },
          ticks: { font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' }, color: '#64748b', padding: 8 },
          title: { display: true, text: countLabel, font: { size: 11, family: 'Plus Jakarta Sans', weight: '600' }, color: '#94a3b8' },
        },
        y1: {
          beginAtZero: true,
          position: 'right',
          min: 0, max: 100,
          grid: { drawOnChartArea: false },
          border: { display: false },
          ticks: { font: { size: 11, family: 'Plus Jakarta Sans', weight: '500' }, color: '#64748b', padding: 8 },
          title: { display: true, text: rateLabel, font: { size: 11, family: 'Plus Jakarta Sans', weight: '600' }, color: '#94a3b8' },
        }
      }
    }
  });
}

// =====================
// TABS
// =====================
document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function switchTab(id) {
  document.querySelectorAll('.tab-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.tab === id);
  });

  document.querySelectorAll('.tab-pane').forEach((p) => {
    p.classList.toggle('active', p.id === 'tab-' + id);
  });

  scheduleChartResize(90);
}

// =====================
// AGENT MODAL
// =====================
async function openAgentModal(agentName) {
  if (!state.dashData) return;

  if ($('modal-title')) $('modal-title').textContent = `Detail Rekaman: ${agentName}`;
  if ($('modal-body')) {
    $('modal-body').innerHTML = '<div style="text-align:center;padding:24px;color:#94a3b8">Memuat...</div>';
  }
  $('agent-modal-overlay')?.classList.add('open');

  try {
    const params = new URLSearchParams({
      agent: agentName,
    });

    if (state.selectedMonth) {
      params.append('month', state.selectedMonth);
    }

    const res = await fetch(`${API}/detail-agent?${params.toString()}`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      const msg = await readErrorResponse(res);
      throw new Error(msg || 'Gagal memuat detail agent');
    }

    const data = await res.json();
    renderModalContent(agentName, data);
  } catch (e) {
    if ($('modal-body')) {
      $('modal-body').innerHTML = `<p style="color:#dc2626">${escHtml(e.message || 'Gagal memuat data.')}</p>`;
    }
  }
}

async function openPriorityAgentModal(tableType, agentName) {
  if ($('modal-title')) {
    $('modal-title').textContent = tableType === 't1'
      ? `Detail Call Minat — ${agentName}`
      : `Detail Call Tidak Minat — ${agentName}`;
  }
  if ($('modal-body')) {
    $('modal-body').innerHTML = '<div style="text-align:center;padding:24px;color:#94a3b8">Memuat...</div>';
  }
  $('agent-modal-overlay')?.classList.add('open');

  try {
    const params = new URLSearchParams({
      table_type: tableType,
      agent: agentName,
    });

    if (state.selectedMonth) {
      params.append('month', state.selectedMonth);
    }

    const res = await fetch(`${API}/priority-agent-detail?${params.toString()}`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      const msg = await readErrorResponse(res);
      throw new Error(msg || 'Gagal memuat detail priority table');
    }

    const data = await res.json();
    renderPriorityModalContent(data);
  } catch (e) {
    if ($('modal-body')) {
      $('modal-body').innerHTML = `<p style="color:#dc2626">${escHtml(e.message || 'Gagal memuat data.')}</p>`;
    }
  }
}

function openAspectBreakdownModal(aspectCol, bucketKey, aspectLabel, ratioLabel) {
  const breakdownKey = `${aspectCol}__${bucketKey}`;
  const rows = state.dashData?.daily_aspect_breakdown?.[breakdownKey] || [];

  if ($('modal-title')) {
    $('modal-title').textContent = `Detail Aspek: ${aspectLabel} (${bucketKey})`;
  }

  if (!rows.length) {
    if ($('modal-body')) $('modal-body').innerHTML = '<p style="color:#94a3b8">Tidak ada detail agent untuk sel ini.</p>';
    $('agent-modal-overlay')?.classList.add('open');
    return;
  }

  const html = `
    <div class="detail-summary-card">
      <div class="detail-summary-label">Total pada sel</div>
      <div class="detail-summary-value">${escHtml(ratioLabel)}</div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Agent</th>
            <th>Jumlah Menyebut</th>
            <th>Total Rekaman</th>
            <th>Rasio</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((row) => `
            <tr>
              <td>${escHtml(row.agent)}</td>
              <td>${fmtNum(row.hit)}</td>
              <td>${fmtNum(row.total)}</td>
              <td>${escHtml(row.ratio)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  if ($('modal-body')) $('modal-body').innerHTML = html;
  $('agent-modal-overlay')?.classList.add('open');
}

function renderPriorityModalContent(data) {
  const total = data?.total || 0;
  let html = `<p style="font-size:12px;color:#475569;margin-bottom:16px">${escHtml(data?.agent || '-')} — ${total} call</p>`;

  if (!data?.records || data.records.length === 0) {
    html += '<p style="color:#94a3b8">Tidak ada data.</p>';
  } else {
    const preferredKeys = ['tanggal', 'agent', 'call_result', 'id_customer', 'Aspek Jarang Disebut', 'Aspek Sudah Disebut'];
    const allKeys = Object.keys(data.records[0]);
    const keys = preferredKeys.filter((k) => allKeys.includes(k));
    html += '<div class="table-wrap"><table>';
    html += '<thead><tr>' + keys.map((k) => `<th>${escHtml(k)}</th>`).join('') + '</tr></thead>';
    html += '<tbody>' + data.records.slice(0, 200).map((r) => `
      <tr>
        ${keys.map((k) => `<td style="font-size:12px">${escHtml(r[k] != null ? String(r[k]) : '-')}</td>`).join('')}
      </tr>
    `).join('') + '</tbody></table></div>';
  }

  if ($('modal-body')) $('modal-body').innerHTML = html;
}

function renderModalContent(agentName, data) {
  const total = data?.total || 0;
  let html = `<p style="font-size:12px;color:#475569;margin-bottom:16px">${escHtml(agentName)} — ${total} rekaman</p>`;

  if (!data?.records || data.records.length === 0) {
    html += '<p style="color:#94a3b8">Tidak ada data.</p>';
  } else {
    // Hanya tampilkan kolom info dasar — kolom scoring (0/1) dihilangkan
    const INFO_KEYS = ['tanggal', 'agent', 'call_result'];
    const allKeys = Object.keys(data.records[0]);
    const keys = INFO_KEYS.filter((k) => allKeys.includes(k));

    const labelMap = {
      tanggal: 'Tanggal',
      agent: 'Agent',
      call_result: 'Call Result',
    };

    html += '<div class="table-wrap"><table>';
    html += '<thead><tr>' + keys.map((k) => `<th>${escHtml(labelMap[k] || k)}</th>`).join('') + '</tr></thead>';
    html += '<tbody>' + data.records.slice(0, 200).map((r) => `
      <tr>
        ${keys.map((k) => `<td style="font-size:12px">${escHtml(r[k] != null ? String(r[k]) : '-')}</td>`).join('')}
      </tr>
    `).join('') + '</tbody></table></div>';
  }

  if ($('modal-body')) $('modal-body').innerHTML = html;
}

$('modal-close')?.addEventListener('click', () => {
  $('agent-modal-overlay')?.classList.remove('open');
});

$('agent-modal-overlay')?.addEventListener('click', (e) => {
  if (e.target === $('agent-modal-overlay')) {
    $('agent-modal-overlay').classList.remove('open');
  }
});

// =====================
// INIT
// =====================
(function init() {
  hideLoader();
  setMode('TL');
  resetDashboardView();
})();

window.addEventListener('resize', () => scheduleChartResize(140));
window.addEventListener('orientationchange', () => scheduleChartResize(180));
window.addEventListener('focus', () => scheduleChartResize(120));
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    scheduleChartResize(180);
  }
});

window.openAgentModal = openAgentModal;
window.openPriorityAgentModal = openPriorityAgentModal;
window.openAspectBreakdownModal = openAspectBreakdownModal;

// =====================
// UI ENHANCEMENTS
// =====================

// ---------- Hamburger / Sidebar mobile ----------
(function initSidebarToggle() {
  const hamburger = document.getElementById('hamburger-btn');
  const sidebar   = document.getElementById('sidebar');
  const backdrop  = document.getElementById('sidebar-backdrop');
  const closeBtn  = document.getElementById('sidebar-close-btn');

  function openSidebar() {
    sidebar?.classList.add('open');
    backdrop?.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
  function closeSidebar() {
    sidebar?.classList.remove('open');
    backdrop?.classList.remove('active');
    document.body.style.overflow = '';
  }

  hamburger?.addEventListener('click', openSidebar);
  closeBtn?.addEventListener('click', closeSidebar);
  backdrop?.addEventListener('click', closeSidebar);
})();


// ---------- Enhanced Loader with staged progress (no loop) ----------
const LOADER_STAGE_TEXT = {
  generic: [
    { max: 25, text: 'Menyiapkan permintaan...' },
    { max: 50, text: 'Mengambil data...' },
    { max: 75, text: 'Memproses data...' },
    { max: 99, text: 'Menyusun tampilan...' },
  ],
  upload: [
    { max: 25, text: 'Mengupload file...' },
    { max: 45, text: 'Membaca file Excel...' },
    { max: 65, text: 'Memvalidasi struktur data...' },
    { max: 85, text: 'Memproses dashboard...' },
    { max: 99, text: 'Menyusun hasil akhir...' },
  ],
};

let _loaderProgress = 0;
let _loaderStage = 'generic';
let _loaderTailTimer = null;
let _loaderHideTimer = null;
let _loaderFrame = null;
let _loaderTextTimer = null;
let _loaderSessionId = 0;

function inferLoaderStage(msg = '', options = {}) {
  if (options.stage) return options.stage;
  const text = String(msg || '').toLowerCase();
  if (text.includes('upload')) return 'upload';
  return 'generic';
}

function getLoaderTextByProgress(progress, stage = 'generic', fallback = '') {
  const steps = LOADER_STAGE_TEXT[stage] || LOADER_STAGE_TEXT.generic;
  const step = steps.find((item) => progress <= item.max) || steps[steps.length - 1];
  return step?.text || fallback || 'Memproses data...';
}

function stopLoaderFrame() {
  if (_loaderFrame) {
    cancelAnimationFrame(_loaderFrame);
    _loaderFrame = null;
  }
}

function stopLoaderTail() {
  if (_loaderTailTimer) {
    clearInterval(_loaderTailTimer);
    _loaderTailTimer = null;
  }
}

function stopLoaderTextTimer() {
  if (_loaderTextTimer) {
    clearTimeout(_loaderTextTimer);
    _loaderTextTimer = null;
  }
}

function clearLoaderTimers() {
  stopLoaderFrame();
  stopLoaderTail();
  stopLoaderTextTimer();
  if (_loaderHideTimer) {
    clearTimeout(_loaderHideTimer);
    _loaderHideTimer = null;
  }
}

function getLoaderElements() {
  return {
    overlay: $('loader-overlay'),
    fillEl: $('loader-progress-fill'),
    pctEl: $('loader-progress-pct'),
    textEl: $('loader-text'),
  };
}

function setLoaderVisual(progress, { text, allowDecrease = false, sessionId = _loaderSessionId } = {}) {
  if (sessionId !== _loaderSessionId) return;

  const { fillEl, pctEl, textEl } = getLoaderElements();
  const rawProgress = Math.max(0, Math.min(100, Number(progress) || 0));
  const safeProgress = allowDecrease ? rawProgress : Math.max(_loaderProgress, rawProgress);
  _loaderProgress = safeProgress;

  if (fillEl) fillEl.style.width = `${safeProgress}%`;
  if (pctEl) pctEl.textContent = `${Math.round(safeProgress)}%`;

  const nextText = text || getLoaderTextByProgress(safeProgress, _loaderStage);
  if (textEl && textEl.textContent !== nextText) {
    stopLoaderTextTimer();
    textEl.classList.add('fade-out');
    _loaderTextTimer = setTimeout(() => {
      if (sessionId !== _loaderSessionId || !textEl) return;
      textEl.textContent = nextText;
      textEl.classList.remove('fade-out');
      _loaderTextTimer = null;
    }, 140);
  } else if (textEl && !text) {
    textEl.textContent = nextText;
    textEl.classList.remove('fade-out');
  }
}

function animateLoaderTo(target, { duration = 360, text, sessionId = _loaderSessionId } = {}) {
  stopLoaderFrame();
  const start = _loaderProgress;
  const end = Math.max(start, Math.min(100, Number(target) || 0));
  const startedAt = performance.now();

  function tick(now) {
    if (sessionId !== _loaderSessionId) {
      _loaderFrame = null;
      return;
    }
    const elapsed = now - startedAt;
    const ratio = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - ratio, 3);
    const current = start + ((end - start) * eased);
    setLoaderVisual(current, { text, sessionId });
    if (ratio < 1) {
      _loaderFrame = requestAnimationFrame(tick);
    } else {
      _loaderFrame = null;
    }
  }

  _loaderFrame = requestAnimationFrame(tick);
}

function beginLoaderTail(from = _loaderProgress, to = 92, sessionId = _loaderSessionId) {
  stopLoaderTail();
  if (sessionId !== _loaderSessionId) return;
  if (from > _loaderProgress) {
    setLoaderVisual(from, { sessionId });
  }
  _loaderTailTimer = setInterval(() => {
    if (sessionId !== _loaderSessionId) {
      stopLoaderTail();
      return;
    }
    if (_loaderProgress >= to) {
      stopLoaderTail();
      return;
    }
    const remaining = to - _loaderProgress;
    const step = Math.max(0.4, remaining * 0.12);
    setLoaderVisual(Math.min(to, _loaderProgress + step), { sessionId });
  }, 220);
}

function startLoaderAnimation(initialMsg, options = {}) {
  const { overlay } = getLoaderElements();
  if (!overlay) return;

  clearLoaderTimers();
  overlay.classList.remove('hidden');

  _loaderSessionId += 1;
  const sessionId = _loaderSessionId;
  _loaderStage = inferLoaderStage(initialMsg, options);
  const reset = options.reset !== false;

  if (reset) {
    _loaderProgress = 0;
    setLoaderVisual(0, {
      text: initialMsg || getLoaderTextByProgress(0, _loaderStage),
      allowDecrease: true,
      sessionId,
    });
  } else {
    setLoaderVisual(_loaderProgress, {
      text: initialMsg || getLoaderTextByProgress(_loaderProgress, _loaderStage),
      sessionId,
    });
  }

  if (_loaderStage !== 'upload') {
    beginLoaderTail(Math.max(_loaderProgress, 6), 92, sessionId);
  }
}

function finishLoaderAnimation(options = {}) {
  const { overlay, textEl } = getLoaderElements();
  if (!overlay) return;
  const sessionId = _loaderSessionId;

  if (options.immediate) {
    clearLoaderTimers();
    overlay.classList.add('hidden');
    return;
  }

  clearLoaderTimers();
  animateLoaderTo(100, { duration: 280, text: options.message || 'Selesai!', sessionId });

  _loaderHideTimer = setTimeout(() => {
    if (sessionId !== _loaderSessionId) return;
    if (textEl) textEl.textContent = options.message || 'Selesai!';
    overlay.classList.add('hidden');
    _loaderHideTimer = null;
  }, 360);
}

function uploadFileWithProgress(formData) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const sessionId = _loaderSessionId;
    xhr.open('POST', `${API}/upload`, true);

    if (state.sessionToken) {
      xhr.setRequestHeader('X-Session-Token', state.sessionToken);
    }

    xhr.upload.addEventListener('loadstart', () => {
      if (sessionId !== _loaderSessionId) return;
      _loaderStage = 'upload';
      stopLoaderFrame();
      setLoaderVisual(1, { text: 'Mengupload file...', sessionId });
    });

    xhr.upload.addEventListener('progress', (event) => {
      if (sessionId !== _loaderSessionId || !event.lengthComputable) return;
      stopLoaderFrame();
      const uploadedPct = (event.loaded / event.total) * 100;
      const mappedPct = 1 + (uploadedPct * 0.34); // fase upload nyata mengisi sampai ~35%
      setLoaderVisual(Math.min(35, mappedPct), { sessionId });
    });

    xhr.upload.addEventListener('loadend', () => {
      if (sessionId !== _loaderSessionId) return;
      stopLoaderFrame();
      animateLoaderTo(45, { duration: 320, sessionId });
      beginLoaderTail(45, 88, sessionId);
    });

    xhr.onload = () => {
      if (sessionId !== _loaderSessionId) return;
      clearLoaderTimers();
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (!ok) {
        let message = `HTTP ${xhr.status}`;
        try {
          const parsed = JSON.parse(xhr.responseText || '{}');
          message = parsed?.detail ? parseErrorDetail(parsed.detail) : (xhr.responseText || message);
        } catch (_) {
          message = xhr.responseText || message;
        }
        reject(new Error(message));
        return;
      }

      try {
        const parsed = xhr.responseText ? JSON.parse(xhr.responseText) : {};
        setLoaderVisual(88, { sessionId });
        resolve(parsed);
      } catch (_) {
        reject(new Error('Respons upload tidak valid.'));
      }
    };

    xhr.onerror = () => {
      if (sessionId !== _loaderSessionId) return;
      clearLoaderTimers();
      reject(new Error('Gagal mengupload file ke server.'));
    };

    xhr.send(formData);
  });
}


(function bootstrapFromStorage() {
  const stored = getStoredAuth();
  if (!stored.sessionToken || !stored.role) return;
  if (stored.role === 'admin') {
    window.location.href = 'admin.html';
    return;
  }
  state.username = stored.username || null;
  state.role = stored.role || null;
  state.tlName = stored.tlName || '';
  state.sessionToken = stored.sessionToken || null;
  state.lockedTL = state.tlName || '';
  state.selectedTL = state.lockedTL || '';
  state.availableFiles = Array.isArray(stored.availableFiles) ? stored.availableFiles : [];
})();

window.addEventListener('load', async () => {
  if (!state.sessionToken || state.role === 'admin') return;
  hide($('login-page'));
  show($('app'));
  populateAvailableFiles();
  setEmptyStateMessage(`
    <div class="empty-state-card">
      <h3>Pilih data dulu</h3>
      <p>Dashboard baru akan memuat metadata dan data utama setelah Anda memilih dataset pada dropdown.</p>
    </div>
  `);
});
