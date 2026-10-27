/**
 * BAIM 330 Kaggle Tracker - Frontend Application Logic
 * Supports both Live Python Backend and Static GitHub Pages deployment.
 */

// Application State
let currentTab = 'leaderboard';
let adminToken = localStorage.getItem('baim330_admin_token') || null;
let allTeams = [];
let historyChartInstance = null;
let miniChartInstance = null;
let showInstructorLine = true;
let isStaticMode = window.location.hostname.includes('github.io') || window.location.protocol === 'file:';
let staticCache = null;

// Color Palette for teams
const TEAM_COLORS = [
  { border: '#0d9488', bg: 'rgba(13, 148, 136, 0.15)' },  // Teal
  { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },  // Amber
  { border: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)' },  // Purple
  { border: '#ec4899', bg: 'rgba(236, 72, 153, 0.15)' },  // Pink
  { border: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)' },   // Cyan
];
const INSTRUCTOR_COLOR = { border: '#1e3a8a', bg: 'rgba(30, 58, 138, 0.15)' }; // Navy Blue

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  updateAuthUI();
  refreshData();
  loadAdminSettings();
  loadTeamsList();

  // If on GitHub Pages, adjust indicator
  if (isStaticMode) {
    const hint = document.getElementById('credentials-source-hint');
    if (hint) {
      hint.textContent = 'Hosted on GitHub Pages (Public Classroom View)';
    }
  }

  // Polling: Auto-refresh leaderboard every 60 seconds
  setInterval(() => {
    if (currentTab === 'leaderboard') {
      loadLeaderboard(false);
    }
  }, 60000);
});

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  const bgColors = {
    success: 'bg-emerald-600 text-white',
    error: 'bg-rose-600 text-white',
    info: 'bg-slate-900 text-white',
    warning: 'bg-amber-600 text-white'
  };

  toast.className = `${bgColors[type] || bgColors.info} px-4 py-3 rounded-xl shadow-xl flex items-center space-x-2 text-sm font-medium animate-fadeIn transition-all pointer-events-auto`;
  toast.innerHTML = `
    <span>${message}</span>
    <button onclick="this.parentElement.remove()" class="ml-2 text-white/80 hover:text-white">&times;</button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching
function switchTab(tabName) {
  currentTab = tabName;

  const tabs = ['leaderboard', 'history', 'admin'];
  tabs.forEach(t => {
    const el = document.getElementById(`tab-${t}`);
    if (el) {
      if (t === tabName) {
        el.classList.remove('hidden');
      } else {
        el.classList.add('hidden');
      }
    }
  });

  // Nav buttons highlight (Desktop)
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('bg-amber-500', 'text-slate-950', 'shadow');
    btn.classList.add('text-slate-300');
  });

  const activeBtn = document.getElementById(`nav-tab-${tabName}`);
  if (activeBtn) {
    activeBtn.classList.add('bg-amber-500', 'text-slate-950', 'shadow');
    activeBtn.classList.remove('text-slate-300');
  }

  if (tabName === 'history') {
    loadHistory();
  } else if (tabName === 'admin') {
    if (!adminToken && !isStaticMode) {
      openModal('modal-login');
    } else {
      loadTeamsList();
      loadAdminSettings();
    }
  } else if (tabName === 'leaderboard') {
    loadLeaderboard();
  }

  if (window.lucide) lucide.createIcons();
}

// Refresh all views
function refreshData() {
  loadLeaderboard();
  loadHistory();
}

// Fetch helper that falls back to static JSON on GitHub Pages
async function fetchStaticOrApi(endpoint) {
  if (!isStaticMode) {
    try {
      const res = await fetch(endpoint);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      // Backend not running, switch to static mode
      isStaticMode = true;
    }
  }

  // Load from static data/leaderboard.json
  if (!staticCache) {
    try {
      const res = await fetch('data/leaderboard.json?v=' + Date.now());
      if (res.ok) {
        staticCache = await res.json();
      }
    } catch (err) {
      console.warn('Could not load static JSON:', err);
    }
  }

  if (staticCache) {
    if (endpoint === '/api/leaderboard') {
      return {
        competition_id: staticCache.competition_id,
        last_sync: staticCache.last_sync,
        total_teams: staticCache.total_teams,
        winner: staticCache.winner,
        standings: staticCache.standings
      };
    } else if (endpoint === '/api/history') {
      return staticCache.history || { series: [], snapshots: [] };
    } else if (endpoint === '/api/teams') {
      return { teams: staticCache.teams || [] };
    } else if (endpoint === '/api/admin/settings') {
      return {
        competition_id: staticCache.competition_id,
        kaggle_configured: true,
        kaggle_username: 'Instructor',
        credentials_source: 'GitHub Repository'
      };
    }
  }

  return null;
}

// -------------------------------------------------------------
// LEADERBOARD & WINNER SPOTLIGHT
// -------------------------------------------------------------
async function loadLeaderboard(showToastNotification = false) {
  try {
    const data = await fetchStaticOrApi('/api/leaderboard');
    if (!data) return;
    
    // Update last sync time
    const syncTimeEl = document.getElementById('last-sync-time');
    if (syncTimeEl) {
      syncTimeEl.textContent = data.last_sync || 'Not yet synced';
    }

    renderWinnerAndBenchmark(data);
    renderLeaderboardTable(data.standings);

    if (showToastNotification) {
      showToast('Leaderboard standings updated.', 'success');
    }
  } catch (err) {
    console.error('Error loading leaderboard:', err);
  }
}

function renderWinnerAndBenchmark(data) {
  const winner = data.winner;
  const standings = data.standings || [];
  const benchmark = standings.find(t => t.is_instructor);

  // 1. Winner Card
  const winnerNameEl = document.getElementById('winner-team-name');
  const winnerMembersEl = document.getElementById('winner-members');
  const winnerScoreEl = document.getElementById('winner-score');
  const winnerRankEl = document.getElementById('winner-kaggle-rank');
  const winnerSubmissionsEl = document.getElementById('winner-submissions');
  const winnerUpdateEl = document.getElementById('winner-last-update');

  if (winner && winner.best_score !== null) {
    winnerNameEl.textContent = winner.name;
    winnerMembersEl.textContent = winner.members ? `Members: ${winner.members}` : `Kaggle: ${winner.kaggle_name}`;
    winnerScoreEl.textContent = Number(winner.best_score).toFixed(5);
    winnerRankEl.textContent = winner.kaggle_rank ? `#${winner.kaggle_rank.toLocaleString()}` : 'Recorded';
    winnerSubmissionsEl.textContent = winner.submission_count || 1;
    winnerUpdateEl.textContent = `Last update recorded: ${winner.last_updated || 'Today'}`;
  } else {
    winnerNameEl.textContent = 'Competition Active';
    winnerMembersEl.textContent = 'Awaiting initial submissions from student groups';
    winnerScoreEl.textContent = '--';
    winnerRankEl.textContent = '--';
    winnerSubmissionsEl.textContent = '0';
    winnerUpdateEl.textContent = 'Syncing submissions';
  }

  // 2. Benchmark Card
  const benchNameEl = document.getElementById('benchmark-name');
  const benchDescEl = document.getElementById('benchmark-desc');
  const benchScoreEl = document.getElementById('benchmark-score');
  const benchRankEl = document.getElementById('benchmark-rank');
  const benchBeatenEl = document.getElementById('benchmark-beaten-status');

  if (benchmark && benchmark.best_score !== null) {
    benchNameEl.textContent = benchmark.name;
    benchDescEl.textContent = benchmark.members || `Instructor model (${benchmark.kaggle_name})`;
    benchScoreEl.textContent = Number(benchmark.best_score).toFixed(5);
    benchRankEl.textContent = benchmark.kaggle_rank ? `#${benchmark.kaggle_rank.toLocaleString()}` : 'Active';

    // Check if any student group beat the benchmark (lower RMSE than instructor)
    if (winner && winner.best_score && winner.best_score < benchmark.best_score) {
      benchBeatenEl.innerHTML = `<span class="text-emerald-400 font-bold flex items-center gap-1">🏆 BEATEN by ${winner.name}!</span>`;
    } else {
      benchBeatenEl.textContent = 'Not yet beaten by students';
      benchBeatenEl.className = 'font-bold text-amber-400';
    }
  } else {
    benchScoreEl.textContent = '--';
    benchRankEl.textContent = '--';
    benchBeatenEl.textContent = 'Benchmark not set';
  }

  if (window.lucide) lucide.createIcons();
}

function renderLeaderboardTable(standings) {
  const tbody = document.getElementById('leaderboard-tbody');
  if (!tbody) return;

  if (!standings || standings.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center py-10 text-slate-400">
          No teams currently configured.
        </td>
      </tr>
    `;
    return;
  }

  let html = '';
  standings.forEach(team => {
    // Rank Badge
    let rankBadge = '';
    if (team.is_instructor) {
      rankBadge = `<span class="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold badge-instructor" title="Instructor Benchmark">BENCH</span>`;
    } else if (team.class_rank === 1) {
      rankBadge = `<span class="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-black badge-gold">🥇 1</span>`;
    } else if (team.class_rank === 2) {
      rankBadge = `<span class="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-black badge-silver">🥈 2</span>`;
    } else if (team.class_rank === 3) {
      rankBadge = `<span class="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-black badge-bronze">🥉 3</span>`;
    } else if (team.class_rank) {
      rankBadge = `<span class="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold bg-slate-200 text-slate-700">#${team.class_rank}</span>`;
    } else {
      rankBadge = `<span class="text-xs text-slate-400 font-medium">--</span>`;
    }

    // Trend Indicator
    let trendBadge = '';
    if (team.trend === 'improved') {
      trendBadge = `
        <span class="inline-flex items-center text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200" title="Improved by ${Math.abs(team.delta).toFixed(5)} RMSE">
          <i data-lucide="trending-down" class="w-3.5 h-3.5 mr-0.5"></i>
          <span>-${Math.abs(team.delta).toFixed(4)}</span>
        </span>
      `;
    } else if (team.trend === 'regressed') {
      trendBadge = `
        <span class="inline-flex items-center text-xs font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200" title="Score increased by ${Math.abs(team.delta).toFixed(5)}">
          <i data-lucide="trending-up" class="w-3.5 h-3.5 mr-0.5"></i>
          <span>+${Math.abs(team.delta).toFixed(4)}</span>
        </span>
      `;
    } else {
      trendBadge = `<span class="text-slate-400 text-xs font-medium">&mdash;</span>`;
    }

    const scoreDisplay = team.best_score !== null 
      ? `<span class="font-mono font-bold text-slate-900 text-base">${Number(team.best_score).toFixed(5)}</span>`
      : `<span class="text-slate-400 font-mono">Pending</span>`;

    const kaggleRankDisplay = team.kaggle_rank 
      ? `<span class="font-mono font-semibold text-slate-700">#${team.kaggle_rank.toLocaleString()}</span>`
      : `<span class="text-slate-400 font-mono">&mdash;</span>`;

    html += `
      <tr class="transition-colors ${team.is_instructor ? 'bg-blue-50/40' : ''}">
        <td class="py-4 px-4 text-center">${rankBadge}</td>
        <td class="py-4 px-4">
          <div class="font-bold text-slate-900 flex items-center space-x-2">
            <span>${escapeHtml(team.name)}</span>
            ${team.is_instructor ? '<span class="text-[10px] bg-blue-100 text-blue-800 font-bold px-1.5 py-0.2 rounded">Instructor</span>' : ''}
          </div>
          ${team.members ? `<div class="text-xs text-slate-500 mt-0.5">${escapeHtml(team.members)}</div>` : ''}
        </td>
        <td class="py-4 px-4">
          <a href="https://www.kaggle.com/${encodeURIComponent(team.kaggle_name)}" target="_blank" class="inline-flex items-center space-x-1 text-sky-600 hover:text-sky-800 font-mono text-xs hover:underline">
            <span>${escapeHtml(team.kaggle_name)}</span>
            <i data-lucide="external-link" class="w-3 h-3"></i>
          </a>
        </td>
        <td class="py-4 px-4 text-right">${scoreDisplay}</td>
        <td class="py-4 px-4 text-center">${trendBadge}</td>
        <td class="py-4 px-4 text-center">${kaggleRankDisplay}</td>
        <td class="py-4 px-4 text-center">
          <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
            ${team.submission_count}
          </span>
        </td>
        <td class="py-4 px-4 text-right text-xs text-slate-500 font-mono">
          ${team.last_updated ? team.last_updated.split(' ')[0] : '&mdash;'}
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// -------------------------------------------------------------
// TIME SERIES HISTORY & CHARTS
// -------------------------------------------------------------
async function loadHistory() {
  try {
    const data = await fetchStaticOrApi('/api/history');
    if (!data) return;

    renderHistoryChart(data);
    renderMiniChart(data);
    renderHistoryTable(data.snapshots);
  } catch (err) {
    console.error('Error loading history:', err);
  }
}

function renderHistoryChart(data) {
  const canvas = document.getElementById('historyChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (historyChartInstance) {
    historyChartInstance.destroy();
  }

  const datasets = [];
  let colorIdx = 0;

  (data.series || []).forEach(item => {
    if (item.is_instructor && !showInstructorLine) return;

    const color = item.is_instructor ? INSTRUCTOR_COLOR : TEAM_COLORS[colorIdx % TEAM_COLORS.length];
    if (!item.is_instructor) colorIdx++;

    datasets.push({
      label: item.team_name,
      data: item.points.map(p => ({
        x: p.x,
        y: p.y,
        kaggle_rank: p.kaggle_rank,
        notes: p.notes
      })),
      borderColor: color.border,
      backgroundColor: color.bg,
      borderWidth: item.is_instructor ? 2.5 : 3,
      borderDash: item.is_instructor ? [6, 4] : [],
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: color.border,
      tension: 0.25,
      fill: false
    });
  });

  historyChartInstance = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'nearest',
        axis: 'x',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            usePointStyle: true,
            boxWidth: 8,
            font: { size: 12, weight: 'bold' }
          }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleFont: { size: 13, weight: 'bold' },
          bodyFont: { size: 12 },
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: function(context) {
              const raw = context.raw;
              let label = `${context.dataset.label}: ${Number(raw.y).toFixed(5)} RMSE`;
              if (raw.kaggle_rank) {
                label += ` (Rank: #${raw.kaggle_rank.toLocaleString()})`;
              }
              return label;
            },
            afterLabel: function(context) {
              const notes = context.raw.notes;
              return notes ? `Note: ${notes}` : '';
            }
          }
        }
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'day',
            displayFormats: { day: 'MMM d' },
            tooltipFormat: 'yyyy-MM-dd HH:mm'
          },
          grid: { color: 'rgba(226, 232, 240, 0.6)' },
          title: { display: true, text: 'Date of Submission', font: { weight: 'bold', size: 11 } }
        },
        y: {
          grid: { color: 'rgba(226, 232, 240, 0.6)' },
          title: { display: true, text: 'RMSE Score (Lower is Better)', font: { weight: 'bold', size: 11 } }
        }
      }
    }
  });
}

function renderMiniChart(data) {
  const canvas = document.getElementById('miniChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (miniChartInstance) {
    miniChartInstance.destroy();
  }

  const datasets = [];
  let colorIdx = 0;

  (data.series || []).forEach(item => {
    const color = item.is_instructor ? INSTRUCTOR_COLOR : TEAM_COLORS[colorIdx % TEAM_COLORS.length];
    if (!item.is_instructor) colorIdx++;

    datasets.push({
      label: item.team_name,
      data: item.points.map(p => ({ x: p.x, y: p.y })),
      borderColor: color.border,
      borderWidth: 2,
      borderDash: item.is_instructor ? [4, 4] : [],
      pointRadius: 3,
      tension: 0.25,
      fill: false
    });
  });

  miniChartInstance = new Chart(ctx, {
    type: 'line',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 6, font: { size: 10 } } }
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'day', displayFormats: { day: 'MMM d' } },
          grid: { display: false }
        },
        y: {
          grid: { color: 'rgba(226, 232, 240, 0.4)' },
          ticks: { font: { size: 10 } }
        }
      }
    }
  });
}

function toggleInstructorLine() {
  showInstructorLine = !showInstructorLine;
  const btnText = document.getElementById('toggle-instructor-text');
  if (btnText) {
    btnText.textContent = showInstructorLine ? 'Hide Benchmark' : 'Show Benchmark';
  }
  loadHistory();
}

function resetChartZoom() {
  if (historyChartInstance) {
    historyChartInstance.reset();
  }
}

function renderHistoryTable(snapshots) {
  const tbody = document.getElementById('history-tbody');
  const badge = document.getElementById('total-snapshots-badge');
  if (!tbody) return;

  if (badge) {
    badge.textContent = `${snapshots ? snapshots.length : 0} Submissions Logged`;
  }

  if (!snapshots || snapshots.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="text-center py-8 text-slate-400">
          No historical scores recorded yet.
        </td>
      </tr>
    `;
    return;
  }

  let html = '';
  snapshots.forEach(s => {
    const isAdmin = Boolean(adminToken);
    html += `
      <tr>
        <td class="py-3 px-4 font-mono text-xs text-slate-600">${s.recorded_at}</td>
        <td class="py-3 px-4 font-bold text-slate-800">
          ${escapeHtml(s.team_name)}
          ${s.is_instructor ? '<span class="ml-1 text-[10px] bg-blue-100 text-blue-800 px-1 rounded font-bold">Benchmark</span>' : ''}
        </td>
        <td class="py-3 px-4 text-right font-mono font-bold text-slate-900">${Number(s.score).toFixed(5)}</td>
        <td class="py-3 px-4 text-center font-mono text-xs">${s.kaggle_rank ? `#${s.kaggle_rank.toLocaleString()}` : '&mdash;'}</td>
        <td class="py-3 px-4 text-xs text-slate-600">${escapeHtml(s.notes || '&mdash;')}</td>
        <td class="py-3 px-4 text-center">
          <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded ${s.source && s.source.includes('manual') ? 'bg-amber-100 text-amber-800' : 'bg-sky-100 text-sky-800'}">
            ${s.source ? s.source.split(' ')[0] : 'Kaggle'}
          </span>
        </td>
        <td class="py-3 px-4 text-center admin-only-col ${isAdmin ? '' : 'hidden'}">
          <button onclick="handleDeleteSnapshot(${s.id})" class="text-rose-500 hover:text-rose-700 p-1 rounded" title="Delete snapshot">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = html;
  if (window.lucide) lucide.createIcons();
}

// -------------------------------------------------------------
// ADMINISTRATIVE PANEL & ACTIONS
// -------------------------------------------------------------
function updateAuthUI() {
  const btn = document.getElementById('admin-auth-btn');
  const text = document.getElementById('admin-auth-text');
  const adminCols = document.querySelectorAll('.admin-only-col');

  if (adminToken) {
    if (text) text.textContent = 'Admin Logout';
    if (btn) btn.classList.add('border-emerald-500/50', 'bg-emerald-950/30');
    adminCols.forEach(col => col.classList.remove('hidden'));
  } else {
    if (text) text.textContent = 'Admin Login';
    if (btn) btn.classList.remove('border-emerald-500/50', 'bg-emerald-950/30');
    adminCols.forEach(col => col.classList.add('hidden'));
  }
  if (window.lucide) lucide.createIcons();
}

function handleAdminBtnClick() {
  if (adminToken) {
    adminToken = null;
    localStorage.removeItem('baim330_admin_token');
    updateAuthUI();
    showToast('Logged out of admin panel.', 'info');
    if (currentTab === 'admin') {
      switchTab('leaderboard');
    }
  } else {
    openModal('modal-login');
  }
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const password = document.getElementById('login-password').value;

  if (isStaticMode) {
    // If in static GitHub Pages mode, simple client check for demo/management
    if (password === 'baim330admin') {
      adminToken = 'gh_pages_admin_token';
      localStorage.setItem('baim330_admin_token', adminToken);
      closeModal('modal-login');
      document.getElementById('login-password').value = '';
      updateAuthUI();
      showToast('Admin access granted on GitHub Pages.', 'success');
      switchTab('admin');
      return;
    }
  }

  try {
    const res = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });
    const data = await res.json();

    if (data.success) {
      adminToken = data.token;
      localStorage.setItem('baim330_admin_token', adminToken);
      closeModal('modal-login');
      document.getElementById('login-password').value = '';
      updateAuthUI();
      showToast('Admin access granted.', 'success');
      switchTab('admin');
    } else {
      showToast(data.error || 'Invalid admin password', 'error');
    }
  } catch (err) {
    showToast('Failed to authenticate: ' + err.message, 'error');
  }
}

// Trigger Kaggle update
async function triggerKaggleUpdate() {
  if (!adminToken) {
    openModal('modal-login');
    return;
  }

  if (isStaticMode) {
    showToast('On GitHub Pages, click "Update Scores" from your local machine or trigger GitHub Actions.', 'info');
    return;
  }

  const btn = document.getElementById('admin-update-scores-btn');
  const spinner = document.getElementById('update-spinner-icon');
  const resultBox = document.getElementById('sync-result-box');

  if (spinner) spinner.classList.add('animate-spin-custom');
  if (btn) btn.disabled = true;

  try {
    showToast('Fetching latest Kaggle leaderboard...', 'info');

    const res = await fetch('/api/admin/update', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({})
    });

    const data = await res.json();

    if (data.success) {
      showToast(data.message, 'success');
      if (resultBox) {
        resultBox.className = 'mt-6 p-4 rounded-xl text-sm border bg-emerald-950/40 border-emerald-500/50 text-emerald-200 block';
        let updatedList = (data.updated_teams || []).map(t => `<b>${t.name}</b> (${t.score} RMSE)`).join(', ');
        resultBox.innerHTML = `
          <div class="font-bold flex items-center space-x-2">
            <i data-lucide="check-circle" class="w-4 h-4 text-emerald-400"></i>
            <span>${data.message}</span>
          </div>
          <div class="text-xs mt-1 text-emerald-300">Updated: ${updatedList || 'None'}</div>
        `;
      }
      refreshData();
    } else {
      showToast(data.error || 'Failed to update from Kaggle', 'warning');
      if (resultBox) {
        resultBox.className = 'mt-6 p-4 rounded-xl text-sm border bg-rose-950/40 border-rose-500/50 text-rose-200 block';
        resultBox.innerHTML = `
          <div class="font-bold flex items-center space-x-2">
            <i data-lucide="alert-triangle" class="w-4 h-4 text-rose-400"></i>
            <span>Kaggle Sync Notification</span>
          </div>
          <p class="text-xs mt-1">${data.error}</p>
        `;
      }
    }
  } catch (err) {
    showToast('Error syncing with Kaggle: ' + err.message, 'error');
  } finally {
    if (spinner) spinner.classList.remove('animate-spin-custom');
    if (btn) btn.disabled = false;
    if (window.lucide) lucide.createIcons();
  }
}

// Teams Management
async function loadTeamsList() {
  try {
    const data = await fetchStaticOrApi('/api/teams');
    allTeams = data ? data.teams || [] : [];

    const tbody = document.getElementById('admin-teams-tbody');
    const snapSelect = document.getElementById('snap-team-id');

    if (snapSelect) {
      snapSelect.innerHTML = allTeams.map(t => `
        <option value="${t.id}">${escapeHtml(t.name)} ${t.is_instructor ? '(Instructor Benchmark)' : ''}</option>
      `).join('');
    }

    if (!tbody) return;

    if (allTeams.length === 0) {
      tbody.innerHTML = `
        <tr><td colspan="5" class="text-center py-6 text-slate-400">No groups configured. Click "+ Add New Group" to begin.</td></tr>
      `;
      return;
    }

    tbody.innerHTML = allTeams.map(t => `
      <tr>
        <td class="py-3 px-4 font-bold text-slate-900">${escapeHtml(t.name)}</td>
        <td class="py-3 px-4 font-mono text-sky-600 text-xs">${escapeHtml(t.kaggle_name)}</td>
        <td class="py-3 px-4 text-xs text-slate-600">${escapeHtml(t.members || '&mdash;')}</td>
        <td class="py-3 px-4 text-center">
          <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${t.is_instructor ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-700'}">
            ${t.is_instructor ? 'Benchmark' : 'Student Group'}
          </span>
        </td>
        <td class="py-3 px-4 text-right space-x-2">
          <button onclick="editTeam(${t.id})" class="text-xs font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-lg">
            Edit
          </button>
          <button onclick="deleteTeam(${t.id}, '${escapeHtml(t.name)}')" class="text-xs font-semibold text-rose-600 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 px-2.5 py-1 rounded-lg">
            Delete
          </button>
        </td>
      </tr>
    `).join('');

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error('Error loading teams:', err);
  }
}

async function handleSaveTeam(e) {
  e.preventDefault();
  const id = document.getElementById('team-form-id').value;
  const name = document.getElementById('team-form-name').value;
  const kaggle_name = document.getElementById('team-form-kaggle').value;
  const members = document.getElementById('team-form-members').value;
  const is_instructor = document.getElementById('team-form-is-instructor').checked ? 1 : 0;

  const method = id ? 'PUT' : 'POST';
  const url = id ? `/api/admin/teams/${id}` : '/api/admin/teams';

  try {
    const res = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({ name, kaggle_name, members, is_instructor })
    });
    const data = await res.json();

    if (data.success) {
      closeModal('modal-add-team');
      showToast(data.message, 'success');
      loadTeamsList();
      refreshData();
    } else {
      showToast(data.error || 'Failed to save group', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function editTeam(id) {
  const team = allTeams.find(t => t.id === id);
  if (!team) return;

  document.getElementById('modal-team-title').textContent = 'Edit Tracked Group';
  document.getElementById('team-form-id').value = team.id;
  document.getElementById('team-form-name').value = team.name;
  document.getElementById('team-form-kaggle').value = team.kaggle_name;
  document.getElementById('team-form-members').value = team.members || '';
  document.getElementById('team-form-is-instructor').checked = Boolean(team.is_instructor);

  openModal('modal-add-team');
}

async function deleteTeam(id, name) {
  if (!confirm(`Are you sure you want to delete group "${name}" and all their recorded scores?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/admin/teams/${id}`, {
      method: 'DELETE',
      headers: { 'X-Admin-Token': adminToken }
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Group "${name}" deleted.`, 'info');
      loadTeamsList();
      refreshData();
    }
  } catch (err) {
    showToast('Failed to delete team: ' + err.message, 'error');
  }
}

// Manual Score Snapshot
async function handleSaveSnapshot(e) {
  e.preventDefault();
  const team_id = document.getElementById('snap-team-id').value;
  const score = document.getElementById('snap-score').value;
  const kaggle_rank = document.getElementById('snap-rank').value;
  const recorded_at = document.getElementById('snap-datetime').value;
  const notes = document.getElementById('snap-notes').value;

  try {
    const res = await fetch('/api/admin/snapshot', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({
        team_id,
        score,
        kaggle_rank: kaggle_rank || null,
        recorded_at: recorded_at ? recorded_at.replace('T', ' ') + ':00' : null,
        notes
      })
    });
    const data = await res.json();

    if (data.success) {
      closeModal('modal-add-snapshot');
      document.getElementById('snapshot-form').reset();
      showToast('Score snapshot recorded successfully.', 'success');
      refreshData();
    } else {
      showToast(data.error || 'Failed to save snapshot', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function handleDeleteSnapshot(snapshotId) {
  if (!confirm('Are you sure you want to delete this recorded score entry?')) return;

  try {
    const res = await fetch(`/api/admin/snapshot/${snapshotId}`, {
      method: 'DELETE',
      headers: { 'X-Admin-Token': adminToken }
    });
    const data = await res.json();
    if (data.success) {
      showToast('Snapshot entry deleted.', 'info');
      refreshData();
    }
  } catch (err) {
    showToast('Failed to delete snapshot: ' + err.message, 'error');
  }
}

// Settings & CSV Upload
async function loadAdminSettings() {
  try {
    const data = await fetchStaticOrApi('/api/admin/settings');
    if (!data) return;

    const userInp = document.getElementById('setting-kaggle-user');
    const pill = document.getElementById('kaggle-status-pill');
    const hint = document.getElementById('credentials-source-hint');

    if (userInp && data.kaggle_username) {
      userInp.value = data.kaggle_username;
    }

    if (pill) {
      if (data.kaggle_configured) {
        pill.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300';
        pill.textContent = 'Configured & Active';
      } else {
        pill.className = 'text-xs font-bold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300';
        pill.textContent = 'Credentials Required';
      }
    }

    if (hint) {
      hint.textContent = data.credentials_source ? `Loaded via: ${data.credentials_source}` : '';
    }
  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

async function handleSaveKaggleSettings(e) {
  e.preventDefault();
  if (!adminToken) return openModal('modal-login');

  const username = document.getElementById('setting-kaggle-user').value;
  const key = document.getElementById('setting-kaggle-key').value;

  try {
    const res = await fetch('/api/admin/settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({
        kaggle_username: username,
        kaggle_key: key
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Kaggle credentials saved.', 'success');
      document.getElementById('setting-kaggle-key').value = '';
      loadAdminSettings();
    } else {
      showToast(data.error || 'Failed to save settings', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function handleCSVUpload(input) {
  if (!input.files || input.files.length === 0) return;
  if (!adminToken) {
    openModal('modal-login');
    return;
  }

  const file = input.files[0];
  const reader = new FileReader();

  reader.onload = async (e) => {
    const csvContent = e.target.result;
    showToast('Processing uploaded CSV...', 'info');

    try {
      const res = await fetch('/api/admin/upload-csv', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken
        },
        body: JSON.stringify({ csv_content: csvContent })
      });
      const data = await res.json();

      if (data.success) {
        showToast(data.message, 'success');
        refreshData();
      } else {
        showToast(data.error || 'Could not parse CSV', 'error');
      }
    } catch (err) {
      showToast('CSV upload error: ' + err.message, 'error');
    }
  };

  reader.readAsText(file);
}

async function handleSeedDemo() {
  if (!adminToken) return openModal('modal-login');
  if (!confirm('This will seed realistic milestone score history for the groups and benchmark. Proceed?')) {
    return;
  }

  try {
    const res = await fetch('/api/admin/seed-demo', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      }
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message, 'success');
      refreshData();
    }
  } catch (err) {
    showToast('Failed to seed demo data: ' + err.message, 'error');
  }
}

async function handleChangePassword(e) {
  e.preventDefault();
  const newPassword = document.getElementById('new-password').value;

  try {
    const res = await fetch('/api/admin/settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': adminToken
      },
      body: JSON.stringify({ new_admin_password: newPassword })
    });
    const data = await res.json();
    if (data.success) {
      if (data.token) {
        adminToken = data.token;
        localStorage.setItem('baim330_admin_token', adminToken);
      }
      closeModal('modal-change-password');
      document.getElementById('password-form').reset();
      showToast('Admin password updated successfully.', 'success');
    }
  } catch (err) {
    showToast('Error updating password: ' + err.message, 'error');
  }
}

// Modal Helpers
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
  if (id === 'modal-add-team') {
    document.getElementById('team-form').reset();
    document.getElementById('team-form-id').value = '';
    document.getElementById('modal-team-title').textContent = 'Add New Group to Follow';
  }
  if (window.lucide) lucide.createIcons();
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
