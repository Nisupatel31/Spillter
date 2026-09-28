// Spillter Frontend Application Logic

let currentTripId = null;
let currentTrip = null;
let trips = [];
let members = [];
let expenses = [];
let currentSplitType = 'equal';
let editingExpenseId = null;
let currentUser = null;
let currentDashboardData = null;

// --- THEME MANAGEMENT (DARK / LIGHT MODE) ---
function initTheme() {
  const saved = localStorage.getItem('spillter_theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = saved === 'dark' || (!saved && prefersDark);
  if (isDark) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  updateThemeUI(isDark);
}

function toggleTheme() {
  const isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('spillter_theme', isDark ? 'dark' : 'light');
  updateThemeUI(isDark);
  if (currentDashboardData) {
    renderCharts(currentDashboardData);
  }
}

function updateThemeUI(isDark) {
  const icon = document.getElementById('themeIcon');
  if (icon) {
    icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
    if (window.lucide) lucide.createIcons();
  }
}

// Initial theme bootstrap
initTheme();

// Fuel & Mileage state
let vehicleCatalogs = null;
let currentTripVehicle = null;
let currentFuelLogs = [];
let currentMileageSummary = null;

// Chart instances
let categoryChart = null;
let memberSpendChart = null;
let dailyTrendChart = null;

// Category icons & styling
const CATEGORY_META = {
  Stay: { icon: 'hotel', label: 'Stay', color: '#6366F1' },
  Food: { icon: 'utensils', label: 'Food', color: '#EC4899' },
  Travel: { icon: 'car', label: 'Travel', color: '#F59E0B' },
  Activities: { icon: 'waves', label: 'Activities', color: '#06B6D4' },
  Sightseeing: { icon: 'camera', label: 'Sightseeing', color: '#8B5CF6' },
  Shopping: { icon: 'shopping-bag', label: 'Shopping', color: '#10B981' },
  Misc: { icon: 'box', label: 'Misc', color: '#64748B' }
};

// Numeric input sanitization (prevents non-numeric characters and ensures clean decimal format)
function validateDecimalInput(el) {
  if (!el) return;
  let val = el.value.replace(/[^0-9.]/g, '');
  const parts = val.split('.');
  if (parts.length > 2) {
    val = parts[0] + '.' + parts.slice(1).join('');
  }
  el.value = val;
}

// --- AUTH HELPERS & STATE ---
async function authFetch(url, options = {}) {
  const token = localStorage.getItem('spillter_token');
  const headers = options.headers ? { ...options.headers } : {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    if (!url.includes('/api/auth/login') && !url.includes('/api/auth/signup')) {
      localStorage.removeItem('spillter_token');
      currentUser = null;
      updateUserUI(null);
      openAuthModal();
    }
  }
  return response;
}

async function checkAuth() {
  const token = localStorage.getItem('spillter_token');
  if (!token) {
    updateUserUI(null);
    openAuthModal();
    return false;
  }

  try {
    const res = await authFetch('/api/auth/me');
    if (res.ok) {
      currentUser = await res.json();
      updateUserUI(currentUser);
      closeModal('authModal');
      return true;
    } else {
      localStorage.removeItem('spillter_token');
      currentUser = null;
      updateUserUI(null);
      openAuthModal();
      return false;
    }
  } catch (err) {
    console.error('Auth check error:', err);
    openAuthModal();
    return false;
  }
}

function updateUserUI(user) {
  const profileHeader = document.getElementById('userProfileHeader');
  const navLoginBtn = document.getElementById('navLoginBtn');
  const nameEl = document.getElementById('userNameHeader');
  const emailEl = document.getElementById('userEmailHeader');
  const avatarEl = document.getElementById('userAvatarPill');

  if (user && user.name) {
    if (profileHeader) profileHeader.classList.remove('hidden');
    if (navLoginBtn) navLoginBtn.classList.add('hidden');
    if (nameEl) nameEl.innerText = user.name;
    if (emailEl) emailEl.innerText = user.email;
    if (avatarEl) avatarEl.innerText = user.name.charAt(0).toUpperCase();
  } else {
    if (profileHeader) profileHeader.classList.add('hidden');
    if (navLoginBtn) navLoginBtn.classList.remove('hidden');
  }
}

// Password Visibility Toggle (Show / Hide Password)
function togglePasswordVisibility(inputId, iconId) {
  const input = document.getElementById(inputId);
  const icon = document.getElementById(iconId);
  if (!input) return;
  const isPassword = input.type === 'password';
  input.type = isPassword ? 'text' : 'password';
  if (icon) {
    icon.setAttribute('data-lucide', isPassword ? 'eye-off' : 'eye');
    if (window.lucide) lucide.createIcons();
  }
}

function openAuthModal() {
  const modal = document.getElementById('authModal');
  if (modal) modal.classList.remove('hidden');
  const alertBox = document.getElementById('authAlert');
  if (alertBox) alertBox.classList.add('hidden');
  switchAuthTab('login');
  lucide.createIcons();
}

function switchAuthTab(tab) {
  const tabLogin = document.getElementById('tabBtnLogin');
  const tabSignup = document.getElementById('tabBtnSignup');
  const tabsNav = document.getElementById('authTabsNav');
  const loginForm = document.getElementById('loginForm');
  const signupForm = document.getElementById('signupForm');
  const forgotForm = document.getElementById('forgotPasswordForm');
  const alertBox = document.getElementById('authAlert');
  const titleEl = document.getElementById('authModalTitle');
  const subtitleEl = document.getElementById('authModalSubtitle');

  if (alertBox) alertBox.classList.add('hidden');

  if (tab === 'login') {
    if (tabsNav) tabsNav.classList.remove('hidden');
    if (tabLogin) tabLogin.className = 'py-2 text-xs font-bold rounded-xl transition bg-white dark:bg-slate-900 text-brand-700 dark:text-brand-400 shadow-xs';
    if (tabSignup) tabSignup.className = 'py-2 text-xs font-bold rounded-xl transition text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white';
    if (titleEl) titleEl.innerText = 'Welcome to Spillter';
    if (subtitleEl) subtitleEl.innerText = 'Travel expense tracking & group settlement made effortless';
    if (loginForm) loginForm.classList.remove('hidden');
    if (signupForm) signupForm.classList.add('hidden');
    if (forgotForm) forgotForm.classList.add('hidden');
  } else if (tab === 'signup') {
    if (tabsNav) tabsNav.classList.remove('hidden');
    if (tabSignup) tabSignup.className = 'py-2 text-xs font-bold rounded-xl transition bg-white dark:bg-slate-900 text-brand-700 dark:text-brand-400 shadow-xs';
    if (tabLogin) tabLogin.className = 'py-2 text-xs font-bold rounded-xl transition text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white';
    if (titleEl) titleEl.innerText = 'Create an Account';
    if (subtitleEl) subtitleEl.innerText = 'Join Spillter to track expenses, scan bills, and split trips';
    if (signupForm) signupForm.classList.remove('hidden');
    if (loginForm) loginForm.classList.add('hidden');
    if (forgotForm) forgotForm.classList.add('hidden');
  } else if (tab === 'forgot') {
    if (tabsNav) tabsNav.classList.add('hidden');
    if (titleEl) titleEl.innerText = 'Reset Password';
    if (subtitleEl) subtitleEl.innerText = 'Enter your email and choose a new password';
    if (loginForm) loginForm.classList.add('hidden');
    if (signupForm) signupForm.classList.add('hidden');
    if (forgotForm) {
      forgotForm.classList.remove('hidden');
      const currentEmail = document.getElementById('loginEmail')?.value.trim();
      const resetEmailInp = document.getElementById('resetEmail');
      if (resetEmailInp && currentEmail) {
        resetEmailInp.value = currentEmail;
      }
    }
  }
  lucide.createIcons();
}

function showAuthAlert(msg) {
  const alertBox = document.getElementById('authAlert');
  const msgEl = document.getElementById('authAlertMsg');
  if (alertBox && msgEl) {
    msgEl.innerText = msg;
    alertBox.classList.remove('hidden');
  }
}

async function handleLoginSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (res.ok) {
      localStorage.setItem('spillter_token', data.token);
      currentUser = data.user;
      updateUserUI(currentUser);
      closeModal('authModal');
      showToast(`Welcome back, ${data.user.name}! 👋`);
      await loadTrips();
    } else {
      showAuthAlert(data.detail || 'Invalid email or password');
    }
  } catch (err) {
    console.error(err);
    showAuthAlert('Unable to connect to server');
  }
}

async function handleSignupSubmit(e) {
  e.preventDefault();
  const name = document.getElementById('signupName').value.trim();
  const email = document.getElementById('signupEmail').value.trim();
  const mobile = document.getElementById('signupPhone').value.trim();
  const password = document.getElementById('signupPassword').value;

  try {
    const res = await fetch('/api/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, mobile, password })
    });

    const data = await res.json();
    if (res.ok) {
      localStorage.setItem('spillter_token', data.token);
      currentUser = data.user;
      updateUserUI(currentUser);
      closeModal('authModal');
      showToast(`Account created! Welcome, ${data.user.name}! 🎉`);
      await loadTrips();
    } else {
      showAuthAlert(data.detail || 'Registration failed');
    }
  } catch (err) {
    console.error(err);
    showAuthAlert('Unable to connect to server');
  }
}

async function handleResetPasswordSubmit(e) {
  e.preventDefault();
  const email = document.getElementById('resetEmail').value.trim();
  const newPassword = document.getElementById('resetNewPassword').value;
  const confirmPassword = document.getElementById('resetConfirmPassword').value;

  if (newPassword.length < 4) {
    showAuthAlert('Password must be at least 4 characters long');
    return;
  }

  if (newPassword !== confirmPassword) {
    showAuthAlert('Passwords do not match. Please re-type your confirm password.');
    return;
  }

  const submitBtn = document.getElementById('resetSubmitBtn');
  const originalBtnHtml = submitBtn ? submitBtn.innerHTML : '';
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = 'Updating Password...';
  }

  try {
    const res = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, new_password: newPassword })
    });

    const data = await res.json();
    if (res.ok) {
      localStorage.setItem('spillter_token', data.token);
      currentUser = data.user;
      updateUserUI(currentUser);
      closeModal('authModal');
      showToast('Password updated successfully! Welcome back! 🎉');
      document.getElementById('forgotPasswordForm').reset();
      switchAuthTab('login');
      await loadTrips();
    } else {
      showAuthAlert(data.detail || 'Failed to reset password');
    }
  } catch (err) {
    console.error(err);
    showAuthAlert('Unable to connect to server. Please try again.');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnHtml;
      lucide.createIcons();
    }
  }
}

async function handleLogout() {
  try {
    await authFetch('/api/auth/logout', { method: 'POST' });
  } catch (err) {
    console.error(err);
  }
  localStorage.removeItem('spillter_token');
  currentUser = null;
  updateUserUI(null);
  openAuthModal();
  showToast('Logged out successfully');
}

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', async () => {
  // Set today's date in expense form
  const today = new Date().toISOString().split('T')[0];
  const dateInput = document.getElementById('expDate');
  if (dateInput) dateInput.value = today;

  const authed = await checkAuth();
  if (authed) {
    await loadTrips();
  }
  lucide.createIcons();
});

// --- TAB SWITCHING ---
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  const targetTab = document.getElementById(`tab-${tabId}`);
  if (targetTab) targetTab.classList.remove('hidden');

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active-tab');
    btn.classList.add('inactive-tab');
  });

  const activeBtn = document.getElementById(`tab-btn-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.add('active-tab');
    activeBtn.classList.remove('inactive-tab');
  }

  // Ensure trip banner is strictly scoped to Dashboard only
  const tripHeaderBanner = document.getElementById('tripHeaderBanner');
  if (tripHeaderBanner) {
    if (tabId === 'dashboard' && trips && trips.length > 0) {
      tripHeaderBanner.classList.remove('hidden');
    } else {
      tripHeaderBanner.classList.add('hidden');
    }
  }

  // Refresh charts if opening dashboard
  if (tabId === 'dashboard') {
    setTimeout(() => {
      if (categoryChart) categoryChart.resize();
      if (memberSpendChart) memberSpendChart.resize();
      if (dailyTrendChart) dailyTrendChart.resize();
    }, 100);
  }

  // Load fuel and mileage data when opening mileage tab
  if (tabId === 'mileage' && currentTripId) {
    loadMileageData(currentTripId);
  }

  lucide.createIcons();
}

// --- TOAST NOTIFICATIONS ---
function showToast(message, isError = false) {
  const toast = document.getElementById('toast');
  const toastMsg = document.getElementById('toastMsg');
  const toastIcon = document.getElementById('toastIcon');

  toastMsg.innerText = message;
  if (isError) {
    toastIcon.setAttribute('data-lucide', 'alert-circle');
    toastIcon.className = 'w-5 h-5 text-rose-400';
  } else {
    toastIcon.setAttribute('data-lucide', 'check-circle');
    toastIcon.className = 'w-5 h-5 text-emerald-400';
  }
  lucide.createIcons();

  toast.classList.remove('translate-y-20', 'opacity-0');
  setTimeout(() => {
    toast.classList.add('translate-y-20', 'opacity-0');
  }, 3000);
}

// --- MODAL HELPERS ---
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('hidden');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('hidden');
}

// --- TRIPS API & SELECTION ---
async function loadTrips() {
  try {
    const res = await authFetch('/api/trips');
    trips = await res.json();
    const select = document.getElementById('tripSelect');
    const zeroEmptyState = document.getElementById('zeroTripsEmptyState');
    const activeView = document.getElementById('activeTripView');
    const tripHeaderBanner = document.getElementById('tripHeaderBanner');
    const tripSelectWrap = document.getElementById('tripSelectWrap');

    select.innerHTML = '';

    if (!trips || trips.length === 0) {
      currentTripId = null;
      currentTrip = null;
      if (zeroEmptyState) zeroEmptyState.classList.remove('hidden');
      if (activeView) activeView.classList.add('hidden');
      if (tripHeaderBanner) tripHeaderBanner.classList.add('hidden');
      if (tripSelectWrap) tripSelectWrap.classList.add('hidden');
      return;
    }

    if (zeroEmptyState) zeroEmptyState.classList.add('hidden');
    if (activeView) activeView.classList.remove('hidden');
    if (tripHeaderBanner) tripHeaderBanner.classList.remove('hidden');
    if (tripSelectWrap) tripSelectWrap.classList.remove('hidden');

    trips.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.innerText = `${t.name} (${t.currency})`;
      select.appendChild(opt);
    });

    if (!currentTripId || !trips.some(t => t.id === currentTripId)) {
      currentTripId = trips[0].id;
    }
    select.value = currentTripId;

    await loadTripData(currentTripId);
  } catch (err) {
    console.error(err);
    showToast('Failed to load trips', true);
  }
}

async function onTripChange() {
  const select = document.getElementById('tripSelect');
  currentTripId = parseInt(select.value);
  await loadTripData(currentTripId);
}

async function loadTripData(tripId) {
  try {
    // 1. Get Trip Info
    const tripRes = await authFetch(`/api/trips/${tripId}`);
    currentTrip = await tripRes.json();
    renderTripBanner();

    // 2. Get Members
    const memRes = await authFetch(`/api/trips/${tripId}/members`);
    members = await memRes.json();
    populatePayerDropdown();
    renderMembersTab();

    // 3. Get Expenses
    const expRes = await authFetch(`/api/trips/${tripId}/expenses`);
    expenses = await expRes.json();
    renderExpensesList();
    renderStatementTable();

    // 4. Update Badges
    document.getElementById('navExpenseBadge').innerText = expenses.length;
    document.getElementById('navMemberBadge').innerText = members.length;

    // 5. Get Dashboard Analytics
    await loadDashboard(tripId);

    // 6. Get Settlement & WhatsApp
    await loadSettlement(tripId);

    // 7. Get Fuel & Mileage Analytics
    await loadMileageData(tripId);

    // Update Export Links
    updateExportLinks(tripId);

    lucide.createIcons();
  } catch (err) {
    console.error(err);
    showToast('Failed to load trip data', true);
  }
}

function renderTripBanner() {
  if (!currentTrip) return;
  document.getElementById('tripTitle').innerText = currentTrip.name;
  document.getElementById('tripDescription').innerText = currentTrip.description || 'No description added.';
  document.getElementById('tripCurrencyBadge').innerText = `${currentTrip.currency} Currency`;
  document.getElementById('expCurrencyPrefix').innerText = currentTrip.currency;
}

function updateExportLinks(tripId) {
  const pdfUrl = `/api/trips/${tripId}/export/pdf`;
  const excelUrl = `/api/trips/${tripId}/export/excel`;

  document.getElementById('bannerPdfBtn').href = pdfUrl;
  document.getElementById('bannerExcelBtn').href = excelUrl;
  document.getElementById('downloadPdfBtn').href = pdfUrl;
  document.getElementById('downloadExcelBtn').href = excelUrl;
}

// --- DASHBOARD & CHARTS ---
async function loadDashboard(tripId) {
  try {
    const res = await authFetch(`/api/trips/${tripId}/dashboard`);
    const data = await res.json();

    const curr = data.kpis.currency || '₹';
    document.getElementById('kpiTotalSpent').innerText = `${curr}${data.kpis.total_spent.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('kpiExpenseCount').innerText = data.kpis.expense_count;
    document.getElementById('kpiMemberCount').innerText = data.kpis.member_count;
    document.getElementById('kpiAvgPerPerson').innerText = `${curr}${data.kpis.avg_per_person.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('kpiTopSpender').innerText = data.kpis.top_spender;
    document.getElementById('kpiPendingSettlements').innerText = `${data.kpis.pending_settlements_count} Pending`;
    document.getElementById('navSettlementBadge').innerText = data.kpis.pending_settlements_count;

    renderRecentExpensesTable(expenses.slice(0, 5));
    renderCharts(data);
  } catch (err) {
    console.error(err);
  }
}

function renderCharts(data) {
  currentDashboardData = data;
  const curr = data.kpis.currency || '₹';
  const isDark = document.documentElement.classList.contains('dark');
  const textColor = isDark ? '#94a3b8' : '#64748b';
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
  const doughnutBorder = isDark ? '#111827' : '#FFFFFF';
  const fairShareBg = isDark ? '#334155' : '#E2E8F0';
  const fairShareHover = isDark ? '#475569' : '#CBD5E1';

  // 1. Category Donut Chart
  const catCanvas = document.getElementById('categoryChart');
  const catLabels = data.category_breakdown.map(c => c.category);
  const catValues = data.category_breakdown.map(c => c.total);
  const catColors = data.category_breakdown.map(c => (CATEGORY_META[c.category] ? CATEGORY_META[c.category].color : '#6366F1'));

  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(catCanvas, {
    type: 'doughnut',
    data: {
      labels: catLabels,
      datasets: [{
        data: catValues,
        backgroundColor: catColors,
        borderWidth: 2,
        borderColor: doughnutBorder
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      cutout: '70%'
    }
  });

  // Render Category Legend List below chart
  const legendBox = document.getElementById('categoryLegend');
  legendBox.innerHTML = '';
  data.category_breakdown.forEach(c => {
    const meta = CATEGORY_META[c.category] || { color: '#6366f1' };
    const row = document.createElement('div');
    row.className = 'flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800 last:border-0';
    row.innerHTML = `
      <div class="flex items-center space-x-2">
        <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${meta.color}"></span>
        <span class="font-medium text-slate-700 dark:text-slate-300">${c.category}</span>
        <span class="text-slate-400">(${c.percentage}%)</span>
      </div>
      <span class="font-bold text-slate-900 dark:text-white">${curr}${c.total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
    `;
    legendBox.appendChild(row);
  });

  // 2. Member Spend vs Share Bar Chart
  const memberCanvas = document.getElementById('memberSpendChart');
  const memNames = data.member_spending.map(m => m.name);
  const memPaid = data.member_spending.map(m => m.total_paid);
  const memShare = data.member_spending.map(m => m.total_owed);

  if (memberSpendChart) memberSpendChart.destroy();
  memberSpendChart = new Chart(memberCanvas, {
    type: 'bar',
    data: {
      labels: memNames,
      datasets: [
        {
          label: 'Total Paid Upfront',
          data: memPaid,
          backgroundColor: '#4F46E5',
          borderRadius: 6
        },
        {
          label: 'Fair Calculated Share',
          data: memShare,
          backgroundColor: fairShareBg,
          hoverBackgroundColor: fairShareHover,
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: textColor }
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            callback: val => `${curr}${val}`
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: textColor }
        }
      }
    }
  });

  // 3. Daily Trend Line Chart
  const dailyCanvas = document.getElementById('dailyTrendChart');
  const dailyDates = data.daily_trend.map(d => d.date);
  const dailyTotals = data.daily_trend.map(d => d.total);

  if (dailyTrendChart) dailyTrendChart.destroy();
  dailyTrendChart = new Chart(dailyCanvas, {
    type: 'line',
    data: {
      labels: dailyDates.length > 0 ? dailyDates : ['No Data'],
      datasets: [{
        label: `Daily Expenses (${curr})`,
        data: dailyTotals.length > 0 ? dailyTotals : [0],
        borderColor: '#059669',
        backgroundColor: 'rgba(5, 150, 105, 0.1)',
        tension: 0.35,
        fill: true,
        pointBackgroundColor: '#059669',
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor }
        },
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            callback: val => `${curr}${val}`
          }
        }
      },
      plugins: {
        legend: {
          labels: { color: textColor }
        }
      }
    }
  });
}

function renderRecentExpensesTable(recentList) {
  const tbody = document.getElementById('recentExpensesTableBody');
  tbody.innerHTML = '';
  if (!recentList || recentList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="px-5 py-6 text-center text-slate-400">No expenses recorded yet. Click "+ Add Expense" to start!</td></tr>`;
    return;
  }

  const curr = currentTrip ? currentTrip.currency : '₹';
  recentList.forEach(e => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50/70 transition';
    tr.innerHTML = `
      <td class="px-5 py-3 text-slate-500 font-mono text-xs">${e.date}</td>
      <td class="px-5 py-3 font-semibold text-slate-900">${e.title}</td>
      <td class="px-5 py-3">
        <span class="px-2 py-0.5 text-xs font-semibold rounded-md bg-slate-100 text-slate-700">${e.category}</span>
      </td>
      <td class="px-5 py-3">
        <div class="flex items-center space-x-1.5">
          <span class="w-2 h-2 rounded-full" style="background-color: ${e.payer_color || '#4F46E5'}"></span>
          <span>${e.payer_name}</span>
        </div>
      </td>
      <td class="px-5 py-3">
        <span class="px-2 py-0.5 text-xs font-semibold rounded-md bg-slate-100 text-slate-700">${e.payment_mode || 'Cash'}</span>
      </td>
      <td class="px-5 py-3 text-xs capitalize text-slate-500">${e.split_type}</td>
      <td class="px-5 py-3 text-right font-bold text-slate-900">${curr}${e.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
    `;
    tbody.appendChild(tr);
  });
}

// --- EXPENSES TAB & FILTERING ---
function renderExpensesList() {
  filterExpenses();
}

function filterExpenses() {
  const query = (document.getElementById('expenseSearchInput').value || '').toLowerCase();
  const catFilter = document.getElementById('categoryFilter').value;
  const payerFilter = document.getElementById('memberFilter').value;

  const filtered = expenses.filter(e => {
    const matchQuery = !query || e.title.toLowerCase().includes(query) || (e.notes && e.notes.toLowerCase().includes(query));
    const matchCat = catFilter === 'all' || e.category === catFilter;
    const matchPayer = payerFilter === 'all' || e.payer_id.toString() === payerFilter;
    return matchQuery && matchCat && matchPayer;
  });

  const container = document.getElementById('expensesList');
  container.innerHTML = '';

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="bg-white rounded-2xl p-10 text-center border border-slate-200">
        <div class="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
          <i data-lucide="receipt" class="w-6 h-6"></i>
        </div>
        <h4 class="text-base font-bold text-slate-700">No expenses found</h4>
        <p class="text-xs text-slate-400 mt-1">Try changing filters or add a new travel expense</p>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  const curr = currentTrip ? currentTrip.currency : '₹';
  filtered.forEach(e => {
    const meta = CATEGORY_META[e.category] || { icon: 'box', label: e.category, color: '#64748b' };
    const splitsSummary = e.splits.map(s => `${s.member_name} (${curr}${s.share_amount.toFixed(2)})`).join(', ');

    const card = document.createElement('div');
    card.className = 'bg-white rounded-2xl p-4 sm:p-5 border border-slate-200 shadow-xs hover:shadow-md transition flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4';
    card.innerHTML = `
      <div class="flex items-start space-x-3.5">
        <div class="w-11 h-11 rounded-2xl flex items-center justify-center text-white shrink-0 shadow-sm" style="background-color: ${meta.color}">
          <i data-lucide="${meta.icon}" class="w-5 h-5"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h4 class="font-bold text-slate-900 text-base">${e.title}</h4>
            <span class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-600">${e.category}</span>
            <span class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-700">💳 ${e.payment_mode || 'Cash'}</span>
            <span class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-indigo-50 text-indigo-700 capitalize">${e.split_type} Split</span>
          </div>
          <p class="text-xs text-slate-500 mt-1">
            Paid by <strong class="text-slate-700">${e.payer_name}</strong> on <span class="font-mono">${e.date}</span>
          </p>
          <p class="text-xs text-slate-400 mt-1">
            <span class="text-slate-500 font-medium">Split with:</span> ${splitsSummary}
          </p>
          ${e.notes ? `<p class="text-xs text-amber-700 bg-amber-50 rounded-md px-2 py-0.5 mt-1.5 inline-block font-sans">📝 ${e.notes}</p>` : ''}
        </div>
      </div>

      <div class="flex items-center justify-between sm:justify-end sm:space-x-4 border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-100">
        <div class="text-right">
          <span class="text-lg sm:text-xl font-black text-slate-900 dark:text-white">${curr}${e.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
        <div class="flex items-center space-x-1">
          <button onclick="editExpenseItem(${e.id})" class="text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 p-2 rounded-lg hover:bg-brand-50 dark:hover:bg-brand-950/40 transition" title="Edit Expense">
            <i data-lucide="pencil" class="w-4 h-4"></i>
          </button>
          <button onclick="deleteExpenseItem(${e.id})" class="text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 p-2 rounded-lg hover:bg-rose-50 dark:hover:bg-rose-950/40 transition" title="Delete Expense">
            <i data-lucide="trash-2" class="w-4 h-4"></i>
          </button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });

  lucide.createIcons();
}

async function deleteExpenseItem(expenseId) {
  if (!confirm('Are you sure you want to delete this expense?')) return;
  try {
    const res = await authFetch(`/api/expenses/${expenseId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Expense deleted successfully');
      await loadTripData(currentTripId);
    } else {
      showToast('Failed to delete expense', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error deleting expense', true);
  }
}

// --- SETTLEMENT & WHATSAPP TAB ---
let cachedWhatsAppUrl = '';
let cachedWhatsAppText = '';

async function loadSettlement(tripId) {
  try {
    const res = await authFetch(`/api/trips/${tripId}/settlement`);
    const data = await res.json();
    const curr = data.trip.currency || '₹';

    cachedWhatsAppText = data.whatsapp_text;
    cachedWhatsAppUrl = data.whatsapp_url;

    // Set Live preview box
    document.getElementById('whatsappPreviewBox').innerText = data.whatsapp_text;
    document.getElementById('btnOpenWhatsApp').href = data.whatsapp_url;

    // Render Settlements ("Who Pays Whom")
    const settleBox = document.getElementById('settlementsContainer');
    settleBox.innerHTML = '';
    document.getElementById('settlementTxnCount').innerText = `${data.settlements.length} Transactions`;

    if (data.settlements.length === 0) {
      settleBox.innerHTML = `
        <div class="p-6 bg-emerald-50 rounded-2xl border border-emerald-100 text-center text-emerald-800">
          <i data-lucide="check-circle-2" class="w-8 h-8 text-emerald-600 mx-auto mb-2"></i>
          <p class="font-bold text-base">All balances are completely settled!</p>
          <p class="text-xs text-emerald-600 mt-1">Nobody owes anyone anything right now.</p>
        </div>
      `;
    } else {
      data.settlements.forEach(s => {
        const card = document.createElement('div');
        card.className = 'flex flex-col sm:flex-row sm:items-center sm:justify-between p-4 bg-slate-50 hover:bg-slate-100/80 rounded-2xl border border-slate-200 transition gap-3';
        card.innerHTML = `
          <div class="flex items-center justify-between flex-1">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 rounded-xl bg-rose-100 text-rose-700 flex items-center justify-center font-bold text-sm shrink-0">
                ${s.from_name.charAt(0)}
              </div>
              <div>
                <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Payer (Owes)</span>
                <h4 class="font-bold text-slate-900">${s.from_name}</h4>
              </div>
            </div>

            <div class="flex flex-col items-center px-2">
              <span class="text-xs font-bold text-indigo-600 mb-0.5">pays ➔</span>
              <div class="h-0.5 w-12 bg-indigo-300 relative flex items-center justify-end">
                <div class="w-1.5 h-1.5 bg-indigo-600 rotate-45 transform -mr-0.5"></div>
              </div>
            </div>

            <div class="flex items-center space-x-3 text-right">
              <div>
                <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Receiver</span>
                <h4 class="font-bold text-slate-900">${s.to_name}</h4>
              </div>
              <div class="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-sm shrink-0">
                ${s.to_name.charAt(0)}
              </div>
            </div>
          </div>

          <div class="flex items-center justify-between sm:justify-end space-x-3 sm:pl-4 sm:border-l border-slate-200 border-t sm:border-t-0 pt-2 sm:pt-0">
            <span class="text-base font-black text-brand-700">${curr}${s.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            <button onclick="openRecordSettlementModal(${s.from_id}, '${s.from_name}', ${s.to_id}, '${s.to_name}', ${s.amount})" class="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs transition">
              <i data-lucide="check" class="w-3.5 h-3.5"></i>
              <span>Settle</span>
            </button>
          </div>
        `;
        settleBox.appendChild(card);
      });
    }

    // Render Settlement History (Paid & Settled)
    const historyBox = document.getElementById('settlementHistoryContainer');
    const settledBadge = document.getElementById('settledCountBadge');
    if (historyBox) {
      historyBox.innerHTML = '';
      const historyList = data.settlement_history || [];
      if (settledBadge) settledBadge.innerText = `${historyList.length} Settled`;

      if (historyList.length === 0) {
        historyBox.innerHTML = `
          <div class="p-4 bg-slate-50 rounded-xl text-center text-xs text-slate-400">
            No payments recorded yet. When a traveler settles their debt, click "Settle" above!
          </div>
        `;
      } else {
        historyList.forEach(sh => {
          const row = document.createElement('div');
          row.className = 'flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100/70 rounded-xl border border-slate-200/80 transition text-xs';
          row.innerHTML = `
            <div class="flex items-center space-x-2.5">
              <div class="w-6 h-6 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
                <i data-lucide="check" class="w-3.5 h-3.5"></i>
              </div>
              <div>
                <span class="font-bold text-slate-900">${sh.payer_name}</span>
                <span class="text-slate-400">paid</span>
                <span class="font-bold text-slate-900">${sh.receiver_name}</span>
                <span class="text-slate-400 font-mono ml-1">(${sh.date})</span>
                ${sh.notes ? `<span class="text-slate-500 block text-[11px]">📝 ${sh.notes}</span>` : ''}
              </div>
            </div>
            <div class="flex items-center space-x-2.5">
              <span class="font-bold text-emerald-700 text-sm">${curr}${parseFloat(sh.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
              <button onclick="undoSettlement(${sh.id})" class="text-slate-400 hover:text-rose-600 p-1 rounded hover:bg-rose-50 transition" title="Undo settlement">
                <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
              </button>
            </div>
          `;
          historyBox.appendChild(row);
        });
      }
    }

    // Render Member Net Balances
    const balancesBox = document.getElementById('memberBalancesContainer');
    balancesBox.innerHTML = '';
    data.member_stats.forEach(m => {
      const net = m.net_balance;
      const isPositive = net > 0.009;
      const isNegative = net < -0.009;

      const badgeColor = isPositive ? 'bg-emerald-100 text-emerald-800' : (isNegative ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-600');
      const statusText = isPositive ? `Gets back ${curr}${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : (isNegative ? `Owes ${curr}${Math.abs(net).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : 'Settled up');

      const card = document.createElement('div');
      card.className = 'flex items-center justify-between p-3.5 bg-white rounded-xl border border-slate-100 hover:border-slate-200 transition';
      card.innerHTML = `
        <div class="flex items-center space-x-3">
          <div class="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-xs" style="background-color: ${m.avatar_color}">
            ${m.name.charAt(0)}
          </div>
          <div>
            <h5 class="font-bold text-slate-900 text-sm">${m.name}</h5>
            <p class="text-xs text-slate-400">Paid: ${curr}${m.total_paid.toLocaleString('en-IN', { minimumFractionDigits: 2 })} | Share: ${curr}${m.total_owed.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</p>
          </div>
        </div>

        <div>
          <span class="px-3 py-1 rounded-full text-xs font-bold ${badgeColor}">
            ${statusText}
          </span>
        </div>
      `;
      balancesBox.appendChild(card);
    });

    lucide.createIcons();
  } catch (err) {
    console.error(err);
  }
}

function copyWhatsAppText() {
  if (!cachedWhatsAppText) {
    showToast('No settlement text to copy', true);
    return;
  }
  navigator.clipboard.writeText(cachedWhatsAppText).then(() => {
    showToast('WhatsApp settlement summary copied to clipboard! 📋');
  }).catch(() => {
    // Fallback
    const area = document.createElement('textarea');
    area.value = cachedWhatsAppText;
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    document.body.removeChild(area);
    showToast('WhatsApp summary copied to clipboard!');
  });
}

// --- SETTLEMENT ACTION HANDLERS ---
function openRecordSettlementModal(fromId, fromName, toId, toName, amount) {
  document.getElementById('settlePayerId').value = fromId;
  document.getElementById('settleReceiverId').value = toId;
  document.getElementById('settlePayerName').innerText = fromName;
  document.getElementById('settleReceiverName').innerText = toName;
  document.getElementById('settleAmountInput').value = amount.toFixed(2);
  document.getElementById('settleDateInput').value = new Date().toISOString().split('T')[0];
  document.getElementById('settleNotesInput').value = '';
  document.getElementById('settleCurrencyPrefix').innerText = currentTrip ? currentTrip.currency : '₹';
  openModal('recordSettlementModal');
}

async function submitSettlementPayment(event) {
  event.preventDefault();
  const payerId = parseInt(document.getElementById('settlePayerId').value);
  const receiverId = parseInt(document.getElementById('settleReceiverId').value);
  const amount = parseFloat(document.getElementById('settleAmountInput').value);
  const date = document.getElementById('settleDateInput').value;
  const notes = document.getElementById('settleNotesInput').value.trim();

  if (!amount || amount <= 0) {
    showToast('Please enter a valid settled amount', true);
    return;
  }

  try {
    const res = await authFetch(`/api/trips/${currentTripId}/settlements`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ payer_id: payerId, receiver_id: receiverId, amount, date, notes })
    });

    if (res.ok) {
      closeModal('recordSettlementModal');
      showToast('Settlement payment recorded successfully! 🎉');
      await loadTripData(currentTripId);
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to record settlement', true);
    }
  } catch (e) {
    console.error(e);
    showToast('Error recording settlement', true);
  }
}

async function undoSettlement(settleId) {
  if (!confirm('Are you sure you want to undo this settlement payment?')) return;
  try {
    const res = await authFetch(`/api/settlements/${settleId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Settlement undone');
      await loadTripData(currentTripId);
    } else {
      showToast('Failed to undo settlement', true);
    }
  } catch (e) {
    console.error(e);
    showToast('Error undoing settlement', true);
  }
}

// --- STATEMENT & AUDIT REPORTS ---
function renderStatementTable() {
  const tbody = document.getElementById('statementTableBody');
  tbody.innerHTML = '';
  const curr = currentTrip ? currentTrip.currency : '₹';
  let total = 0;

  expenses.forEach(e => {
    total += e.amount;

    // Clean Date formatting: DD MMM YYYY (e.g. 26 Aug 2026)
    let displayDate = e.date;
    try {
      const parts = e.date.split('-');
      if (parts.length === 3) {
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        displayDate = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
      }
    } catch (err) {}

    // Intelligent Split Status Badge
    let splitBadge = '';
    if (e.split_type === 'equal') {
      if (members.length > 0 && e.splits.length >= members.length) {
        splitBadge = `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200/60 dark:border-indigo-800/50 whitespace-nowrap">All ${members.length} Equal</span>`;
      } else {
        splitBadge = `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border border-amber-200/60 dark:border-amber-800/50 whitespace-nowrap">${e.splits.length} Members</span>`;
      }
    } else if (e.split_type === 'selected') {
      splitBadge = `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border border-blue-200/60 dark:border-blue-800/50 whitespace-nowrap">${e.splits.length} Selected</span>`;
    } else {
      splitBadge = `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border border-purple-200/60 dark:border-purple-800/50 whitespace-nowrap">Custom</span>`;
    }

    // Rich Split Breakdown Chips
    const splitChips = e.splits.map(s => `
      <span class="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[11px] font-medium text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/60 mr-1 mb-1 whitespace-nowrap shadow-2xs">
        <span>${s.member_name}:</span>
        <b class="text-indigo-600 dark:text-indigo-400 font-bold">${curr}${s.share_amount.toFixed(2)}</b>
      </span>
    `).join('');

    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-800/50 transition border-b border-slate-100 dark:border-slate-800/60';
    tr.innerHTML = `
      <td class="px-4 py-3 font-mono text-xs text-slate-400 dark:text-slate-500 whitespace-nowrap">#${e.id}</td>
      <td class="px-4 py-3 font-semibold text-xs text-slate-700 dark:text-slate-200 whitespace-nowrap">${displayDate}</td>
      <td class="px-4 py-3 font-bold text-slate-900 dark:text-white">${e.title}</td>
      <td class="px-4 py-3 whitespace-nowrap"><span class="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium">${e.category}</span></td>
      <td class="px-4 py-3 font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">${e.payer_name}</td>
      <td class="px-4 py-3 whitespace-nowrap"><span class="px-2 py-0.5 rounded-md bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-xs font-semibold">💳 ${e.payment_mode || 'UPI'}</span></td>
      <td class="px-4 py-3 whitespace-nowrap">${splitBadge}</td>
      <td class="px-4 py-3 min-w-[200px]"><div class="flex flex-wrap items-center pt-0.5">${splitChips}</div></td>
      <td class="px-4 py-3 text-right font-black text-slate-900 dark:text-white whitespace-nowrap">${curr}${e.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('statementGrandTotal').innerText = `${curr}${total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
}

// --- GROUP MEMBERS TAB ---
function renderMembersTab() {
  const grid = document.getElementById('membersListGrid');
  grid.innerHTML = '';
  const curr = currentTrip ? currentTrip.currency : '₹';

  // Also populate payer dropdown filter
  const filterPayer = document.getElementById('memberFilter');
  filterPayer.innerHTML = '<option value="all">All Payers</option>';

  members.forEach(m => {
    // Add to filter dropdown
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.innerText = m.name;
    filterPayer.appendChild(opt);

    // Render member card
    const card = document.createElement('div');
    card.className = 'bg-white rounded-2xl p-5 border border-slate-200 shadow-xs hover:shadow-md transition space-y-4';
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-11 h-11 rounded-2xl flex items-center justify-center text-white font-bold text-base shadow-sm" style="background-color: ${m.avatar_color || '#4F46E5'}">
            ${m.name.charAt(0)}
          </div>
          <div>
            <h4 class="font-bold text-slate-900 text-base">${m.name}</h4>
            <p class="text-xs text-slate-400">${m.phone || 'No phone added'}</p>
          </div>
        </div>
        <button onclick="deleteMemberItem(${m.id})" class="text-slate-300 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition" title="Remove Traveler">
          <i data-lucide="user-minus" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-3 grid grid-cols-2 gap-2 text-center text-xs">
        <div>
          <span class="text-slate-400 block">Total Spent</span>
          <span class="font-bold text-slate-800 dark:text-slate-200" id="mem-spent-${m.id}">...</span>
        </div>
        <div>
          <span class="text-slate-400 block">Fair Share</span>
          <span class="font-bold text-slate-800 dark:text-slate-200" id="mem-share-${m.id}">...</span>
        </div>
      </div>

      <div class="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <span class="text-[11px] text-slate-400 font-medium">Individual Audit</span>
        <a href="/api/trips/${currentTripId}/members/${m.id}/export/pdf" target="_blank" class="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 text-xs font-bold border border-indigo-200/70 dark:border-indigo-800/60 shadow-2xs transition" title="Download individual traveler statement PDF">
          <i data-lucide="file-text" class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400"></i>
          <span>Statement PDF</span>
        </a>
      </div>
    `;
    grid.appendChild(card);
  });

  // Populate individual spent and share from dashboard
  if (currentTripId) {
    authFetch(`/api/trips/${currentTripId}/settlement`)
      .then(r => r.json())
      .then(d => {
        d.member_stats.forEach(st => {
          const spentEl = document.getElementById(`mem-spent-${st.id}`);
          const shareEl = document.getElementById(`mem-share-${st.id}`);
          if (spentEl) spentEl.innerText = `${curr}${st.total_paid.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
          if (shareEl) shareEl.innerText = `${curr}${st.total_owed.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        });
      });
  }

  lucide.createIcons();
}

async function deleteMemberItem(memberId) {
  if (!confirm('Are you sure you want to remove this traveler from the trip?')) return;
  try {
    const res = await authFetch(`/api/members/${memberId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Traveler removed');
      await loadTripData(currentTripId);
    } else {
      showToast('Failed to remove traveler', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error removing traveler', true);
  }
}

// --- ADD EXPENSE MODAL & DYNAMIC SPLIT ENGINE ---
function openAddExpenseModal() {
  if (members.length === 0) {
    showToast('Please add at least one group member before adding expenses!', true);
    switchTab('members');
    return;
  }

  editingExpenseId = null;
  const titleEl = document.getElementById('addExpenseModalTitle');
  if (titleEl) titleEl.innerText = 'Add Travel Expense';
  const subEl = document.getElementById('addExpenseModalSubtitle');
  if (subEl) subEl.innerText = 'Log a bill and select how to split it';
  const submitBtn = document.getElementById('expSubmitBtn');
  if (submitBtn) submitBtn.innerText = 'Save Expense';
  const ocrBanner = document.getElementById('expOcrBanner');
  if (ocrBanner) ocrBanner.classList.remove('hidden');

  document.getElementById('addExpenseForm').reset();
  document.getElementById('expDate').value = new Date().toISOString().split('T')[0];
  populatePayerDropdown();
  setSplitType('equal');
  openModal('addExpenseModal');
}

function editExpenseItem(expenseId) {
  const exp = expenses.find(e => e.id === expenseId);
  if (!exp) {
    showToast('Expense not found', true);
    return;
  }

  editingExpenseId = expenseId;

  // Update modal titles & buttons
  const titleEl = document.getElementById('addExpenseModalTitle');
  if (titleEl) titleEl.innerText = 'Edit Travel Expense';
  const subEl = document.getElementById('addExpenseModalSubtitle');
  if (subEl) subEl.innerText = 'Update bill details and adjust member splits';
  const submitBtn = document.getElementById('expSubmitBtn');
  if (submitBtn) submitBtn.innerText = 'Update Expense';
  const ocrBanner = document.getElementById('expOcrBanner');
  if (ocrBanner) ocrBanner.classList.add('hidden');

  // Fill form inputs
  document.getElementById('expTitle').value = exp.title || '';
  document.getElementById('expAmount').value = exp.amount ? exp.amount.toString() : '';
  document.getElementById('expDate').value = exp.date || new Date().toISOString().split('T')[0];
  document.getElementById('expCategory').value = exp.category || 'Misc';
  populatePayerDropdown();
  document.getElementById('expPayer').value = exp.payer_id;
  if (document.getElementById('expPaymentMode')) {
    document.getElementById('expPaymentMode').value = exp.payment_mode || 'UPI';
  }
  document.getElementById('expNotes').value = exp.notes || '';

  // Setup splits
  const splitMemberIds = new Set(exp.splits.map(s => s.member_id));
  const isCustom = exp.split_type === 'custom';

  if (isCustom) {
    setSplitType('custom');
    setTimeout(() => {
      document.querySelectorAll('.split-member-checkbox').forEach(cb => {
        const mid = parseInt(cb.value);
        cb.checked = splitMemberIds.has(mid);
        const inp = document.querySelector(`.custom-fixed-input[data-mid="${mid}"]`);
        if (inp) {
          const sObj = exp.splits.find(s => s.member_id === mid);
          inp.value = sObj ? sObj.share_amount.toFixed(2) : '';
        }
      });
      recalculateSplits();
    }, 20);
  } else {
    setSplitType('equal');
    setTimeout(() => {
      document.querySelectorAll('.split-member-checkbox').forEach(cb => {
        const mid = parseInt(cb.value);
        cb.checked = splitMemberIds.has(mid);
      });
      recalculateSplits();
    }, 20);
  }

  openModal('addExpenseModal');
}

function populatePayerDropdown() {
  const payerSelect = document.getElementById('expPayer');
  if (!payerSelect) return;
  payerSelect.innerHTML = '';

  members.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.innerText = m.name;
    payerSelect.appendChild(opt);
  });
}

function setSplitType(type) {
  currentSplitType = type;

  // Update button highlights
  document.querySelectorAll('.split-tab-btn').forEach(b => {
    b.className = 'split-tab-btn py-2 px-3 rounded-lg text-xs font-bold text-slate-600 hover:text-slate-900';
  });
  const activeBtn = document.getElementById(`splitBtn-${type}`);
  if (activeBtn) {
    activeBtn.className = 'split-tab-btn py-2 px-3 rounded-lg text-xs font-bold bg-white text-brand-700 shadow-xs';
  }

  // Render input rows for members
  renderSplitMemberRows();
  recalculateSplits();
}

function renderSplitMemberRows() {
  const container = document.getElementById('splitMembersContainer');
  container.innerHTML = '';
  const curr = currentTrip ? currentTrip.currency : '₹';

  if (currentSplitType === 'equal') {
    document.getElementById('splitSectionTitle').innerText = 'Split equally among checked members:';
    members.forEach(m => {
      const row = document.createElement('div');
      row.className = 'flex items-center justify-between p-2.5 bg-white rounded-xl border border-slate-100 hover:border-slate-200 transition';
      row.innerHTML = `
        <label class="flex items-center space-x-3 cursor-pointer flex-1">
          <input type="checkbox" checked onchange="recalculateSplits()" value="${m.id}" class="split-member-checkbox w-4 h-4 text-brand-600 rounded border-slate-300 focus:ring-brand-500 cursor-pointer" />
          <div class="flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${m.avatar_color}"></span>
            <span class="text-sm font-semibold text-slate-800">${m.name}</span>
          </div>
        </label>
        <span class="text-xs font-bold text-slate-600 member-split-preview" data-mid="${m.id}">
          ${curr}0.00
        </span>
      `;
      container.appendChild(row);
    });
  } else if (currentSplitType === 'custom') {
    document.getElementById('splitSectionTitle').innerText = 'Enter specific amount for selected members. Remaining is split equally among others:';
    members.forEach(m => {
      const row = document.createElement('div');
      row.className = 'flex items-center justify-between p-2.5 bg-white rounded-xl border border-slate-100 hover:border-slate-200 transition gap-2.5';
      row.innerHTML = `
        <label class="flex items-center space-x-2.5 cursor-pointer min-w-[130px]">
          <input type="checkbox" checked onchange="recalculateSplits()" value="${m.id}" class="split-member-checkbox w-4 h-4 text-brand-600 rounded border-slate-300 focus:ring-brand-500 cursor-pointer" />
          <div class="flex items-center space-x-1.5">
            <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${m.avatar_color}"></span>
            <span class="text-sm font-semibold text-slate-800">${m.name}</span>
          </div>
        </label>
        <div class="flex items-center space-x-2 flex-1 justify-end">
          <div class="relative w-28 sm:w-32">
            <span class="absolute inset-y-0 left-0 pl-2.5 flex items-center text-xs text-slate-400 font-bold">${curr}</span>
            <input type="text" inputmode="decimal" placeholder="Fixed" oninput="validateDecimalInput(this); recalculateSplits()" data-mid="${m.id}" class="custom-fixed-input w-full bg-slate-50 border border-slate-200 rounded-lg pl-6 pr-2 py-1 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white" />
          </div>
          <span class="text-xs font-bold text-slate-700 member-split-preview min-w-[90px] text-right" data-mid="${m.id}">
            ${curr}0.00
          </span>
        </div>
      `;
      container.appendChild(row);
    });
  }
}

function recalculateSplits() {
  const totalAmount = parseFloat(document.getElementById('expAmount').value) || 0.0;
  const curr = currentTrip ? currentTrip.currency : '₹';
  const statusEl = document.getElementById('splitLiveStatus');

  if (currentSplitType === 'equal') {
    const checkboxes = document.querySelectorAll('.split-member-checkbox');
    const checked = Array.from(checkboxes).filter(cb => cb.checked);
    const count = checked.length;

    if (count === 0) {
      statusEl.innerHTML = '<span class="text-rose-600 font-bold">Please select at least 1 member</span>';
      document.querySelectorAll('.member-split-preview').forEach(el => el.innerText = `${curr}0.00`);
      return;
    }

    const perShare = totalAmount > 0 ? (totalAmount / count) : 0.0;
    statusEl.innerHTML = `<span class="text-emerald-700 font-bold">${curr}${perShare.toFixed(2)} each (${count} selected)</span>`;

    checkboxes.forEach(cb => {
      const mid = cb.value;
      const previewEl = document.querySelector(`.member-split-preview[data-mid="${mid}"]`);
      if (previewEl) {
        if (cb.checked) {
          previewEl.innerText = `${curr}${perShare.toFixed(2)}`;
          previewEl.classList.remove('text-slate-300');
          previewEl.classList.add('text-slate-800');
        } else {
          previewEl.innerText = `${curr}0.00`;
          previewEl.classList.add('text-slate-300');
          previewEl.classList.remove('text-slate-800');
        }
      }
    });
  } else if (currentSplitType === 'custom') {
    const checkboxes = document.querySelectorAll('.split-member-checkbox');
    let totalFixed = 0;
    let remainderMembers = [];

    checkboxes.forEach(cb => {
      const mid = cb.value;
      const inp = document.querySelector(`.custom-fixed-input[data-mid="${mid}"]`);
      const val = inp ? parseFloat(inp.value) : 0;

      if (cb.checked) {
        if (val && val > 0) {
          totalFixed += val;
        } else {
          remainderMembers.push(mid);
        }
      }
    });

    totalFixed = Math.round(totalFixed * 100) / 100;
    const remainingAmount = Math.round((totalAmount - totalFixed) * 100) / 100;

    if (remainingAmount < -0.01) {
      statusEl.innerHTML = `<span class="text-rose-600 font-bold">⚠️ Fixed (${curr}${totalFixed.toFixed(2)}) exceeds total bill by ${curr}${Math.abs(remainingAmount).toFixed(2)}</span>`;
    } else if (remainderMembers.length > 0) {
      const perRemainder = Math.round((remainingAmount / remainderMembers.length) * 100) / 100;
      statusEl.innerHTML = `<span class="text-emerald-700 font-bold">Fixed: ${curr}${totalFixed.toFixed(2)} | Remainder: ${curr}${remainingAmount.toFixed(2)} (${curr}${perRemainder.toFixed(2)} each for ${remainderMembers.length} members)</span>`;
    } else {
      if (Math.abs(remainingAmount) > 0.05) {
        statusEl.innerHTML = `<span class="text-amber-600 font-bold">Fixed sum (${curr}${totalFixed.toFixed(2)}) doesn't match total bill (${curr}${totalAmount.toFixed(2)})</span>`;
      } else {
        statusEl.innerHTML = `<span class="text-emerald-700 font-bold">Exact match: All members have fixed amounts ✓</span>`;
      }
    }

    checkboxes.forEach(cb => {
      const mid = cb.value;
      const inp = document.querySelector(`.custom-fixed-input[data-mid="${mid}"]`);
      const previewEl = document.querySelector(`.member-split-preview[data-mid="${mid}"]`);
      if (!previewEl) return;

      if (!cb.checked) {
        previewEl.innerText = `${curr}0.00`;
        previewEl.className = 'text-xs font-bold text-slate-300 member-split-preview min-w-[90px] text-right';
        if (inp) inp.disabled = true;
        return;
      }

      if (inp) inp.disabled = false;
      const val = inp ? parseFloat(inp.value) : 0;
      if (val && val > 0) {
        previewEl.innerHTML = `<span class="text-indigo-600 font-bold">[Fixed]</span> ${curr}${val.toFixed(2)}`;
        previewEl.className = 'text-xs font-bold text-slate-900 member-split-preview min-w-[90px] text-right';
      } else if (remainderMembers.length > 0 && remainingAmount >= 0) {
        const perRemainder = Math.round((remainingAmount / remainderMembers.length) * 100) / 100;
        previewEl.innerHTML = `<span class="text-emerald-600 font-bold">[Rem.]</span> ${curr}${perRemainder.toFixed(2)}`;
        previewEl.className = 'text-xs font-bold text-slate-900 member-split-preview min-w-[90px] text-right';
      } else {
        previewEl.innerText = `${curr}0.00`;
        previewEl.className = 'text-xs font-bold text-slate-400 member-split-preview min-w-[90px] text-right';
      }
    });
  }
}

async function submitExpense(event) {
  event.preventDefault();
  const totalAmount = parseFloat(document.getElementById('expAmount').value);
  if (!totalAmount || totalAmount <= 0) {
    showToast('Please enter a valid amount', true);
    return;
  }

  const title = document.getElementById('expTitle').value.trim();
  const date = document.getElementById('expDate').value;
  const category = document.getElementById('expCategory').value;
  const payerId = parseInt(document.getElementById('expPayer').value);
  const notes = document.getElementById('expNotes').value.trim();

  let splits = [];

  if (currentSplitType === 'equal') {
    const checked = Array.from(document.querySelectorAll('.split-member-checkbox:checked')).map(cb => parseInt(cb.value));
    if (checked.length === 0) {
      showToast('Please select at least one traveler to split with', true);
      return;
    }

    const count = checked.length;
    const perShare = Math.round((totalAmount / count) * 100) / 100;
    let allocated = 0;

    checked.forEach((mid, idx) => {
      let share = perShare;
      if (idx === count - 1) {
        share = Math.round((totalAmount - allocated) * 100) / 100;
      } else {
        allocated += share;
      }
      splits.push({
        member_id: mid,
        share_amount: share,
        percentage: Math.round((100 / count) * 100) / 100
      });
    });
  } else if (currentSplitType === 'custom') {
    const checkboxes = document.querySelectorAll('.split-member-checkbox');
    let totalFixed = 0;
    let fixedList = [];
    let remainderMembers = [];

    checkboxes.forEach(cb => {
      if (cb.checked) {
        const mid = parseInt(cb.value);
        const inp = document.querySelector(`.custom-fixed-input[data-mid="${mid}"]`);
        const val = inp ? parseFloat(inp.value) : 0;
        if (val && val > 0) {
          totalFixed += val;
          fixedList.push({ mid, val });
        } else {
          remainderMembers.push(mid);
        }
      }
    });

    if (fixedList.length === 0 && remainderMembers.length === 0) {
      showToast('Please select at least one traveler to split with', true);
      return;
    }

    totalFixed = Math.round(totalFixed * 100) / 100;
    const remainingAmount = Math.round((totalAmount - totalFixed) * 100) / 100;

    if (remainingAmount < -0.05) {
      showToast(`Fixed amounts (${totalFixed.toFixed(2)}) exceed total expense (${totalAmount.toFixed(2)})`, true);
      return;
    }

    let allocated = 0;
    fixedList.forEach(item => {
      splits.push({
        member_id: item.mid,
        share_amount: item.val,
        percentage: Math.round((item.val / totalAmount) * 1000) / 10
      });
      allocated += item.val;
    });

    if (remainderMembers.length > 0) {
      const count = remainderMembers.length;
      const perRemainder = Math.round((remainingAmount / count) * 100) / 100;
      let remAllocated = 0;

      remainderMembers.forEach((mid, idx) => {
        let share = perRemainder;
        if (idx === count - 1) {
          share = Math.round((remainingAmount - remAllocated) * 100) / 100;
        } else {
          remAllocated += share;
        }
        splits.push({
          member_id: mid,
          share_amount: share,
          percentage: Math.round((share / totalAmount) * 1000) / 10
        });
      });
    } else {
      if (Math.abs(allocated - totalAmount) > 0.10) {
        showToast(`Sum of fixed amounts (${allocated.toFixed(2)}) does not equal total expense (${totalAmount.toFixed(2)})`, true);
        return;
      }
    }
  }

  const paymentMode = document.getElementById('expPaymentMode') ? document.getElementById('expPaymentMode').value : 'UPI';

  const payload = {
    title,
    amount: totalAmount,
    date,
    category,
    payer_id: payerId,
    payment_mode: paymentMode,
    split_type: currentSplitType,
    splits,
    notes
  };

  const isEditing = Boolean(editingExpenseId);
  const url = isEditing ? `/api/expenses/${editingExpenseId}` : `/api/trips/${currentTripId}/expenses`;
  const method = isEditing ? 'PUT' : 'POST';

  try {
    const res = await authFetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast(isEditing ? 'Expense updated successfully! ✏️' : 'Expense logged successfully! 💰');
      editingExpenseId = null;
      closeModal('addExpenseModal');
      await loadTripData(currentTripId);
    } else {
      const errData = await res.json();
      showToast(errData.detail || 'Failed to save expense', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error saving expense', true);
  }
}

// --- NEW TRIP & NEW MEMBER HANDLERS ---
function openNewTripModal() {
  document.getElementById('newTripForm').reset();
  openModal('newTripModal');
}

async function submitNewTrip(event) {
  event.preventDefault();
  const name = document.getElementById('tripNameInput').value.trim();
  const description = document.getElementById('tripDescInput').value.trim();
  const currency = document.getElementById('tripCurrencyInput').value;

  try {
    const res = await authFetch('/api/trips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, currency })
    });

    if (res.ok) {
      const data = await res.json();
      showToast(`Trip "${name}" created! 🗺️`);
      closeModal('newTripModal');
      currentTripId = data.id;
      await loadTrips();
    } else {
      showToast('Failed to create trip', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error creating trip', true);
  }
}

function openEditTripModal() {
  if (!currentTrip) return;
  document.getElementById('editTripName').value = currentTrip.name || '';
  document.getElementById('editTripDesc').value = currentTrip.description || '';
  document.getElementById('editTripCurrency').value = currentTrip.currency || '₹';
  openModal('editTripModal');
}

async function submitEditTrip(event) {
  event.preventDefault();
  if (!currentTripId) return;
  const name = document.getElementById('editTripName').value.trim();
  const description = document.getElementById('editTripDesc').value.trim();
  const currency = document.getElementById('editTripCurrency').value;

  if (!name) {
    showToast('Trip name cannot be empty', true);
    return;
  }

  try {
    const res = await authFetch(`/api/trips/${currentTripId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, currency })
    });

    if (res.ok) {
      showToast(`Trip "${name}" updated successfully! ✨`);
      closeModal('editTripModal');
      await loadTrips();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to update trip', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error updating trip', true);
  }
}

async function confirmDeleteTrip() {
  if (!currentTrip || !currentTripId) return;
  const tripName = currentTrip.name;
  const confirmed = confirm(`Are you sure you want to delete the trip "${tripName}"?\n\nThis will permanently delete all expenses, members, settlements, and fuel logs associated with this trip.`);
  if (!confirmed) return;

  try {
    const res = await authFetch(`/api/trips/${currentTripId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast(`Trip "${tripName}" deleted successfully`);
      currentTripId = null;
      currentTrip = null;
      await loadTrips();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to delete trip', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error deleting trip', true);
  }
}

function openAddMemberModal() {
  document.getElementById('addMemberForm').reset();
  openModal('addMemberModal');
}

async function submitNewMember(event) {
  event.preventDefault();
  const name = document.getElementById('memberNameInput').value.trim();
  const phone = document.getElementById('memberPhoneInput').value.trim();
  const avatar_color = document.getElementById('memberColorInput').value;

  try {
    const res = await authFetch(`/api/trips/${currentTripId}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, phone, avatar_color })
    });

    if (res.ok) {
      showToast(`Added traveler "${name}"! 👤`);
      closeModal('addMemberModal');
      await loadTripData(currentTripId);
    } else {
      showToast('Failed to add member', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error adding member', true);
  }
}

// ==================== BILL SCANNER & OCR AUTO-SPLIT ====================

let scanCurrentSplitType = 'equal';
let scannedRawOcrText = '';

// Sample receipt SVG illustrations
const SAMPLE_RECEIPT_SVGS = {
  gpay: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400" width="100%" height="100%"><rect width="300" height="400" rx="16" fill="%23ffffff"/><rect width="300" height="70" fill="%231E88E5"/><text x="150" y="42" fill="%23ffffff" font-family="sans-serif" font-size="18" font-weight="bold" text-anchor="middle">Google Pay</text><circle cx="150" cy="115" r="28" fill="%230F9D58"/><path d="M140 115 l7 7 l15 -15" stroke="%23ffffff" stroke-width="4" fill="none" stroke-linecap="round"/><text x="150" y="165" fill="%23333333" font-family="sans-serif" font-size="12" text-anchor="middle">Paid to</text><text x="150" y="185" fill="%23111827" font-family="sans-serif" font-size="16" font-weight="bold" text-anchor="middle">Fisherman's Wharf Goa</text><text x="150" y="235" fill="%230F9D58" font-family="sans-serif" font-size="28" font-weight="900" text-anchor="middle">₹ 2,450.00</text><rect x="30" y="260" width="240" height="1" fill="%23E5E7EB"/><text x="40" y="285" fill="%236B7280" font-family="sans-serif" font-size="11">Status: Completed</text><text x="40" y="305" fill="%236B7280" font-family="sans-serif" font-size="11">UPI ID: wharf@hdfcbank</text><text x="40" y="325" fill="%236B7280" font-family="sans-serif" font-size="11">Mode: UPI Transfer</text><text x="40" y="345" fill="%236B7280" font-family="sans-serif" font-size="11">Txn ID: 424567890123</text><rect x="30" y="365" width="240" height="20" rx="6" fill="%23E8F5E9"/><text x="150" y="379" fill="%232E7D32" font-family="sans-serif" font-size="10" font-weight="bold" text-anchor="middle">Payment Verified via UPI ✓</text></svg>`,
  restaurant: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400" width="100%" height="100%"><rect width="300" height="400" rx="12" fill="%23FFFDF9" stroke="%23E5E7EB"/><text x="150" y="35" fill="%23111827" font-family="serif" font-size="16" font-weight="bold" text-anchor="middle">THALASSA BEACH LOUNGE</text><text x="150" y="52" fill="%236B7280" font-family="sans-serif" font-size="10" text-anchor="middle">Small Vagator, Ozran Beach, Goa</text><line x1="25" y1="65" x2="275" y2="65" stroke="%23D1D5DB" stroke-dasharray="4"/><text x="30" y="85" fill="%234B5563" font-family="monospace" font-size="10">1x Greek Salad</text><text x="270" y="85" fill="%23111827" font-family="monospace" font-size="10" text-anchor="end">450.00</text><text x="30" y="105" fill="%234B5563" font-family="monospace" font-size="10">1x Calamari Butter</text><text x="270" y="105" fill="%23111827" font-family="monospace" font-size="10" text-anchor="end">680.00</text><text x="30" y="125" fill="%234B5563" font-family="monospace" font-size="10">1x Seafood Platter</text><text x="270" y="125" fill="%23111827" font-family="monospace" font-size="10" text-anchor="end">1250.00</text><text x="30" y="145" fill="%234B5563" font-family="monospace" font-size="10">3x Craft Cocktails</text><text x="270" y="145" fill="%23111827" font-family="monospace" font-size="10" text-anchor="end">900.00</text><line x1="25" y1="165" x2="275" y2="165" stroke="%23D1D5DB" stroke-dasharray="4"/><text x="30" y="185" fill="%234B5563" font-family="monospace" font-size="10">Sub Total</text><text x="270" y="185" fill="%234B5563" font-family="monospace" font-size="10" text-anchor="end">3280.00</text><text x="30" y="205" fill="%234B5563" font-family="monospace" font-size="10">Taxes (GST 5%)</text><text x="270" y="205" fill="%234B5563" font-family="monospace" font-size="10" text-anchor="end">164.00</text><text x="30" y="225" fill="%234B5563" font-family="monospace" font-size="10">Service Charge</text><text x="270" y="225" fill="%234B5563" font-family="monospace" font-size="10" text-anchor="end">164.00</text><line x1="25" y1="245" x2="275" y2="245" stroke="%23111827" stroke-width="2"/><text x="30" y="275" fill="%23111827" font-family="sans-serif" font-size="14" font-weight="bold">GRAND TOTAL</text><text x="270" y="275" fill="%23111827" font-family="sans-serif" font-size="18" font-weight="900" text-anchor="end">₹ 3,608.00</text><rect x="25" y="300" width="250" height="35" rx="8" fill="%23F3F4F6"/><text x="150" y="322" fill="%23374151" font-family="sans-serif" font-size="11" font-weight="bold" text-anchor="middle">Paid by: Credit Card (Visa)</text><text x="150" y="365" fill="%239CA3AF" font-family="sans-serif" font-size="10" text-anchor="middle">*** Thank You! Visit Again ***</text></svg>`,
  fuel: `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 400" width="100%" height="100%"><rect width="300" height="400" rx="12" fill="%23FFFDF0" stroke="%23E5E7EB"/><rect width="300" height="50" fill="%23FF8F00"/><text x="150" y="32" fill="%23ffffff" font-family="sans-serif" font-size="14" font-weight="bold" text-anchor="middle">INDIAN OIL CORPORATION LTD</text><text x="150" y="75" fill="%23374151" font-family="sans-serif" font-size="12" font-weight="bold" text-anchor="middle">COCO Panaji Goa Pump</text><line x1="25" y1="95" x2="275" y2="95" stroke="%23D1D5DB" stroke-dasharray="3"/><text x="30" y="125" fill="%234B5563" font-family="monospace" font-size="11">Product: Speed Petrol</text><text x="30" y="150" fill="%234B5563" font-family="monospace" font-size="11">Rate / Ltr: ₹ 98.40</text><text x="30" y="175" fill="%234B5563" font-family="monospace" font-size="11">Volume: 20.32 Ltr</text><line x1="25" y1="205" x2="275" y2="205" stroke="%23111827" stroke-width="2"/><text x="30" y="235" fill="%23111827" font-family="sans-serif" font-size="13" font-weight="bold">TOTAL SALE</text><text x="270" y="235" fill="%23B45309" font-family="sans-serif" font-size="20" font-weight="900" text-anchor="end">INR 2,000.00</text><line x1="25" y1="255" x2="275" y2="255" stroke="%23111827" stroke-width="2"/><text x="30" y="285" fill="%234B5563" font-family="monospace" font-size="11">Cash Tendered: 2000.00</text><text x="30" y="305" fill="%234B5563" font-family="monospace" font-size="11">Change Due: 0.00</text><text x="30" y="325" fill="%234B5563" font-family="monospace" font-size="11">Payment Mode: Cash</text><text x="150" y="370" fill="%236B7280" font-family="sans-serif" font-size="11" font-weight="bold" text-anchor="middle">SAVE FUEL YAANI SAVE MONEY</text></svg>`
};

function openBillScannerModal() {
  if (!currentTripId) {
    showToast('Please select or create a trip first', true);
    return;
  }
  if (members.length === 0) {
    showToast('Please add group members to this trip before scanning bills!', true);
    switchTab('members');
    return;
  }

  resetScanner();
  populateScanPayerDropdown();
  setScanSplitType('equal');

  const curr = currentTrip ? currentTrip.currency : '₹';
  const prefixEl = document.getElementById('scanCurrencyPrefix');
  if (prefixEl) prefixEl.innerText = curr;

  openModal('scanBillModal');
  setupDropzone();
}

function resetScanner() {
  const fileInp = document.getElementById('billFileInput');
  const camInp = document.getElementById('billCameraInput');
  if (fileInp) fileInp.value = '';
  if (camInp) camInp.value = '';

  const uploadArea = document.getElementById('scanUploadArea');
  const progressArea = document.getElementById('scanProgressArea');
  const resultArea = document.getElementById('scanResultArea');
  const rawBox = document.getElementById('rawOcrTextBox');

  if (uploadArea) uploadArea.classList.remove('hidden');
  if (progressArea) progressArea.classList.add('hidden');
  if (resultArea) resultArea.classList.add('hidden');
  if (rawBox) rawBox.classList.add('hidden');

  updateScanProgress(0, 'Initializing scanner...');
  lucide.createIcons();
}

function setupDropzone() {
  const dropzone = document.getElementById('scanDropzone');
  if (!dropzone || dropzone.dataset.bound) return;
  dropzone.dataset.bound = 'true';

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, e => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('border-emerald-600', 'bg-emerald-100/50');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, e => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('border-emerald-600', 'bg-emerald-100/50');
    });
  });

  dropzone.addEventListener('drop', e => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files[0]) {
      handleBillFile(dt.files[0]);
    }
  });
}

function onBillFileSelected(e) {
  if (e.target.files && e.target.files[0]) {
    handleBillFile(e.target.files[0]);
  }
}

function handleBillFile(file) {
  if (!file.type.startsWith('image/')) {
    showToast('Please select a valid image file (JPG, PNG, WebP)', true);
    return;
  }

  const reader = new FileReader();
  reader.onload = evt => {
    const dataUrl = evt.target.result;
    processReceiptImage(dataUrl);
  };
  reader.readAsDataURL(file);
}

function updateScanProgress(pct, statusText = null) {
  const bar = document.getElementById('scanProgressBar');
  const pctEl = document.getElementById('scanProgressPct');
  const txtEl = document.getElementById('scanStatusText');

  if (bar) bar.style.width = `${pct}%`;
  if (pctEl) pctEl.innerText = `${pct}%`;
  if (statusText && txtEl) txtEl.innerText = statusText;
}

function preprocessReceiptImage(imageSrc) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        // Upscale small phone screenshots / receipts so character strokes are distinct (>30px height)
        let scale = 1;
        const maxDim = Math.max(img.naturalWidth || img.width, img.naturalHeight || img.height);
        if (maxDim < 1400) {
          scale = 2.0;
        } else if (maxDim > 2800) {
          scale = 2800 / maxDim;
        }

        const w = Math.round((img.naturalWidth || img.width) * scale);
        const h = Math.round((img.naturalHeight || img.height) * scale);
        canvas.width = w;
        canvas.height = h;

        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(img, 0, 0, w, h);

        const imgData = ctx.getImageData(0, 0, w, h);
        const d = imgData.data;
        const factor = 1.25; // 25% contrast enhancement
        for (let i = 0; i < d.length; i += 4) {
          const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
          const enhanced = Math.min(255, Math.max(0, factor * (gray - 128) + 128));
          d[i] = enhanced;
          d[i + 1] = enhanced;
          d[i + 2] = enhanced;
        }
        ctx.putImageData(imgData, 0, 0);
        resolve(canvas);
      } catch (err) {
        console.warn('Preprocessing fallback:', err);
        resolve(imageSrc);
      }
    };
    img.onerror = () => resolve(imageSrc);
    img.src = imageSrc;
  });
}

async function processReceiptImage(imageSrc) {
  const uploadArea = document.getElementById('scanUploadArea');
  const progressArea = document.getElementById('scanProgressArea');
  const resultArea = document.getElementById('scanResultArea');

  uploadArea.classList.add('hidden');
  progressArea.classList.remove('hidden');
  resultArea.classList.add('hidden');

  document.getElementById('scanPreviewThumbnail').src = imageSrc;
  document.getElementById('scanResultImg').src = imageSrc;

  updateScanProgress(15, 'Loading image into OCR engine...');

  try {
    let recognizedText = '';

    // If Tesseract is loaded in browser
    if (typeof Tesseract !== 'undefined') {
      updateScanProgress(25, 'Optimizing image clarity for currency & text...');
      const processedCanvas = await preprocessReceiptImage(imageSrc);

      updateScanProgress(40, 'Scanning text & amounts...');
      const ocrResult = await Tesseract.recognize(processedCanvas, 'eng+hin', {
        langPath: window.location.origin + '/static/tessdata',
        logger: m => {
          if (m.status === 'recognizing text') {
            const pct = Math.min(90, Math.max(40, Math.round(m.progress * 100)));
            updateScanProgress(pct, `Recognizing text & amounts (${pct}%)...`);
          }
        }
      });
      recognizedText = ocrResult.data.text || '';
    }

    updateScanProgress(92, 'Extracting merchant, amount & payment mode...');

    // Call backend parser
    const parseRes = await authFetch('/api/receipts/parse-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: recognizedText })
    });

    let parsed = {};
    if (parseRes.ok) {
      parsed = await parseRes.json();
    } else {
      // Fallback
      parsed = {
        title: 'Scanned Expense',
        amount: 0.0,
        date: new Date().toISOString().split('T')[0],
        category: 'Food',
        payment_mode: 'UPI'
      };
    }

    updateScanProgress(100, 'Scan Complete!');
    setTimeout(() => {
      applyParsedReceipt(parsed, imageSrc, recognizedText || '(No clear text detected)');
    }, 400);

  } catch (err) {
    console.error('OCR Error:', err);
    updateScanProgress(100, 'Processing complete');
    applyParsedReceipt({
      title: 'Scanned Receipt',
      amount: 0.0,
      date: new Date().toISOString().split('T')[0],
      category: 'Food',
      payment_mode: 'UPI'
    }, imageSrc, '(OCR recognition error)');
  }
}

async function loadSampleReceipt(sampleId) {
  const uploadArea = document.getElementById('scanUploadArea');
  const progressArea = document.getElementById('scanProgressArea');
  const resultArea = document.getElementById('scanResultArea');

  uploadArea.classList.add('hidden');
  progressArea.classList.remove('hidden');
  resultArea.classList.add('hidden');

  const sampleSvg = SAMPLE_RECEIPT_SVGS[sampleId] || SAMPLE_RECEIPT_SVGS['gpay'];
  document.getElementById('scanPreviewThumbnail').src = sampleSvg;
  document.getElementById('scanResultImg').src = sampleSvg;

  // Animate scanner simulation
  updateScanProgress(20, 'Reading receipt image...');
  await new Promise(r => setTimeout(r, 200));
  updateScanProgress(60, 'Extracting amount & vendor...');
  await new Promise(r => setTimeout(r, 250));
  updateScanProgress(90, 'Classifying category & payment mode...');
  await new Promise(r => setTimeout(r, 200));

  try {
    const res = await authFetch('/api/receipts/samples');
    const data = await res.json();
    const sample = data.samples.find(s => s.id === sampleId) || data.samples[0];

    updateScanProgress(100, 'Scan Complete!');
    setTimeout(() => {
      applyParsedReceipt(sample.parsed, sampleSvg, sample.raw_text);
    }, 300);
  } catch (err) {
    console.error(err);
    resetScanner();
  }
}

function applyParsedReceipt(parsed, imageSrc, rawText) {
  const progressArea = document.getElementById('scanProgressArea');
  const resultArea = document.getElementById('scanResultArea');

  progressArea.classList.add('hidden');
  resultArea.classList.remove('hidden');

  document.getElementById('scanResultImg').src = imageSrc;
  document.getElementById('scanTitle').value = parsed.title || 'Scanned Expense';
  document.getElementById('scanAmount').value = parsed.amount > 0 ? parsed.amount.toFixed(2) : '';
  document.getElementById('scanDate').value = parsed.date || new Date().toISOString().split('T')[0];

  const catSelect = document.getElementById('scanCategory');
  if (catSelect) catSelect.value = parsed.category || 'Food';

  const modeSelect = document.getElementById('scanPaymentMode');
  if (modeSelect) modeSelect.value = parsed.payment_mode || 'UPI';

  scannedRawOcrText = rawText || '';
  const rawBox = document.getElementById('rawOcrTextBox');
  if (rawBox) rawBox.innerText = scannedRawOcrText;

  populateScanPayerDropdown();
  setScanSplitType('equal');
  lucide.createIcons();
}

function toggleRawOcrText() {
  const box = document.getElementById('rawOcrTextBox');
  const icon = document.getElementById('ocrToggleIcon');
  if (!box) return;

  if (box.classList.contains('hidden')) {
    box.classList.remove('hidden');
    if (icon) icon.className = 'w-3.5 h-3.5 text-slate-400 rotate-180 transition';
  } else {
    box.classList.add('hidden');
    if (icon) icon.className = 'w-3.5 h-3.5 text-slate-400 transition';
  }
}

function populateScanPayerDropdown() {
  const select = document.getElementById('scanPayer');
  if (!select) return;
  select.innerHTML = '';
  members.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.innerText = m.name;
    select.appendChild(opt);
  });
}

function setScanSplitType(type) {
  scanCurrentSplitType = type;

  ['equal', 'custom'].forEach(t => {
    const btn = document.getElementById(`scanSplitBtn-${t}`);
    if (!btn) return;
    if (t === type) {
      btn.className = 'py-1.5 px-3 rounded-lg text-xs font-bold bg-white text-brand-700 shadow-xs';
    } else {
      btn.className = 'py-1.5 px-3 rounded-lg text-xs font-bold text-slate-600 hover:text-slate-900';
    }
  });

  renderScanSplitMembers();
  recalculateScanSplits();
}

function renderScanSplitMembers() {
  const container = document.getElementById('scanSplitMembersContainer');
  if (!container) return;
  container.innerHTML = '';
  const curr = currentTrip ? currentTrip.currency : '₹';

  members.forEach(m => {
    const row = document.createElement('div');
    row.className = 'flex items-center justify-between p-2 rounded-xl bg-white border border-slate-200/80 text-xs';
    row.innerHTML = `
      <div class="flex items-center space-x-2.5">
        <input type="checkbox" checked value="${m.id}" onchange="recalculateScanSplits()" class="scan-split-member-checkbox w-4 h-4 rounded text-brand-600 focus:ring-brand-500 border-slate-300 cursor-pointer" />
        <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${m.avatar_color || '#4F46E5'}"></span>
        <span class="font-bold text-slate-800">${m.name}</span>
      </div>

      <div class="flex items-center space-x-2">
        ${scanCurrentSplitType === 'custom' ? `
          <div class="relative w-24">
            <span class="absolute inset-y-0 left-0 pl-1.5 flex items-center text-[11px] font-bold text-slate-400">${curr}</span>
            <input type="text" inputmode="decimal" placeholder="Fixed" data-mid="${m.id}" oninput="validateDecimalInput(this); recalculateScanSplits()" class="scan-custom-fixed-input w-full bg-slate-50 border border-slate-200 rounded-lg pl-5 pr-1.5 py-1 text-xs font-bold focus:outline-none focus:ring-1 focus:ring-brand-500 focus:bg-white text-right" />
          </div>
        ` : ''}
        <span class="font-bold text-slate-800 scan-member-split-preview min-w-[70px] text-right" data-mid="${m.id}">${curr}0.00</span>
      </div>
    `;
    container.appendChild(row);
  });
}

function recalculateScanSplits() {
  const totalAmount = parseFloat(document.getElementById('scanAmount').value) || 0.0;
  const curr = currentTrip ? currentTrip.currency : '₹';
  const statusEl = document.getElementById('scanSplitLiveStatus');
  if (!statusEl) return;

  if (scanCurrentSplitType === 'equal') {
    const checked = document.querySelectorAll('.scan-split-member-checkbox:checked');
    const count = checked.length;
    if (count === 0) {
      statusEl.innerHTML = `<span class="text-rose-600 font-bold">Select at least 1 member</span>`;
      return;
    }
    const perShare = totalAmount > 0 ? (totalAmount / count) : 0.0;
    statusEl.innerHTML = `<span class="text-emerald-700 font-bold">${curr}${perShare.toFixed(2)} each (${count} travelers)</span>`;

    document.querySelectorAll('.scan-split-member-checkbox').forEach(cb => {
      const mid = cb.value;
      const preview = document.querySelector(`.scan-member-split-preview[data-mid="${mid}"]`);
      if (preview) {
        preview.innerText = cb.checked ? `${curr}${perShare.toFixed(2)}` : `${curr}0.00`;
        preview.className = cb.checked ? 'font-bold text-slate-900 scan-member-split-preview min-w-[70px] text-right' : 'font-bold text-slate-300 scan-member-split-preview min-w-[70px] text-right';
      }
    });
  } else if (scanCurrentSplitType === 'custom') {
    const checkboxes = document.querySelectorAll('.scan-split-member-checkbox');
    let totalFixed = 0;
    let remainderMembers = [];

    checkboxes.forEach(cb => {
      const mid = cb.value;
      const inp = document.querySelector(`.scan-custom-fixed-input[data-mid="${mid}"]`);
      const val = inp ? parseFloat(inp.value) : 0;
      if (cb.checked) {
        if (val && val > 0) totalFixed += val;
        else remainderMembers.push(mid);
      }
    });

    totalFixed = Math.round(totalFixed * 100) / 100;
    const remainingAmount = Math.round((totalAmount - totalFixed) * 100) / 100;

    if (remainingAmount < -0.01) {
      statusEl.innerHTML = `<span class="text-rose-600 font-bold">Fixed exceeds bill by ${curr}${Math.abs(remainingAmount).toFixed(2)}</span>`;
    } else if (remainderMembers.length > 0) {
      const perRem = Math.round((remainingAmount / remainderMembers.length) * 100) / 100;
      statusEl.innerHTML = `<span class="text-emerald-700 font-bold">Fixed: ${curr}${totalFixed.toFixed(2)} | Rem.: ${curr}${remainingAmount.toFixed(2)} (${curr}${perRem.toFixed(2)} each)</span>`;
    } else {
      statusEl.innerHTML = `<span class="text-emerald-700 font-bold">Exact match ✓</span>`;
    }

    checkboxes.forEach(cb => {
      const mid = cb.value;
      const inp = document.querySelector(`.scan-custom-fixed-input[data-mid="${mid}"]`);
      const preview = document.querySelector(`.scan-member-split-preview[data-mid="${mid}"]`);
      if (!preview) return;

      if (!cb.checked) {
        preview.innerText = `${curr}0.00`;
        if (inp) inp.disabled = true;
        return;
      }
      if (inp) inp.disabled = false;
      const val = inp ? parseFloat(inp.value) : 0;
      if (val && val > 0) {
        preview.innerHTML = `<span class="text-indigo-600 font-bold">[Fix]</span> ${curr}${val.toFixed(2)}`;
      } else if (remainderMembers.length > 0 && remainingAmount >= 0) {
        const perRem = Math.round((remainingAmount / remainderMembers.length) * 100) / 100;
        preview.innerHTML = `<span class="text-emerald-600 font-bold">[Rem]</span> ${curr}${perRem.toFixed(2)}`;
      } else {
        preview.innerText = `${curr}0.00`;
      }
    });
  }
}

async function submitScannedExpense(event) {
  event.preventDefault();
  const totalAmount = parseFloat(document.getElementById('scanAmount').value);
  if (!totalAmount || totalAmount <= 0) {
    showToast('Please enter a valid bill amount', true);
    return;
  }

  const title = document.getElementById('scanTitle').value.trim();
  const date = document.getElementById('scanDate').value;
  const category = document.getElementById('scanCategory').value;
  const payerId = parseInt(document.getElementById('scanPayer').value);
  const paymentMode = document.getElementById('scanPaymentMode').value;

  let splits = [];

  if (scanCurrentSplitType === 'equal') {
    const checked = Array.from(document.querySelectorAll('.scan-split-member-checkbox:checked')).map(cb => parseInt(cb.value));
    if (checked.length === 0) {
      showToast('Please select at least one traveler to split with', true);
      return;
    }
    const count = checked.length;
    const perShare = Math.round((totalAmount / count) * 100) / 100;
    let allocated = 0;
    checked.forEach((mid, idx) => {
      let share = perShare;
      if (idx === count - 1) share = Math.round((totalAmount - allocated) * 100) / 100;
      else allocated += share;
      splits.push({ member_id: mid, share_amount: share, percentage: Math.round((100 / count) * 100) / 100 });
    });
  } else if (scanCurrentSplitType === 'custom') {
    const checkboxes = document.querySelectorAll('.scan-split-member-checkbox');
    let totalFixed = 0;
    let fixedList = [];
    let remainderMembers = [];

    checkboxes.forEach(cb => {
      if (cb.checked) {
        const mid = parseInt(cb.value);
        const inp = document.querySelector(`.scan-custom-fixed-input[data-mid="${mid}"]`);
        const val = inp ? parseFloat(inp.value) : 0;
        if (val && val > 0) {
          totalFixed += val;
          fixedList.push({ mid, val });
        } else {
          remainderMembers.push(mid);
        }
      }
    });

    totalFixed = Math.round(totalFixed * 100) / 100;
    const remainingAmount = Math.round((totalAmount - totalFixed) * 100) / 100;

    if (remainingAmount < -0.05) {
      showToast(`Fixed amounts (${totalFixed.toFixed(2)}) exceed total expense (${totalAmount.toFixed(2)})`, true);
      return;
    }

    let allocated = 0;
    fixedList.forEach(item => {
      splits.push({ member_id: item.mid, share_amount: item.val, percentage: Math.round((item.val / totalAmount) * 1000) / 10 });
      allocated += item.val;
    });

    if (remainderMembers.length > 0) {
      const count = remainderMembers.length;
      const perRemainder = Math.round((remainingAmount / count) * 100) / 100;
      let remAllocated = 0;
      remainderMembers.forEach((mid, idx) => {
        let share = perRemainder;
        if (idx === count - 1) share = Math.round((remainingAmount - remAllocated) * 100) / 100;
        else remAllocated += share;
        splits.push({ member_id: mid, share_amount: share, percentage: Math.round((share / totalAmount) * 1000) / 10 });
      });
    }
  }

  const payload = {
    title,
    amount: totalAmount,
    date,
    category,
    payer_id: payerId,
    payment_mode: paymentMode,
    split_type: scanCurrentSplitType,
    splits,
    notes: 'Scanned from receipt image'
  };

  try {
    const res = await authFetch(`/api/trips/${currentTripId}/expenses`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast(`Scanned bill "${title}" logged & split successfully! 🎉`);
      closeModal('scanBillModal');
      await loadTripData(currentTripId);
    } else {
      const errData = await res.json();
      showToast(errData.detail || 'Failed to save scanned expense', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error saving scanned expense', true);
  }
}

// =========================================================================
// FUEL & MILEAGE TRACKING LOGIC (Car & Bike, CNG / Petrol / Diesel)
// =========================================================================

async function fetchVehicleCatalogs() {
  if (vehicleCatalogs) return vehicleCatalogs;
  try {
    const res = await authFetch('/api/mileage/catalogs');
    if (res.ok) {
      vehicleCatalogs = await res.json();
      return vehicleCatalogs;
    }
  } catch (err) {
    console.error('Error fetching vehicle catalogs:', err);
  }
  return null;
}

async function loadMileageData(tripId = currentTripId) {
  if (!tripId) return;
  try {
    // 1. Fetch trip vehicle
    const vRes = await authFetch(`/api/trips/${tripId}/vehicle`);
    currentTripVehicle = vRes.ok ? await vRes.json() : null;

    // 2. Fetch fuel logs
    const lRes = await authFetch(`/api/trips/${tripId}/fuel-logs`);
    const lData = lRes.ok ? await lRes.json() : [];
    currentFuelLogs = Array.isArray(lData) ? lData : (lData.logs || []);

    // 3. Fetch summary
    const sRes = await authFetch(`/api/trips/${tripId}/mileage-summary`);
    currentMileageSummary = sRes.ok ? await sRes.json() : null;

    renderMileageTab();
    renderDashboardMileageWidget();
  } catch (err) {
    console.error('Error loading mileage data:', err);
  }
}

function renderMileageTab() {
  const summary = currentMileageSummary;
  const vehicle = currentTripVehicle;
  const isCng = vehicle && vehicle.fuel_type === 'CNG';
  const qtyUnit = isCng ? 'kg' : 'L';
  const mileageUnit = isCng ? 'km/kg' : 'km/L';

  // 1. Update navigation badge
  const navBadge = document.getElementById('navMileageBadge');
  if (navBadge) {
    if (summary && summary.total_distance_km > 0) {
      navBadge.innerText = `${summary.total_distance_km} km`;
    } else if (vehicle) {
      navBadge.innerText = `${vehicle.fuel_type}`;
    } else {
      navBadge.innerText = '0 km';
    }
  }

  // 2. Render Vehicle Status Info Banner
  const bannerEl = document.getElementById('vehicleConfigBanner');
  if (bannerEl) {
    if (vehicle) {
      const typeEmoji = vehicle.vehicle_type === 'Bike' ? '🏍️' : '🚗';
      const fuelBadgeColor = vehicle.fuel_type === 'CNG' ? 'bg-emerald-100 text-emerald-800 border-emerald-300' :
                             (vehicle.fuel_type === 'Diesel' ? 'bg-blue-100 text-blue-800 border-blue-300' : 'bg-amber-100 text-amber-800 border-amber-300');

      bannerEl.innerHTML = `
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div class="flex items-center space-x-3.5">
            <div class="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-2xl shrink-0">
              ${typeEmoji}
            </div>
            <div>
              <div class="flex items-center space-x-2 flex-wrap gap-y-1">
                <h3 class="text-lg font-black text-slate-900">${vehicle.brand_model}</h3>
                <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border ${fuelBadgeColor}">
                  ${vehicle.fuel_type}
                </span>
                <span class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                  ${vehicle.vehicle_type}
                </span>
              </div>
              <div class="flex items-center space-x-3 text-xs text-slate-500 mt-1 flex-wrap gap-y-1">
                <span>Claimed Benchmark: <strong class="text-slate-800">${vehicle.benchmark_mileage} ${mileageUnit}</strong></span>
                <span>&bull;</span>
                <span>Trip Starting Odometer: <strong class="text-slate-800">${(vehicle.initial_odometer || 0).toLocaleString()} km</strong></span>
                <span>&bull;</span>
                <span>Latest Odometer: <strong class="text-slate-800">${summary ? (summary.latest_odometer || vehicle.initial_odometer || 0).toLocaleString() : (vehicle.initial_odometer || 0).toLocaleString()} km</strong></span>
              </div>
            </div>
          </div>
          <div class="flex items-center space-x-2 shrink-0">
            <button onclick="openVehicleSetupModal()" class="px-3.5 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 shadow-2xs">
              <i data-lucide="edit-2" class="w-3.5 h-3.5"></i>
              <span>Edit Vehicle</span>
            </button>
          </div>
        </div>
      `;
    } else {
      bannerEl.innerHTML = `
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 py-2">
          <div class="flex items-center space-x-3.5">
            <div class="w-12 h-12 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-2xl shrink-0">
              🚗
            </div>
            <div>
              <h3 class="text-base font-bold text-slate-900">Setup your Trip Vehicle (Car or Bike)</h3>
              <p class="text-xs text-slate-500 mt-0.5">
                Choose your vehicle brand &amp; model (e.g. Maruti Suzuki Ertiga CNG) to start calculating real mileage, fuel consumption, and running cost per km.
              </p>
            </div>
          </div>
          <button onclick="openVehicleSetupModal()" class="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition shadow-xs flex items-center space-x-1.5 shrink-0">
            <i data-lucide="plus-circle" class="w-4 h-4"></i>
            <span>Configure Vehicle</span>
          </button>
        </div>
      `;
    }
  }

  // 3. Update KPI metric cards
  if (summary) {
    const kpiDistance = document.getElementById('mileageKpiDistance');
    if (kpiDistance) kpiDistance.innerText = `${summary.total_distance_km} km`;

    const kpiOdoSub = document.getElementById('mileageKpiOdoSub');
    if (kpiOdoSub) kpiOdoSub.innerText = `Departure: ${(summary.initial_odometer || 0).toLocaleString()} km → Latest: ${(summary.latest_odometer || 0).toLocaleString()} km`;

    const kpiMileage = document.getElementById('mileageKpiMileage');
    if (kpiMileage) kpiMileage.innerText = summary.average_mileage.toFixed(2);

    const kpiUnit = document.getElementById('mileageKpiUnit');
    if (kpiUnit) kpiUnit.innerText = summary.mileage_unit;

    const kpiBenchSub = document.getElementById('mileageKpiBenchmarkSub');
    if (kpiBenchSub) kpiBenchSub.innerText = `Benchmark: ${summary.benchmark_mileage} ${summary.mileage_unit} (${summary.efficiency_percentage}% achieved)`;

    const kpiFuelQty = document.getElementById('mileageKpiFuelQty');
    if (kpiFuelQty) kpiFuelQty.innerText = summary.total_fuel_quantity.toFixed(1);

    const kpiFuelUnit = document.getElementById('mileageKpiFuelUnit');
    if (kpiFuelUnit) kpiFuelUnit.innerText = summary.quantity_unit;

    const kpiFuelCostSub = document.getElementById('mileageKpiFuelCostSub');
    if (kpiFuelCostSub) kpiFuelCostSub.innerText = `Total Cost: ₹${summary.total_fuel_cost.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    const kpiCostPerKm = document.getElementById('mileageKpiCostPerKm');
    if (kpiCostPerKm) kpiCostPerKm.innerText = `₹${summary.cost_per_km.toFixed(2)}`;

    const kpiCostPerPersonSub = document.getElementById('mileageKpiCostPerPersonSub');
    if (kpiCostPerPersonSub) kpiCostPerPersonSub.innerText = `₹${summary.cost_per_person_km.toFixed(2)} / member-km (${members.length || 1} travelers)`;

    const kpiEfficiencyPct = document.getElementById('mileageKpiEfficiencyPct');
    if (kpiEfficiencyPct) kpiEfficiencyPct.innerText = `${summary.efficiency_percentage}%`;

    const kpiRatingLabel = document.getElementById('mileageKpiRatingLabel');
    if (kpiRatingLabel) kpiRatingLabel.innerText = summary.efficiency_label;
  }

  // 4. Update Fuel Logs table
  const tableBody = document.getElementById('fuelLogsTableBody');
  const emptyState = document.getElementById('fuelLogsEmptyState');
  const countBadge = document.getElementById('fuelLogsCountBadge');

  if (countBadge) countBadge.innerText = `${currentFuelLogs.length} Stop${currentFuelLogs.length === 1 ? '' : 's'}`;

  if (!currentFuelLogs || currentFuelLogs.length === 0) {
    if (tableBody) tableBody.innerHTML = '';
    if (emptyState) emptyState.classList.remove('hidden');
  } else {
    if (emptyState) emptyState.classList.add('hidden');
    if (tableBody) {
      tableBody.innerHTML = currentFuelLogs.map(log => {
        const runDistText = log.calculated_segment_distance > 0 ? `+${log.calculated_segment_distance} km` : '-';
        const segMileageText = log.calculated_segment_mileage > 0 ? `${log.calculated_segment_mileage} ${summary ? summary.mileage_unit : 'km/L'}` : '-';
        const splitBadge = log.expense_id
          ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Split in Group ✓</span>`
          : `<span class="text-slate-400 text-xs">-</span>`;
        const tankBadge = log.is_full_tank
          ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">Full Tank</span>`
          : `<span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">Partial</span>`;

        const payerAvatar = log.payer_name
          ? `<div class="flex items-center space-x-1.5">
               <div class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center font-bold" style="background-color: ${log.payer_color || '#6366F1'}">
                 ${log.payer_name.charAt(0).toUpperCase()}
               </div>
               <span class="text-xs font-medium text-slate-800">${log.payer_name}</span>
             </div>`
          : `<span class="text-xs text-slate-400">-</span>`;

        return `
          <tr class="hover:bg-slate-50/70 transition">
            <td class="px-3.5 py-3 whitespace-nowrap font-medium text-slate-800">${log.date}</td>
            <td class="px-3.5 py-3 whitespace-nowrap font-bold text-slate-900">${(log.odometer_reading || 0).toLocaleString()} km</td>
            <td class="px-3.5 py-3 whitespace-nowrap font-semibold text-indigo-700">${runDistText}</td>
            <td class="px-3.5 py-3 whitespace-nowrap font-medium text-slate-800">${log.fuel_quantity} ${summary ? summary.quantity_unit : 'kg'}</td>
            <td class="px-3.5 py-3 whitespace-nowrap text-slate-600">₹${log.fuel_price_per_unit ? log.fuel_price_per_unit.toFixed(2) : '-'}</td>
            <td class="px-3.5 py-3 whitespace-nowrap font-bold text-slate-900">₹${(log.fuel_amount || 0).toFixed(2)}</td>
            <td class="px-3.5 py-3 whitespace-nowrap font-bold text-emerald-600">${segMileageText}</td>
            <td class="px-3.5 py-3 whitespace-nowrap">${tankBadge}</td>
            <td class="px-3.5 py-3 whitespace-nowrap">${payerAvatar}</td>
            <td class="px-3.5 py-3 whitespace-nowrap">${splitBadge}</td>
            <td class="px-3.5 py-3 whitespace-nowrap text-right">
              <button onclick="deleteFuelLog(${log.id})" class="text-slate-400 hover:text-rose-600 p-1.5 rounded-lg hover:bg-rose-50 transition" title="Delete fuel stop">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }
  }

  lucide.createIcons();
}

function renderDashboardMileageWidget() {
  const card = document.getElementById('dashMileageCard');
  if (!card) return;

  if (!currentTripVehicle && (!currentFuelLogs || currentFuelLogs.length === 0)) {
    card.classList.add('hidden');
    return;
  }

  card.classList.remove('hidden');
  const vehicle = currentTripVehicle || {
    brand_model: 'Maruti Suzuki Ertiga',
    fuel_type: 'CNG',
    vehicle_type: 'Car'
  };
  const summary = currentMileageSummary;

  const iconWrap = document.getElementById('dashVehIconWrap');
  if (iconWrap) iconWrap.innerText = vehicle.vehicle_type === 'Bike' ? '🏍️' : '🚗';

  const modelEl = document.getElementById('dashVehModel');
  if (modelEl) modelEl.innerText = vehicle.brand_model;

  const fuelEl = document.getElementById('dashVehFuelBadge');
  if (fuelEl) fuelEl.innerText = vehicle.fuel_type;

  const ratingBadge = document.getElementById('dashVehRatingBadge');
  if (ratingBadge && summary) {
    ratingBadge.innerText = `${summary.efficiency_percentage}% Benchmark`;
  }

  const distEl = document.getElementById('dashVehDistance');
  if (distEl) distEl.innerText = summary ? `${summary.total_distance_km} km` : '0 km';

  const mileageEl = document.getElementById('dashVehMileage');
  if (mileageEl) mileageEl.innerText = summary ? `${summary.average_mileage.toFixed(2)} ${summary.mileage_unit}` : '0.00';

  const costEl = document.getElementById('dashVehCostPerKm');
  if (costEl) costEl.innerText = summary ? `₹${summary.cost_per_km.toFixed(2)} / km` : '₹0.00 / km';

  lucide.createIcons();
}

// --- VEHICLE SETUP MODAL HANDLERS ---

async function openVehicleSetupModal() {
  await fetchVehicleCatalogs();
  const veh = currentTripVehicle;
  const initialType = veh ? veh.vehicle_type : 'Car';

  selectVehicleType(initialType);

  if (veh) {
    populateVehicleModelDropdown(initialType, veh.brand_model);
    selectFuelType(veh.fuel_type);
    document.getElementById('vehBenchmarkMileage').value = veh.benchmark_mileage;
    document.getElementById('vehInitialOdometer').value = veh.initial_odometer;
  } else {
    // Default to Maruti Suzuki Ertiga CNG
    populateVehicleModelDropdown('Car', 'Maruti Suzuki Ertiga');
    selectFuelType('CNG');
    document.getElementById('vehBenchmarkMileage').value = '26.11';
    document.getElementById('vehInitialOdometer').value = '0';
  }

  openModal('vehicleSetupModal');
  lucide.createIcons();
}

function selectVehicleType(type) {
  document.getElementById('vehTypeInput').value = type;

  const carBtn = document.getElementById('vehTypeBtn-Car');
  const bikeBtn = document.getElementById('vehTypeBtn-Bike');

  if (type === 'Car') {
    carBtn.className = 'py-2.5 px-4 rounded-xl text-xs font-bold border-2 border-indigo-600 bg-indigo-50 text-indigo-700 flex items-center justify-center space-x-2 transition';
    bikeBtn.className = 'py-2.5 px-4 rounded-xl text-xs font-bold border-2 border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 flex items-center justify-center space-x-2 transition';

    // Show CNG and Diesel buttons for cars
    document.getElementById('fuelTypeBtn-CNG').classList.remove('hidden');
    document.getElementById('fuelTypeBtn-Diesel').classList.remove('hidden');
  } else {
    bikeBtn.className = 'py-2.5 px-4 rounded-xl text-xs font-bold border-2 border-indigo-600 bg-indigo-50 text-indigo-700 flex items-center justify-center space-x-2 transition';
    carBtn.className = 'py-2.5 px-4 rounded-xl text-xs font-bold border-2 border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 flex items-center justify-center space-x-2 transition';

    // Two-wheelers in India are predominantly petrol
    document.getElementById('fuelTypeBtn-CNG').classList.add('hidden');
    document.getElementById('fuelTypeBtn-Diesel').classList.add('hidden');
    selectFuelType('Petrol');
  }

  populateVehicleModelDropdown(type);
  onVehicleModelSelectChange();
}

function populateVehicleModelDropdown(type, selectedModel = null) {
  const select = document.getElementById('vehModelSelect');
  if (!select) return;

  const list = (vehicleCatalogs && vehicleCatalogs[type]) ? vehicleCatalogs[type] : [];
  let html = '';

  list.forEach(item => {
    const isSelected = selectedModel && selectedModel.toLowerCase() === item.model.toLowerCase();
    html += `<option value="${item.model}" ${isSelected ? 'selected' : ''}>${item.model}</option>`;
  });

  const isCustom = selectedModel && !list.some(i => i.model.toLowerCase() === selectedModel.toLowerCase());
  html += `<option value="Custom" ${isCustom ? 'selected' : ''}>+ Custom / Other ${type}</option>`;

  select.innerHTML = html;

  const customWrap = document.getElementById('customModelWrap');
  if (isCustom) {
    select.value = 'Custom';
    customWrap.classList.remove('hidden');
    document.getElementById('vehCustomModelInput').value = selectedModel;
  } else {
    customWrap.classList.add('hidden');
  }
}

function onVehicleModelSelectChange() {
  const select = document.getElementById('vehModelSelect');
  if (!select) return;

  const modelVal = select.value;
  const customWrap = document.getElementById('customModelWrap');

  if (modelVal === 'Custom') {
    customWrap.classList.remove('hidden');
    return;
  } else {
    customWrap.classList.add('hidden');
  }

  // Lookup model in catalog to get benchmark
  const type = document.getElementById('vehTypeInput').value;
  const list = (vehicleCatalogs && vehicleCatalogs[type]) ? vehicleCatalogs[type] : [];
  const found = list.find(item => item.model === modelVal);

  if (found) {
    const currentFuel = document.getElementById('vehFuelTypeInput').value;
    // Check if current fuel exists in model
    if (found.fuels[currentFuel]) {
      document.getElementById('vehBenchmarkMileage').value = found.fuels[currentFuel].benchmark;
    } else {
      // Pick first available fuel
      const firstFuel = Object.keys(found.fuels)[0];
      selectFuelType(firstFuel);
      document.getElementById('vehBenchmarkMileage').value = found.fuels[firstFuel].benchmark;
    }
  }
}

function selectFuelType(fuel) {
  document.getElementById('vehFuelTypeInput').value = fuel;

  const fuels = ['CNG', 'Petrol', 'Diesel'];
  fuels.forEach(f => {
    const btn = document.getElementById(`fuelTypeBtn-${f}`);
    if (!btn) return;
    if (f === fuel) {
      if (f === 'CNG') btn.className = 'py-2 px-3 rounded-xl text-xs font-bold border-2 border-emerald-600 bg-emerald-50 text-emerald-700 flex items-center justify-center space-x-1.5 transition';
      else if (f === 'Diesel') btn.className = 'py-2 px-3 rounded-xl text-xs font-bold border-2 border-blue-600 bg-blue-50 text-blue-700 flex items-center justify-center space-x-1.5 transition';
      else btn.className = 'py-2 px-3 rounded-xl text-xs font-bold border-2 border-amber-600 bg-amber-50 text-amber-700 flex items-center justify-center space-x-1.5 transition';
    } else {
      btn.className = 'py-2 px-3 rounded-xl text-xs font-bold border-2 border-slate-200 bg-slate-50 text-slate-600 hover:border-slate-300 flex items-center justify-center space-x-1.5 transition';
    }
  });

  // Update benchmark unit label
  const unitLabel = document.getElementById('vehBenchmarkUnitLabel');
  if (unitLabel) {
    unitLabel.innerText = fuel === 'CNG' ? 'km/kg' : 'km/L';
  }

  // Auto-refresh benchmark from model if possible
  const select = document.getElementById('vehModelSelect');
  if (select && select.value !== 'Custom') {
    const type = document.getElementById('vehTypeInput').value;
    const list = (vehicleCatalogs && vehicleCatalogs[type]) ? vehicleCatalogs[type] : [];
    const found = list.find(item => item.model === select.value);
    if (found && found.fuels[fuel]) {
      document.getElementById('vehBenchmarkMileage').value = found.fuels[fuel].benchmark;
    }
  }
}

async function submitVehicleSetup(e) {
  e.preventDefault();
  if (!currentTripId) return;

  const vehicleType = document.getElementById('vehTypeInput').value;
  const selectVal = document.getElementById('vehModelSelect').value;
  const customVal = document.getElementById('vehCustomModelInput').value.trim();
  const brandModel = (selectVal === 'Custom') ? (customVal || `Custom ${vehicleType}`) : selectVal;

  const fuelType = document.getElementById('vehFuelTypeInput').value;
  const benchmarkMileage = parseFloat(document.getElementById('vehBenchmarkMileage').value) || 20.0;
  const initialOdometer = parseFloat(document.getElementById('vehInitialOdometer').value) || 0.0;

  const payload = {
    vehicle_type: vehicleType,
    brand_model: brandModel,
    fuel_type: fuelType,
    benchmark_mileage: benchmarkMileage,
    initial_odometer: initialOdometer
  };

  try {
    const res = await authFetch(`/api/trips/${currentTripId}/vehicle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast(`Vehicle configured: ${brandModel} (${fuelType}) 🚗`);
      closeModal('vehicleSetupModal');
      await loadMileageData(currentTripId);
    } else {
      const errData = await res.json();
      showToast(errData.detail || 'Failed to save vehicle settings', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error saving vehicle settings', true);
  }
}

// --- FUEL LOG MODAL HANDLERS ---

function openLogFuelModal() {
  if (!currentTripId) return;

  // 1. Pre-fill date with today
  const today = new Date().toISOString().split('T')[0];
  document.getElementById('fuelDate').value = today;

  // 2. Set previous odometer hint
  const prevOdo = (currentMileageSummary && currentMileageSummary.latest_odometer > 0)
    ? currentMileageSummary.latest_odometer
    : (currentTripVehicle ? (currentTripVehicle.initial_odometer || 0) : 0);
  document.getElementById('fuelPrevOdoHint').innerText = prevOdo.toLocaleString();

  // 3. Set unit labels
  const isCng = currentTripVehicle && currentTripVehicle.fuel_type === 'CNG';
  const qtyUnit = isCng ? 'kg' : 'L';
  const rateUnit = isCng ? '₹/kg' : '₹/L';

  document.getElementById('fuelQtyUnitLabel').innerText = qtyUnit;
  document.getElementById('fuelRateUnitLabel').innerText = rateUnit;

  // 4. Populate payer dropdown
  const payerSelect = document.getElementById('fuelPayer');
  payerSelect.innerHTML = members.map(m => `<option value="${m.id}">${m.name}</option>`).join('');

  // 5. Clear input fields
  document.getElementById('fuelOdometer').value = '';
  document.getElementById('fuelQuantity').value = '';
  document.getElementById('fuelPrice').value = '';
  document.getElementById('fuelAmount').value = '';
  document.getElementById('fuelNotes').value = '';
  document.getElementById('fuelIsFullTank').checked = true;
  document.getElementById('fuelAddToExpenses').checked = true;

  openModal('logFuelModal');
  lucide.createIcons();
}

function onFuelCalcChange(trigger) {
  const qtyInput = document.getElementById('fuelQuantity');
  const priceInput = document.getElementById('fuelPrice');
  const amountInput = document.getElementById('fuelAmount');

  const qty = parseFloat(qtyInput.value) || 0;
  const rate = parseFloat(priceInput.value) || 0;
  const amount = parseFloat(amountInput.value) || 0;

  if (trigger === 'qty' || trigger === 'rate') {
    if (qty > 0 && rate > 0) {
      amountInput.value = (qty * rate).toFixed(2);
    }
  } else if (trigger === 'amount') {
    if (amount > 0 && rate > 0) {
      qtyInput.value = (amount / rate).toFixed(2);
    }
  }
}

async function submitFuelLog(e) {
  e.preventDefault();
  if (!currentTripId) return;

  const date = document.getElementById('fuelDate').value;
  const odometerReading = parseFloat(document.getElementById('fuelOdometer').value) || 0.0;
  const fuelQuantity = parseFloat(document.getElementById('fuelQuantity').value) || 0.0;
  const fuelPrice = parseFloat(document.getElementById('fuelPrice').value) || 0.0;
  const fuelAmount = parseFloat(document.getElementById('fuelAmount').value) || 0.0;
  const isFullTank = document.getElementById('fuelIsFullTank').checked;
  const payerId = parseInt(document.getElementById('fuelPayer').value, 10);
  const addToExpenses = document.getElementById('fuelAddToExpenses').checked;
  const notes = document.getElementById('fuelNotes').value.trim();

  if (fuelQuantity <= 0) {
    showToast('Please enter fuel quantity filled', true);
    return;
  }
  if (fuelAmount <= 0) {
    showToast('Please enter total fuel amount paid', true);
    return;
  }

  const payload = {
    date,
    odometer_reading: odometerReading,
    fuel_quantity: fuelQuantity,
    fuel_price_per_unit: fuelPrice > 0 ? fuelPrice : (fuelAmount / fuelQuantity),
    fuel_amount: fuelAmount,
    is_full_tank: isFullTank,
    payer_id: payerId,
    add_to_expenses: addToExpenses,
    notes: notes || 'Fuel stop refilling'
  };

  try {
    const res = await authFetch(`/api/trips/${currentTripId}/fuel-logs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast(`Fuel stop logged: ${fuelQuantity} ${currentTripVehicle && currentTripVehicle.fuel_type === 'CNG' ? 'kg' : 'L'} (₹${fuelAmount}) ⛽`);
      closeModal('logFuelModal');

      // If added to expenses, refresh full trip data (expenses, settlement, dashboard)
      if (addToExpenses) {
        await loadTripData(currentTripId);
      } else {
        await loadMileageData(currentTripId);
      }
    } else {
      const errData = await res.json();
      showToast(errData.detail || 'Failed to save fuel stop', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error saving fuel stop', true);
  }
}

async function deleteFuelLog(logId) {
  if (!confirm('Are you sure you want to delete this fuel stop?')) return;
  if (!currentTripId) return;

  try {
    const res = await authFetch(`/api/trips/${currentTripId}/fuel-logs/${logId}`, {
      method: 'DELETE'
    });

    if (res.ok) {
      showToast('Fuel stop deleted');
      await loadTripData(currentTripId);
    } else {
      const errData = await res.json();
      showToast(errData.detail || 'Failed to delete fuel stop', true);
    }
  } catch (err) {
    console.error(err);
    showToast('Error deleting fuel stop', true);
  }
}


