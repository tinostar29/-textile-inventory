// State Management
let currentUser = null;
let currentView = 'dashboard';
let currentFinishedStockTab = ''; // '' for all, or 'Tape', 'Rope', 'Tipping'
let mastersData = { machines: [], yarns: [], colours: [], settings: {} };
let suppliersList = [];
let customersList = [];
let rawStockCache = [];
let finishedStockCache = [];

let monthlyChart = null;
let stockDonutChart = null;

// Helpers
const fmtKg = (val) => `${parseFloat(val || 0).toFixed(3)} KG`;
const fmtCurr = (val) => `₹ ${parseFloat(val || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) lucide.createIcons();
  setupEventListeners();
  await checkAuth();
});

// Setup Form and Button Listeners
function setupEventListeners() {
  // Mobile Sidebar Toggle
  const toggleBtn = document.getElementById('sidebar-toggle');
  const mobileBtn = document.getElementById('mobile-menu-btn');
  const sidebar = document.getElementById('sidebar');

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('-translate-x-full');
    });
  }
  if (mobileBtn) {
    mobileBtn.addEventListener('click', () => {
      sidebar.classList.toggle('hidden');
    });
  }

  // Login Form
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }

  // Forms
  document.getElementById('form-purchase')?.addEventListener('submit', submitPurchase);
  document.getElementById('form-production')?.addEventListener('submit', submitProduction);
  document.getElementById('form-sale')?.addEventListener('submit', submitSale);
  document.getElementById('form-customer')?.addEventListener('submit', submitCustomer);
  document.getElementById('form-supplier')?.addEventListener('submit', submitSupplier);
  document.getElementById('form-user')?.addEventListener('submit', submitUser);
  document.getElementById('form-change-password')?.addEventListener('submit', submitChangePassword);
  document.getElementById('settings-company-form')?.addEventListener('submit', saveSettings);

  // Search & Filter listeners
  document.getElementById('purchases-search')?.addEventListener('input', debounce(loadPurchases, 300));
  document.getElementById('purchases-supplier-filter')?.addEventListener('change', loadPurchases);
  document.getElementById('raw-stock-search')?.addEventListener('input', debounce(loadRawStock, 300));
  document.getElementById('production-search')?.addEventListener('input', debounce(loadProduction, 300));
  document.getElementById('finished-stock-search')?.addEventListener('input', debounce(loadFinishedStock, 300));
  document.getElementById('sales-search')?.addEventListener('input', debounce(loadSales, 300));
  document.getElementById('sales-product-filter')?.addEventListener('change', loadSales);
  document.getElementById('sales-payment-filter')?.addEventListener('change', loadSales);
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// --- Authentication ---

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.authenticated) {
      currentUser = data.user;
      showAppScreen();
      await loadInitialData();
    } else {
      showLoginScreen();
    }
  } catch (err) {
    console.error('Auth check error:', err);
    showLoginScreen();
  }
}

function showLoginScreen() {
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('app-layout').classList.add('hidden');
  if (window.lucide) lucide.createIcons();
}

function showAppScreen() {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app-layout').classList.remove('hidden');

  if (currentUser) {
    document.getElementById('user-display-name').textContent = currentUser.full_name || currentUser.username;
    document.getElementById('user-display-role').textContent = currentUser.role.toUpperCase();
    const initials = (currentUser.full_name || currentUser.username)
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
    document.getElementById('user-avatar-initials').textContent = initials;
  }
  if (window.lucide) lucide.createIcons();
}

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById('login-username').value;
  const password = document.getElementById('login-password').value;

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();

    if (data.success) {
      currentUser = data.user;
      showAppScreen();
      await loadInitialData();
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'success',
        title: `Welcome back, ${currentUser.full_name}!`,
        showConfirmButton: false,
        timer: 2000
      });
    } else {
      Swal.fire('Login Failed', data.message || 'Invalid credentials.', 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Unable to connect to server.', 'error');
  }
}

function openChangePasswordModal() {
  const form = document.getElementById('form-change-password');
  if (form) form.reset();
  const modal = document.getElementById('modal-change-password');
  if (modal) {
    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
    setTimeout(() => {
      document.getElementById('cp-current')?.focus();
    }, 50);
  }
}

async function submitChangePassword(e) {
  e.preventDefault();
  const currentPassword = document.getElementById('cp-current').value;
  const newPassword = document.getElementById('cp-new').value;
  const confirmPassword = document.getElementById('cp-confirm').value;

  if (newPassword !== confirmPassword) {
    Swal.fire('Error', 'New password and confirm password do not match.', 'warning');
    return;
  }

  if (newPassword.length < 4) {
    Swal.fire('Error', 'New password must be at least 4 characters long.', 'warning');
    return;
  }

  try {
    const res = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      })
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-change-password');
      Swal.fire('Success', data.message, 'success');
    } else {
      Swal.fire('Error', data.message, 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Unable to change password.', 'error');
  }
}

async function performLogout() {
  const result = await Swal.fire({
    title: 'Log out?',
    text: 'Are you sure you want to end your current session?',
    icon: 'question',
    showCancelButton: true,
    confirmButtonColor: '#4f46e5',
    confirmButtonText: 'Yes, Log out'
  });

  if (result.isConfirmed) {
    await fetch('/api/auth/logout', { method: 'POST' });
    currentUser = null;
    showLoginScreen();
  }
}

// --- Initial Data Load ---

async function loadInitialData() {
  await Promise.all([
    loadMasters(),
    loadSuppliersList(),
    loadCustomersList()
  ]);
  navigateView('dashboard');
}

async function loadMasters() {
  try {
    const res = await fetch('/api/masters');
    const data = await res.json();
    if (data.success) {
      mastersData = data;
      populateDatalists();
      populateSettingsForm();
    }
  } catch (e) {
    console.error('Error loading masters:', e);
  }
}

function populateDatalists() {
  const yarnList = document.getElementById('list-yarn-types');
  if (yarnList) {
    yarnList.innerHTML = mastersData.yarns.map(y => `<option value="${y.name}">`).join('');
  }
  const colourList = document.getElementById('list-yarn-colours');
  if (colourList) {
    colourList.innerHTML = mastersData.colours.map(c => `<option value="${c.name}">`).join('');
  }

  // Populate Machine dropdown in production
  const machineSelect = document.getElementById('prod-machine');
  if (machineSelect) {
    machineSelect.innerHTML = '<option value="">Select Machine</option>' +
      mastersData.machines.map(m => `<option value="${m.name}">${m.name} (${m.code || ''})</option>`).join('');
  }
}

async function loadSuppliersList() {
  try {
    const res = await fetch('/api/suppliers');
    const data = await res.json();
    if (data.success) {
      suppliersList = data.data;
      const selects = [document.getElementById('p-supplier'), document.getElementById('purchases-supplier-filter')];
      selects.forEach(sel => {
        if (!sel) return;
        const isFilter = sel.id === 'purchases-supplier-filter';
        sel.innerHTML = isFilter ? '<option value="">All Suppliers</option>' : '<option value="">Select Supplier</option>';
        suppliersList.forEach(s => {
          sel.innerHTML += `<option value="${s.id}">${s.name}</option>`;
        });
      });
    }
  } catch (e) {
    console.error('Error loading suppliers:', e);
  }
}

async function loadCustomersList() {
  try {
    const res = await fetch('/api/customers');
    const data = await res.json();
    if (data.success) {
      customersList = data.data;
      const sel = document.getElementById('s-customer');
      if (sel) {
        sel.innerHTML = '<option value="">Select Customer</option>' +
          customersList.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
      }
    }
  } catch (e) {
    console.error('Error loading customers:', e);
  }
}

// --- Navigation ---

function navigateView(viewName, param = null) {
  currentView = viewName;

  // Hide all sections
  document.querySelectorAll('main > section').forEach(sec => sec.classList.add('hidden'));

  // Show selected section
  const activeSec = document.getElementById(`view-${viewName}`);
  if (activeSec) activeSec.classList.remove('hidden');

  // Update navigation styling
  document.querySelectorAll('.nav-link').forEach(btn => {
    if (btn.getAttribute('data-nav') === viewName) {
      btn.className = 'nav-link w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition text-white bg-indigo-600/90 shadow-sm';
    } else {
      btn.className = 'nav-link w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition hover:bg-slate-800 hover:text-white text-slate-300';
    }
  });

  // Update Topbar Title
  const titles = {
    'dashboard': ['Dashboard', 'Overview of textile inventory, machines and sales'],
    'purchases': ['Yarn Purchases', 'Record raw cotton & polyester yarn purchases with auto-stock addition'],
    'raw-stock': ['Raw Material Stock', 'Live balances of yarn types, counts & colours ready for production'],
    'production': ['Production Management', 'Input raw yarn → Twisting/Weaving → Tape, Rope & Tipping with Wastage Tracking'],
    'finished-stock': ['Finished Goods Stock', 'Tape, Rope & Tipping stocks produced and available for sale'],
    'sales': ['Sales & Invoicing', 'Customer orders, finished stock deduction, invoice generation & payments'],
    'customers': ['Customers Directory', 'Garment manufacturers purchasing narrow fabrics, cords & tipping'],
    'suppliers': ['Suppliers Directory', 'Spinning mills & dealers supplying raw yarn'],
    'reports': ['Reports & Analytics', 'Export formatted Excel (.xlsx) and PDF reports'],
    'settings': ['Settings & System Utilities', 'Company profile, user management, backup and demo seeding']
  };

  const [t, sub] = titles[viewName] || ['Textile System', ''];
  document.getElementById('view-title').textContent = t;
  document.getElementById('view-subtitle').textContent = sub;

  // View specific loaders
  if (viewName === 'dashboard') loadDashboard();
  else if (viewName === 'purchases') loadPurchases();
  else if (viewName === 'raw-stock') loadRawStock();
  else if (viewName === 'production') loadProduction();
  else if (viewName === 'finished-stock') {
    if (param) setFinishedStockTab(param);
    else loadFinishedStock();
  }
  else if (viewName === 'sales') loadSales();
  else if (viewName === 'customers') loadCustomers();
  else if (viewName === 'suppliers') loadSuppliers();
  else if (viewName === 'settings') loadSettings();

  if (window.lucide) lucide.createIcons();
}

// --- Dashboard Logic ---

async function loadDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    const json = await res.json();
    if (!json.success) return;
    const d = json.data;

    // KPI Cards in KG
    document.getElementById('kpi-yarn-purchased').textContent = fmtKg(d.cards.total_yarn_purchased_kg);
    document.getElementById('kpi-raw-yarn-available').textContent = fmtKg(d.cards.available_raw_yarn_stock_kg);
    document.getElementById('kpi-yarn-used').textContent = fmtKg(d.cards.total_yarn_used_kg);
    document.getElementById('kpi-production-waste').textContent = fmtKg(d.cards.total_production_waste_kg);
    document.getElementById('kpi-waste-pct').textContent = `${d.cards.wastage_percentage}%`;
    
    document.getElementById('kpi-tape-stock').textContent = fmtKg(d.cards.total_tape_stock_kg);
    document.getElementById('kpi-rope-stock').textContent = fmtKg(d.cards.total_rope_stock_kg);
    document.getElementById('kpi-tipping-stock').textContent = fmtKg(d.cards.total_tipping_stock_kg);
    document.getElementById('kpi-goods-sold').textContent = fmtKg(d.cards.total_finished_goods_sold_kg);

    // Sidebar Live Indicator
    document.getElementById('sidebar-live-stock').textContent = fmtKg(d.cards.available_raw_yarn_stock_kg);
    document.getElementById('subnav-tape-kg').textContent = fmtKg(d.cards.total_tape_stock_kg);
    document.getElementById('subnav-rope-kg').textContent = fmtKg(d.cards.total_rope_stock_kg);
    document.getElementById('subnav-tipping-kg').textContent = fmtKg(d.cards.total_tipping_stock_kg);

    // Financial Cards
    document.getElementById('kpi-total-purchases-val').textContent = fmtCurr(d.cards.total_purchase_amount);
    document.getElementById('kpi-total-sales-val').textContent = fmtCurr(d.cards.total_sales_amount);
    document.getElementById('kpi-outstanding-val').textContent = fmtCurr(d.cards.total_outstanding_receivables);

    // Alert Center
    renderAlerts(d.low_stock_alerts);

    // Recent lists
    renderRecentLists(d);

    // Charts
    renderDashboardCharts(d);

  } catch (e) {
    console.error('Error loading dashboard:', e);
  }
}

function renderAlerts(alerts) {
  const count = alerts.total_alert_count;
  const badge = document.getElementById('alert-count-badge');
  const banner = document.getElementById('dashboard-alert-banner');
  const dropdownItems = document.getElementById('alert-dropdown-items');
  const dropdownHeader = document.getElementById('alert-dropdown-header');

  if (count > 0) {
    badge.textContent = count;
    badge.classList.remove('hidden');
    banner.classList.remove('hidden');
    dropdownHeader.textContent = `${count} Alert${count > 1 ? 's' : ''}`;

    let html = '';
    alerts.raw_yarn.forEach(r => {
      html += `
        <div class="p-2 rounded bg-rose-50 border border-rose-200 text-rose-900">
          <p class="font-bold flex items-center justify-between">
            <span>Raw: ${r.yarn_type} (${r.yarn_colour})</span>
            <span class="text-rose-700 font-mono">${fmtKg(r.remaining_kg)}</span>
          </p>
          <p class="text-[10px] text-rose-600 mt-0.5">Threshold: 25 KG — Restock required</p>
        </div>`;
    });
    alerts.finished_goods.forEach(f => {
      html += `
        <div class="p-2 rounded bg-amber-50 border border-amber-200 text-amber-900">
          <p class="font-bold flex items-center justify-between">
            <span>${f.product_type}: ${f.colour}</span>
            <span class="text-amber-800 font-mono">${fmtKg(f.available_kg)}</span>
          </p>
          <p class="text-[10px] text-amber-600 mt-0.5">Threshold: 15 KG — Run production</p>
        </div>`;
    });
    dropdownItems.innerHTML = html;
  } else {
    badge.classList.add('hidden');
    banner.classList.add('hidden');
    dropdownHeader.textContent = 'All stocks healthy';
    dropdownItems.innerHTML = '<p class="text-slate-400 py-3 text-center">No low-stock alerts.</p>';
  }
}

function toggleAlertDropdown() {
  document.getElementById('alert-dropdown').classList.toggle('hidden');
}

function renderRecentLists(d) {
  // Purchases
  const pList = document.getElementById('recent-purchases-list');
  pList.innerHTML = d.recent_purchases.length === 0 ? '<p class="text-slate-400 py-2">No purchases yet.</p>' :
    d.recent_purchases.map(p => `
      <div class="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
        <div>
          <p class="font-semibold text-slate-800">${p.yarn_type} <span class="text-slate-500 font-normal">(${p.yarn_colour})</span></p>
          <p class="text-[10px] text-slate-400">${p.supplier_name || 'Direct'} • ${p.purchase_date}</p>
        </div>
        <div class="text-right">
          <p class="font-mono font-bold text-slate-900">${fmtKg(p.weight_kg)}</p>
          <p class="text-[10px] text-emerald-600 font-semibold">${fmtCurr(p.total_amount)}</p>
        </div>
      </div>
    `).join('');

  // Production
  const prList = document.getElementById('recent-productions-list');
  prList.innerHTML = d.recent_productions.length === 0 ? '<p class="text-slate-400 py-2">No production runs yet.</p>' :
    d.recent_productions.map(p => `
      <div class="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
        <div>
          <p class="font-semibold text-slate-800">${p.batch_number}</p>
          <p class="text-[10px] text-slate-500">${p.finished_summary || 'Finished goods'}</p>
        </div>
        <div class="text-right">
          <p class="font-mono font-bold text-indigo-700">${fmtKg(p.input_weight_kg)} in</p>
          <p class="text-[10px] text-rose-500 font-medium">${fmtKg(p.wastage_weight_kg)} waste</p>
        </div>
      </div>
    `).join('');

  // Sales
  const sList = document.getElementById('recent-sales-list');
  sList.innerHTML = d.recent_sales.length === 0 ? '<p class="text-slate-400 py-2">No sales recorded yet.</p>' :
    d.recent_sales.map(s => `
      <div class="p-2 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-between">
        <div>
          <p class="font-semibold text-slate-800">${s.customer_name || 'Customer'} • <span class="text-indigo-600">${s.product_type}</span></p>
          <p class="text-[10px] text-slate-400">${s.invoice_number} • ${s.sale_date}</p>
        </div>
        <div class="text-right">
          <p class="font-mono font-bold text-slate-900">${fmtKg(s.quantity_kg)}</p>
          <span class="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold ${
            s.payment_status === 'Paid' ? 'bg-emerald-100 text-emerald-800' :
            s.payment_status === 'Partial' ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'
          }">${s.payment_status}</span>
        </div>
      </div>
    `).join('');
}

function renderDashboardCharts(d) {
  // 1. Monthly Purchase vs Sales Chart
  const ctxTrend = document.getElementById('monthlyTrendChart');
  if (ctxTrend) {
    if (monthlyChart) monthlyChart.destroy();
    const months = d.monthly_overview.map(m => m.m);
    const purchaseKg = d.monthly_overview.map(m => m.purchase_kg);
    const salesKg = d.monthly_overview.map(m => m.sales_kg);

    monthlyChart = new Chart(ctxTrend, {
      type: 'bar',
      data: {
        labels: months.length ? months : ['No Data'],
        datasets: [
          {
            label: 'Yarn Purchased (KG)',
            data: purchaseKg.length ? purchaseKg : [0],
            backgroundColor: '#6366f1',
            borderRadius: 6
          },
          {
            label: 'Finished Goods Sold (KG)',
            data: salesKg.length ? salesKg : [0],
            backgroundColor: '#10b981',
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, font: { family: 'Inter', size: 11 } } }
        },
        scales: {
          y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
          x: { grid: { display: false } }
        }
      }
    });
  }

  // 2. Stock Weight Donut Chart
  const ctxDonut = document.getElementById('stockDonutChart');
  if (ctxDonut) {
    if (stockDonutChart) stockDonutChart.destroy();
    const rawKg = d.cards.available_raw_yarn_stock_kg;
    const tapeKg = d.cards.total_tape_stock_kg;
    const ropeKg = d.cards.total_rope_stock_kg;
    const tippingKg = d.cards.total_tipping_stock_kg;
    const wasteKg = d.cards.total_production_waste_kg;

    stockDonutChart = new Chart(ctxDonut, {
      type: 'doughnut',
      data: {
        labels: ['Raw Yarn', 'Tape Stock', 'Rope Stock', 'Tipping Stock', 'Wastage'],
        datasets: [{
          data: [rawKg, tapeKg, ropeKg, tippingKg, wasteKg],
          backgroundColor: ['#4f46e5', '#10b981', '#14b8a6', '#06b6d4', '#f43f5e'],
          borderWidth: 2,
          borderColor: '#ffffff'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { boxWidth: 10, font: { family: 'Inter', size: 10 } } }
        },
        cutout: '65%'
      }
    });
  }
}

// --- Purchases Module ---

async function loadPurchases() {
  const search = document.getElementById('purchases-search')?.value || '';
  const supplierId = document.getElementById('purchases-supplier-filter')?.value || '';
  
  let url = `/api/purchases?search=${encodeURIComponent(search)}`;
  if (supplierId) url += `&supplier_id=${supplierId}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    const tbody = document.getElementById('purchases-table-body');
    if (!data.success || !data.data.length) {
      tbody.innerHTML = `<tr><td colspan="11" class="text-center py-6 text-slate-400">No purchase records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.data.map(p => `
      <tr class="hover:bg-slate-50 transition ${p.status === 'CANCELLED' ? 'opacity-50 bg-slate-50 line-through' : ''}">
        <td class="py-3 px-4 font-mono">${p.purchase_date}</td>
        <td class="py-3 px-4 font-semibold text-slate-800">${p.invoice_number || '-'}</td>
        <td class="py-3 px-4">${p.supplier_name || 'Direct'}</td>
        <td class="py-3 px-4 font-medium text-slate-900">${p.yarn_type}</td>
        <td class="py-3 px-4">${p.yarn_colour}</td>
        <td class="py-3 px-4 text-center font-mono">${p.bags_cones || 0}</td>
        <td class="py-3 px-4 text-right font-mono font-bold text-slate-900">${fmtKg(p.weight_kg)}</td>
        <td class="py-3 px-4 text-right font-mono">${fmtCurr(p.price_per_kg)}</td>
        <td class="py-3 px-4 text-right font-mono font-bold text-indigo-700">${fmtCurr(p.total_amount)}</td>
        <td class="py-3 px-4 text-center">
          <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold ${p.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}">
            ${p.status}
          </span>
        </td>
        <td class="py-3 px-4 text-center">
          ${p.status === 'ACTIVE' ? `
            <button onclick="cancelPurchase(${p.id})" title="Cancel purchase & reverse stock" class="p-1 text-slate-400 hover:text-rose-600 transition">
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>` : '-'}
        </td>
      </tr>
    `).join('');

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error('Error loading purchases:', e);
  }
}

function openPurchaseModal() {
  document.getElementById('form-purchase').reset();
  document.getElementById('p-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('p-total-preview').textContent = '₹ 0.00';
  document.getElementById('modal-purchase').classList.remove('hidden');
}

function calcPurchaseTotal() {
  const wt = parseFloat(document.getElementById('p-weight').value || 0);
  const pr = parseFloat(document.getElementById('p-price').value || 0);
  document.getElementById('p-total-preview').textContent = fmtCurr(wt * pr);
}

async function submitPurchase(e) {
  e.preventDefault();
  const payload = {
    purchase_date: document.getElementById('p-date').value,
    supplier_id: document.getElementById('p-supplier').value,
    yarn_type: document.getElementById('p-yarn-type').value,
    yarn_colour: document.getElementById('p-yarn-colour').value,
    bags_cones: document.getElementById('p-bags').value,
    weight_kg: document.getElementById('p-weight').value,
    price_per_kg: document.getElementById('p-price').value,
    invoice_number: document.getElementById('p-invoice').value,
    notes: document.getElementById('p-notes').value
  };

  try {
    const res = await fetch('/api/purchases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-purchase');
      Swal.fire('Saved', data.message, 'success');
      loadPurchases();
      loadDashboard();
    } else {
      Swal.fire('Validation Error', data.message, 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Unable to record purchase.', 'error');
  }
}

async function cancelPurchase(id) {
  const result = await Swal.fire({
    title: 'Cancel Purchase?',
    text: 'This will atomically deduct the purchased weight from raw stock. If the yarn has already been used in production, cancellation will be blocked.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#ef4444',
    confirmButtonText: 'Yes, Cancel Purchase'
  });

  if (result.isConfirmed) {
    try {
      const res = await fetch(`/api/purchases/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Cancelled', data.message, 'success');
        loadPurchases();
        loadDashboard();
      } else {
        Swal.fire('Action Blocked', data.message, 'error');
      }
    } catch (e) {
      Swal.fire('Error', 'Failed to cancel purchase.', 'error');
    }
  }
}

// --- Raw Yarn Stock Module ---

async function loadRawStock() {
  const search = document.getElementById('raw-stock-search')?.value || '';
  try {
    const res = await fetch(`/api/raw-stock?search=${encodeURIComponent(search)}`);
    const data = await res.json();
    if (!data.success) return;

    rawStockCache = data.data;

    let totAvail = 0;
    let lowCount = 0;
    rawStockCache.forEach(r => {
      totAvail += r.remaining_kg;
      if (r.status !== 'Normal') lowCount++;
    });

    document.getElementById('raw-stock-total-available').textContent = fmtKg(totAvail);
    document.getElementById('raw-stock-types-count').textContent = rawStockCache.length;
    document.getElementById('raw-stock-low-count').textContent = lowCount;

    const tbody = document.getElementById('raw-stock-table-body');
    if (!rawStockCache.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-slate-400">No raw stock records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = rawStockCache.map(r => `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 px-4 font-bold text-slate-900">${r.yarn_type}</td>
        <td class="py-3 px-4">${r.yarn_colour}</td>
        <td class="py-3 px-4 text-center font-mono">${r.purchase_count}</td>
        <td class="py-3 px-4 text-right font-mono">${fmtKg(r.purchased_kg)}</td>
        <td class="py-3 px-4 text-right font-mono text-amber-700">${fmtKg(r.used_kg)}</td>
        <td class="py-3 px-4 text-right font-mono font-extrabold text-sm ${r.remaining_kg <= 0 ? 'text-rose-600' : 'text-indigo-700'}">
          ${fmtKg(r.remaining_kg)}
        </td>
        <td class="py-3 px-4 text-right font-mono">${fmtCurr(r.avg_price_per_kg)}</td>
        <td class="py-3 px-4 text-center">
          <span class="inline-block px-2.5 py-0.5 rounded text-[10px] font-bold ${
            r.status === 'Normal' ? 'badge-healthy' :
            r.status === 'Low Stock' ? 'badge-low' : 'badge-out'
          }">${r.status}</span>
        </td>
        <td class="py-3 px-4 text-center">
          <button onclick="startProductionWithRaw('${r.yarn_type}', '${r.yarn_colour}')"
            class="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-600 hover:text-white text-indigo-700 font-semibold rounded transition text-[11px]">
            Send to Prod
          </button>
        </td>
      </tr>
    `).join('');

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error('Error loading raw stock:', e);
  }
}

function startProductionWithRaw(yarnType, colour) {
  openProductionModal();
  setTimeout(() => {
    document.getElementById('prod-yarn-type').value = yarnType;
    updateProductionColours(yarnType);
    document.getElementById('prod-yarn-colour').value = colour;
    updateProductionRawStockHint();
  }, 100);
}

// --- Production Management Module ---

async function loadProduction() {
  const search = document.getElementById('production-search')?.value || '';
  try {
    const res = await fetch(`/api/productions?search=${encodeURIComponent(search)}`);
    const data = await res.json();
    const tbody = document.getElementById('production-table-body');
    if (!data.success || !data.data.length) {
      tbody.innerHTML = `<tr><td colspan="11" class="text-center py-6 text-slate-400">No production runs recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.data.map(p => {
      const itemsSummary = (p.items || []).map(i => `
        <span class="inline-block px-2 py-0.5 bg-slate-100 rounded text-[10px] font-mono mr-1">
          <b>${i.product_type}</b>: ${fmtKg(i.weight_kg)} (${i.colour})
        </span>
      `).join('');

      return `
        <tr class="hover:bg-slate-50 transition ${p.status === 'CANCELLED' ? 'opacity-50 bg-slate-50 line-through' : ''}">
          <td class="py-3 px-4 font-mono font-bold text-slate-800">${p.batch_number}</td>
          <td class="py-3 px-4 font-mono">${p.production_date}</td>
          <td class="py-3 px-4">${p.machine_name}</td>
          <td class="py-3 px-4">${p.operator_name || '-'}</td>
          <td class="py-3 px-4 font-medium">${p.input_yarn_type} (${p.input_yarn_colour})</td>
          <td class="py-3 px-4 text-right font-mono font-bold text-amber-800">${fmtKg(p.input_weight_kg)}</td>
          <td class="py-3 px-4">${itemsSummary}</td>
          <td class="py-3 px-4 text-right font-mono font-bold text-emerald-700">${fmtKg(p.total_finished_weight_kg)}</td>
          <td class="py-3 px-4 text-right font-mono font-bold text-rose-600">${fmtKg(p.wastage_weight_kg)}</td>
          <td class="py-3 px-4 text-center">
            <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold ${p.status === 'ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}">
              ${p.status}
            </span>
          </td>
          <td class="py-3 px-4 text-center">
            ${p.status === 'ACTIVE' ? `
              <button onclick="cancelProduction(${p.id})" title="Cancel batch (reverts raw yarn & finished goods)" class="p-1 text-slate-400 hover:text-rose-600 transition">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
              </button>` : '-'}
          </td>
        </tr>
      `;
    }).join('');

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error('Error loading production:', e);
  }
}

async function openProductionModal() {
  document.getElementById('form-production').reset();
  document.getElementById('prod-date').value = new Date().toISOString().split('T')[0];

  // Refresh raw stock list in dropdown
  await loadRawStock();
  const typeSelect = document.getElementById('prod-yarn-type');
  const uniqueTypes = [...new Set(rawStockCache.map(r => r.yarn_type))];
  typeSelect.innerHTML = '<option value="">Select Yarn</option>' +
    uniqueTypes.map(t => `<option value="${t}">${t}</option>`).join('');

  typeSelect.onchange = () => {
    updateProductionColours(typeSelect.value);
    updateProductionRawStockHint();
  };

  // Reset finished items container to 1 row
  const container = document.getElementById('prod-items-container');
  container.innerHTML = `
    <div class="prod-item-row grid grid-cols-12 gap-2 items-center">
      <div class="col-span-5">
        <select class="prod-item-type w-full p-2 bg-white border border-slate-300 rounded" onchange="calcProductionBalance()">
          <option value="Tape">Finished Tape</option>
          <option value="Rope">Finished Rope</option>
          <option value="Tipping">Finished Tipping</option>
        </select>
      </div>
      <div class="col-span-4">
        <input type="text" class="prod-item-colour w-full p-2 bg-white border border-slate-300 rounded" placeholder="Colour (default same)">
      </div>
      <div class="col-span-3 flex items-center gap-1">
        <input type="number" class="prod-item-weight w-full p-2 bg-white border border-slate-300 rounded font-mono font-bold"
          step="0.001" min="0.001" placeholder="Weight KG" oninput="calcProductionBalance()" required>
      </div>
    </div>
  `;

  calcProductionBalance();
  document.getElementById('modal-production').classList.remove('hidden');
}

function updateProductionColours(selectedType) {
  const colourSelect = document.getElementById('prod-yarn-colour');
  const availableColours = rawStockCache.filter(r => r.yarn_type === selectedType).map(r => r.yarn_colour);
  colourSelect.innerHTML = '<option value="">Select Colour</option>' +
    availableColours.map(c => `<option value="${c}">${c}</option>`).join('');
}

function updateProductionRawStockHint() {
  const yarnType = document.getElementById('prod-yarn-type').value;
  const colour = document.getElementById('prod-yarn-colour').value;
  const hint = document.getElementById('prod-avail-preview');

  if (!yarnType || !colour) {
    hint.textContent = 'Select yarn to see stock';
    hint.className = 'text-indigo-700 font-semibold text-[11px]';
    return;
  }

  const match = rawStockCache.find(r => r.yarn_type === yarnType && r.yarn_colour === colour);
  const remaining = match ? match.remaining_kg : 0.0;

  hint.textContent = `Available Raw Stock: ${fmtKg(remaining)}`;
  hint.className = remaining > 0 ? 'text-emerald-700 font-bold text-[11px]' : 'text-rose-600 font-bold text-[11px]';

  // Also auto-fill colour in first output item row if blank
  const firstColourInput = document.querySelector('.prod-item-colour');
  if (firstColourInput && !firstColourInput.value) {
    firstColourInput.value = colour;
  }
}

function addProductionItemRow() {
  const container = document.getElementById('prod-items-container');
  const div = document.createElement('div');
  div.className = 'prod-item-row grid grid-cols-12 gap-2 items-center';
  const defaultColour = document.getElementById('prod-yarn-colour').value || '';

  div.innerHTML = `
    <div class="col-span-5">
      <select class="prod-item-type w-full p-2 bg-white border border-slate-300 rounded" onchange="calcProductionBalance()">
        <option value="Tape">Finished Tape</option>
        <option value="Rope">Finished Rope</option>
        <option value="Tipping">Finished Tipping</option>
      </select>
    </div>
    <div class="col-span-4">
      <input type="text" class="prod-item-colour w-full p-2 bg-white border border-slate-300 rounded" value="${defaultColour}" placeholder="Colour">
    </div>
    <div class="col-span-3 flex items-center gap-1">
      <input type="number" class="prod-item-weight w-full p-2 bg-white border border-slate-300 rounded font-mono font-bold"
        step="0.001" min="0.001" placeholder="Weight KG" oninput="calcProductionBalance()" required>
      <button type="button" onclick="this.closest('.prod-item-row').remove(); calcProductionBalance();" class="p-1 text-slate-400 hover:text-rose-600">
        <i data-lucide="x" class="w-4 h-4"></i>
      </button>
    </div>
  `;
  container.appendChild(div);
  if (window.lucide) lucide.createIcons();
  calcProductionBalance();
}

function calcProductionBalance() {
  const inputWt = parseFloat(document.getElementById('prod-input-weight').value || 0);
  const wastageInput = document.getElementById('prod-wastage-weight');
  let wastageWt = parseFloat(wastageInput.value || 0);

  // Sum all finished weights
  let finishedSum = 0;
  document.querySelectorAll('.prod-item-weight').forEach(inp => {
    finishedSum += parseFloat(inp.value || 0);
  });

  // Auto-calculate suggested wastage if input > finishedSum and user hasn't explicitly entered a conflicting value
  if (inputWt > finishedSum && wastageWt === 0) {
    wastageWt = parseFloat((inputWt - finishedSum).toFixed(3));
    wastageInput.value = wastageWt.toFixed(3);
  }

  // Update formula bar preview
  document.getElementById('prod-calc-input').textContent = inputWt.toFixed(3);
  document.getElementById('prod-calc-finished').textContent = finishedSum.toFixed(3);
  document.getElementById('prod-calc-wastage').textContent = wastageWt.toFixed(3);

  const statusEl = document.getElementById('prod-balance-status');
  const submitBtn = document.getElementById('btn-submit-production');
  const expectedInput = parseFloat((finishedSum + wastageWt).toFixed(3));
  const diff = Math.abs(inputWt - expectedInput);

  if (inputWt <= 0) {
    statusEl.innerHTML = `<span class="text-slate-500">Enter input yarn weight.</span>`;
    submitBtn.disabled = true;
    return;
  }

  if (diff < 0.002) {
    statusEl.innerHTML = `<span class="text-emerald-600 font-bold flex items-center gap-1">✓ Balanced! (Input = Finished + Wastage)</span>`;
    submitBtn.disabled = false;
  } else {
    statusEl.innerHTML = `<span class="text-rose-600 font-bold">✕ Mismatch: Input is ${inputWt.toFixed(3)} KG, but Outputs + Wastage = ${expectedInput.toFixed(3)} KG (Diff: ${diff.toFixed(3)} KG)</span>`;
    submitBtn.disabled = true;
  }
}

async function submitProduction(e) {
  e.preventDefault();
  const inputWeight = parseFloat(document.getElementById('prod-input-weight').value || 0);
  const yarnType = document.getElementById('prod-yarn-type').value;
  const colour = document.getElementById('prod-yarn-colour').value;

  // Build items array
  const items = [];
  document.querySelectorAll('.prod-item-row').forEach(row => {
    const type = row.querySelector('.prod-item-type').value;
    const itemColour = row.querySelector('.prod-item-colour').value || colour;
    const wt = parseFloat(row.querySelector('.prod-item-weight').value || 0);
    if (wt > 0) {
      items.push({ product_type: type, colour: itemColour, weight_kg: wt });
    }
  });

  const payload = {
    production_date: document.getElementById('prod-date').value,
    machine_name: document.getElementById('prod-machine').value,
    operator_name: document.getElementById('prod-operator').value,
    input_yarn_type: yarnType,
    input_yarn_colour: colour,
    input_weight_kg: inputWeight,
    items: items,
    wastage_weight_kg: parseFloat(document.getElementById('prod-wastage-weight').value || 0),
    notes: document.getElementById('prod-notes').value
  };

  try {
    const res = await fetch('/api/productions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-production');
      Swal.fire('Production Saved!', data.message, 'success');
      loadProduction();
      loadDashboard();
    } else {
      Swal.fire('Validation Error', data.message, 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Unable to record production entry.', 'error');
  }
}

async function cancelProduction(id) {
  const result = await Swal.fire({
    title: 'Cancel Production Batch?',
    text: 'This will reverse the batch: raw yarn is returned to stock, and finished goods are deducted. If any finished items have already been sold, cancellation is blocked.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#ef4444',
    confirmButtonText: 'Yes, Cancel Batch'
  });

  if (result.isConfirmed) {
    try {
      const res = await fetch(`/api/productions/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Cancelled', data.message, 'success');
        loadProduction();
        loadDashboard();
      } else {
        Swal.fire('Action Blocked', data.message, 'error');
      }
    } catch (e) {
      Swal.fire('Error', 'Failed to cancel production batch.', 'error');
    }
  }
}

// --- Finished Goods Stock Module ---

function setFinishedStockTab(tabName) {
  currentFinishedStockTab = tabName;
  ['all', 'Tape', 'Rope', 'Tipping'].forEach(t => {
    const btn = document.getElementById(`fg-tab-${t}`);
    if (!btn) return;
    if ((t === 'all' && tabName === '') || t === tabName) {
      btn.className = 'px-4 py-2 text-xs font-bold rounded-lg bg-indigo-600 text-white shadow-sm transition';
    } else {
      btn.className = 'px-4 py-2 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-200 transition';
    }
  });
  loadFinishedStock();
}

async function loadFinishedStock() {
  const search = document.getElementById('finished-stock-search')?.value || '';
  let url = `/api/finished-stock?search=${encodeURIComponent(search)}`;
  if (currentFinishedStockTab) url += `&product_type=${encodeURIComponent(currentFinishedStockTab)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!data.success) return;

    finishedStockCache = data.data;

    let totAvail = 0;
    finishedStockCache.forEach(f => totAvail += f.available_kg);
    document.getElementById('fg-current-tab-total').textContent = `Total Available: ${fmtKg(totAvail)}`;

    const tbody = document.getElementById('finished-stock-table-body');
    if (!finishedStockCache.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400">No finished goods in stock for this category.</td></tr>`;
      return;
    }

    tbody.innerHTML = finishedStockCache.map(f => `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-3 px-4 font-bold text-slate-900 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full ${
            f.product_type === 'Tape' ? 'bg-emerald-500' :
            f.product_type === 'Rope' ? 'bg-teal-500' : 'bg-cyan-500'
          }"></span>
          ${f.product_type}
        </td>
        <td class="py-3 px-4">${f.colour}</td>
        <td class="py-3 px-4 text-center font-mono">${f.batch_count}</td>
        <td class="py-3 px-4 text-right font-mono">${fmtKg(f.produced_kg)}</td>
        <td class="py-3 px-4 text-right font-mono text-violet-700">${fmtKg(f.sold_kg)}</td>
        <td class="py-3 px-4 text-right font-mono font-extrabold text-sm ${f.available_kg <= 0 ? 'text-rose-600' : 'text-emerald-700'}">
          ${fmtKg(f.available_kg)}
        </td>
        <td class="py-3 px-4 text-center">
          <span class="inline-block px-2.5 py-0.5 rounded text-[10px] font-bold ${
            f.status === 'Normal' ? 'badge-healthy' :
            f.status === 'Low Stock' ? 'badge-low' : 'badge-out'
          }">${f.status}</span>
        </td>
        <td class="py-3 px-4 text-center">
          <button onclick="startSaleWithProduct('${f.product_type}', '${f.colour}')"
            class="px-2.5 py-1 bg-emerald-50 hover:bg-emerald-600 hover:text-white text-emerald-700 font-semibold rounded transition text-[11px]">
            Sell Item
          </button>
        </td>
      </tr>
    `).join('');

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error('Error loading finished stock:', e);
  }
}

function startSaleWithProduct(pType, colour) {
  openSaleModal();
  setTimeout(() => {
    document.getElementById('s-product-type').value = pType;
    updateSaleColours(pType);
    document.getElementById('s-product-colour').value = colour;
    updateSaleStockHint();
  }, 100);
}

// --- Sales Management Module ---

async function loadSales() {
  const search = document.getElementById('sales-search')?.value || '';
  const pType = document.getElementById('sales-product-filter')?.value || '';
  const payStatus = document.getElementById('sales-payment-filter')?.value || '';

  let url = `/api/sales?search=${encodeURIComponent(search)}`;
  if (pType) url += `&product_type=${encodeURIComponent(pType)}`;
  if (payStatus) url += `&payment_status=${encodeURIComponent(payStatus)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    const tbody = document.getElementById('sales-table-body');
    if (!data.success || !data.data.length) {
      tbody.innerHTML = `<tr><td colspan="11" class="text-center py-6 text-slate-400">No sales records found.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.data.map(s => `
      <tr class="hover:bg-slate-50 transition ${s.status === 'CANCELLED' ? 'opacity-50 bg-slate-50 line-through' : ''}">
        <td class="py-3 px-4 font-mono">${s.sale_date}</td>
        <td class="py-3 px-4 font-semibold text-slate-800">${s.invoice_number}</td>
        <td class="py-3 px-4 font-medium text-slate-900">${s.customer_name || 'Direct Customer'}</td>
        <td class="py-3 px-4 font-bold text-slate-800">${s.product_type}</td>
        <td class="py-3 px-4">${s.product_colour}</td>
        <td class="py-3 px-4 text-right font-mono font-bold">${fmtKg(s.quantity_kg)}</td>
        <td class="py-3 px-4 text-right font-mono">${fmtCurr(s.price_per_kg)}</td>
        <td class="py-3 px-4 text-right font-mono font-bold text-emerald-700">${fmtCurr(s.total_amount)}</td>
        <td class="py-3 px-4 text-center">
          <button onclick="openPaymentModal(${s.id}, '${s.payment_status}', ${s.total_amount}, ${s.paid_amount})"
            class="px-2 py-0.5 rounded text-[10px] font-bold border transition ${
              s.payment_status === 'Paid' ? 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100' :
              s.payment_status === 'Partial' ? 'bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100' :
              'bg-rose-50 text-rose-800 border-rose-200 hover:bg-rose-100'
            }">
            ${s.payment_status} ✎
          </button>
        </td>
        <td class="py-3 px-4 text-right font-mono ${s.balance_amount > 0 ? 'text-amber-700 font-bold' : 'text-slate-400'}">
          ${fmtCurr(s.balance_amount)}
        </td>
        <td class="py-3 px-4 text-center flex items-center justify-center gap-1.5">
          <button onclick="previewInvoice(${s.id})" title="Print GST Invoice" class="p-1 text-indigo-600 hover:bg-indigo-50 rounded">
            <i data-lucide="printer" class="w-4 h-4"></i>
          </button>
          ${s.status === 'ACTIVE' ? `
            <button onclick="cancelSale(${s.id})" title="Cancel sale (restores finished goods stock)" class="p-1 text-slate-400 hover:text-rose-600 rounded">
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>` : '-'}
        </td>
      </tr>
    `).join('');

    if (window.lucide) lucide.createIcons();
  } catch (e) {
    console.error('Error loading sales:', e);
  }
}

async function openSaleModal() {
  document.getElementById('form-sale').reset();
  document.getElementById('s-date').value = new Date().toISOString().split('T')[0];
  document.getElementById('s-total-preview').textContent = '₹ 0.00';
  document.getElementById('s-balance').value = '0.00';

  // Load finished stock to populate colours
  await loadFinishedStock();
  const pTypeSelect = document.getElementById('s-product-type');
  updateSaleColours(pTypeSelect.value);

  pTypeSelect.onchange = () => {
    updateSaleColours(pTypeSelect.value);
    updateSaleStockHint();
  };

  document.getElementById('modal-sale').classList.remove('hidden');
}

function updateSaleColours(productType) {
  const colourSelect = document.getElementById('s-product-colour');
  const availableColours = finishedStockCache.filter(f => f.product_type === productType).map(f => f.colour);
  colourSelect.innerHTML = '<option value="">Select Colour</option>' +
    availableColours.map(c => `<option value="${c}">${c}</option>`).join('');
}

function updateSaleStockHint() {
  const pType = document.getElementById('s-product-type').value;
  const colour = document.getElementById('s-product-colour').value;
  const hint = document.getElementById('s-avail-hint');

  if (!pType || !colour) {
    hint.textContent = '0.000 KG';
    return;
  }

  const match = finishedStockCache.find(f => f.product_type === pType && f.colour === colour);
  const avail = match ? match.available_kg : 0.0;
  hint.textContent = fmtKg(avail);
  hint.className = avail > 0 ? 'font-bold font-mono text-sm text-emerald-700' : 'font-bold font-mono text-sm text-rose-600';
}

function calcSaleTotal() {
  const qty = parseFloat(document.getElementById('s-qty').value || 0);
  const price = parseFloat(document.getElementById('s-price').value || 0);
  const total = qty * price;
  document.getElementById('s-total-preview').textContent = fmtCurr(total);

  // If status is paid, auto-update paid amount
  const status = document.getElementById('s-payment-status').value;
  if (status === 'Paid') {
    document.getElementById('s-paid').value = total.toFixed(2);
    document.getElementById('s-balance').value = '0.00';
  } else {
    calcSaleBalance();
  }
}

function onSalePaymentStatusChange() {
  const status = document.getElementById('s-payment-status').value;
  const qty = parseFloat(document.getElementById('s-qty').value || 0);
  const price = parseFloat(document.getElementById('s-price').value || 0);
  const total = qty * price;

  if (status === 'Paid') {
    document.getElementById('s-paid').value = total.toFixed(2);
    document.getElementById('s-balance').value = '0.00';
  } else if (status === 'Unpaid') {
    document.getElementById('s-paid').value = '0.00';
    document.getElementById('s-balance').value = total.toFixed(2);
  }
}

function calcSaleBalance() {
  const qty = parseFloat(document.getElementById('s-qty').value || 0);
  const price = parseFloat(document.getElementById('s-price').value || 0);
  const total = qty * price;
  const paid = parseFloat(document.getElementById('s-paid').value || 0);
  const bal = Math.max(0, total - paid);
  document.getElementById('s-balance').value = bal.toFixed(2);
}

async function submitSale(e) {
  e.preventDefault();
  const qty = parseFloat(document.getElementById('s-qty').value || 0);
  const pType = document.getElementById('s-product-type').value;
  const colour = document.getElementById('s-product-colour').value;

  // Client check available stock
  const match = finishedStockCache.find(f => f.product_type === pType && f.colour === colour);
  const avail = match ? match.available_kg : 0.0;
  if (qty > avail) {
    Swal.fire('Insufficient Finished Stock', `Cannot sell ${qty.toFixed(3)} KG. Available stock of ${pType} (${colour}) is only ${avail.toFixed(3)} KG.`, 'error');
    return;
  }

  const payload = {
    sale_date: document.getElementById('s-date').value,
    customer_id: document.getElementById('s-customer').value,
    product_type: pType,
    product_colour: colour,
    quantity_kg: qty,
    price_per_kg: parseFloat(document.getElementById('s-price').value || 0),
    payment_status: document.getElementById('s-payment-status').value,
    paid_amount: parseFloat(document.getElementById('s-paid').value || 0),
    invoice_number: document.getElementById('s-invoice-num').value,
    notes: document.getElementById('s-notes').value
  };

  try {
    const res = await fetch('/api/sales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-sale');
      Swal.fire({
        title: 'Sale Invoice Created!',
        text: `${data.message} Would you like to view the invoice?`,
        icon: 'success',
        showCancelButton: true,
        confirmButtonText: 'View Invoice',
        cancelButtonText: 'Done'
      }).then((r) => {
        if (r.isConfirmed) {
          previewInvoice(data.id);
        }
      });
      loadSales();
      loadDashboard();
    } else {
      Swal.fire('Sale Rejected', data.message, 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Unable to record sale.', 'error');
  }
}

async function cancelSale(id) {
  const result = await Swal.fire({
    title: 'Cancel Sale?',
    text: 'This will atomically restore the sold weight back into finished goods stock.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#ef4444',
    confirmButtonText: 'Yes, Cancel Sale'
  });

  if (result.isConfirmed) {
    try {
      const res = await fetch(`/api/sales/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Cancelled', data.message, 'success');
        loadSales();
        loadDashboard();
      } else {
        Swal.fire('Error', data.message, 'error');
      }
    } catch (e) {
      Swal.fire('Error', 'Failed to cancel sale.', 'error');
    }
  }
}

async function openPaymentModal(saleId, currentStatus, total, paid) {
  const { value: formValues } = await Swal.fire({
    title: 'Update Payment Status',
    html: `
      <div class="text-left text-xs space-y-3">
        <div>
          <label class="block font-medium text-slate-700 mb-1">Status</label>
          <select id="swal-pay-status" class="w-full p-2 border rounded">
            <option value="Paid" ${currentStatus === 'Paid' ? 'selected' : ''}>Paid</option>
            <option value="Partial" ${currentStatus === 'Partial' ? 'selected' : ''}>Partial</option>
            <option value="Unpaid" ${currentStatus === 'Unpaid' ? 'selected' : ''}>Unpaid</option>
          </select>
        </div>
        <div>
          <label class="block font-medium text-slate-700 mb-1">Amount Paid (₹) (Total: ${fmtCurr(total)})</label>
          <input type="number" step="0.01" id="swal-pay-amt" value="${paid}" class="w-full p-2 border rounded font-mono">
        </div>
      </div>
    `,
    focusConfirm: false,
    showCancelButton: true,
    confirmButtonText: 'Save Payment',
    preConfirm: () => {
      return {
        payment_status: document.getElementById('swal-pay-status').value,
        paid_amount: document.getElementById('swal-pay-amt').value
      };
    }
  });

  if (formValues) {
    try {
      const res = await fetch(`/api/sales/${saleId}/payment`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formValues)
      });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Updated', data.message, 'success');
        loadSales();
        loadDashboard();
      }
    } catch (e) {
      Swal.fire('Error', 'Failed to update payment.', 'error');
    }
  }
}

// --- Invoice Preview & Print ---

async function previewInvoice(saleId) {
  try {
    const res = await fetch(`/api/sales/${saleId}/invoice`);
    const data = await res.json();
    if (!data.success) return;

    const s = data.invoice;
    const c = data.company;

    const container = document.getElementById('printable-invoice');
    container.innerHTML = `
      <div class="border border-slate-300 p-8 rounded-lg">
        <!-- Header -->
        <div class="flex items-start justify-between border-b pb-6 mb-6">
          <div>
            <h1 class="text-xl font-bold tracking-tight text-slate-900">${c.company_name || 'Sri Krishna Textile Mills & Twisting Works'}</h1>
            <p class="text-xs text-slate-600 mt-1 max-w-sm">${c.company_address || 'Textile Industrial Complex, Tirupur, Tamil Nadu - 641604'}</p>
            <p class="text-xs text-slate-600 mt-0.5">Phone: ${c.company_phone || '+91 98420 12345'}</p>
            <p class="text-xs font-mono font-bold text-slate-800 mt-1">GSTIN: ${c.company_gstin || '33AABCT9988Q1ZA'}</p>
          </div>
          <div class="text-right">
            <span class="inline-block px-3 py-1 bg-slate-900 text-white text-xs font-bold uppercase tracking-wider rounded">TAX INVOICE</span>
            <p class="text-sm font-bold font-mono text-slate-900 mt-2">${s.invoice_number}</p>
            <p class="text-xs text-slate-500">Date: ${s.sale_date}</p>
          </div>
        </div>

        <!-- Bill To -->
        <div class="grid grid-cols-2 gap-6 mb-6 text-xs">
          <div class="p-4 bg-slate-50 rounded border border-slate-200">
            <h3 class="font-bold text-slate-700 uppercase tracking-wider text-[10px] mb-2">BILLED TO:</h3>
            <p class="font-bold text-sm text-slate-900">${s.customer_name}</p>
            <p class="text-slate-600 mt-0.5">${s.customer_address || 'Tirupur, Tamil Nadu'}</p>
            <p class="text-slate-600">Contact: ${s.contact_person || '-'} • ${s.customer_phone || '-'}</p>
            <p class="font-mono text-slate-800 font-semibold mt-1">GSTIN: ${s.customer_gstin || 'Unregistered'}</p>
          </div>
          <div class="p-4 bg-slate-50 rounded border border-slate-200">
            <h3 class="font-bold text-slate-700 uppercase tracking-wider text-[10px] mb-2">DISPATCH & PAYMENT:</h3>
            <p><b>Product:</b> ${s.product_type} (${s.product_colour})</p>
            <p class="mt-0.5"><b>Payment Status:</b> <span class="font-bold">${s.payment_status}</span></p>
            <p class="mt-0.5"><b>Paid Amount:</b> ${fmtCurr(s.paid_amount)}</p>
            <p class="mt-0.5"><b>Balance Due:</b> <span class="font-bold text-rose-600">${fmtCurr(s.balance_amount)}</span></p>
          </div>
        </div>

        <!-- Line Items Table -->
        <table class="w-full text-left text-xs border border-slate-300 mb-6">
          <thead>
            <tr class="bg-slate-100 border-b border-slate-300 text-slate-700 font-bold uppercase text-[10px]">
              <th class="py-2.5 px-3">#</th>
              <th class="py-2.5 px-3">Description of Goods</th>
              <th class="py-2.5 px-3">Colour</th>
              <th class="py-2.5 px-3 text-right">Quantity (KG)</th>
              <th class="py-2.5 px-3 text-right">Rate / KG (₹)</th>
              <th class="py-2.5 px-3 text-right">Amount (₹)</th>
            </tr>
          </thead>
          <tbody>
            <tr class="border-b border-slate-200">
              <td class="py-3 px-3">1</td>
              <td class="py-3 px-3 font-bold text-slate-900">${s.product_type} (Textile Narrow Fabric / Twisted Cord)</td>
              <td class="py-3 px-3">${s.product_colour}</td>
              <td class="py-3 px-3 text-right font-mono font-bold">${fmtKg(s.quantity_kg)}</td>
              <td class="py-3 px-3 text-right font-mono">${fmtCurr(s.price_per_kg)}</td>
              <td class="py-3 px-3 text-right font-mono font-bold">${fmtCurr(s.total_amount)}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="bg-slate-50 font-bold">
              <td colspan="3" class="py-2.5 px-3 text-right">TOTAL INVOICE VALUE:</td>
              <td class="py-2.5 px-3 text-right font-mono font-extrabold">${fmtKg(s.quantity_kg)}</td>
              <td class="py-2.5 px-3"></td>
              <td class="py-2.5 px-3 text-right font-mono font-extrabold text-sm text-indigo-900">${fmtCurr(s.total_amount)}</td>
            </tr>
          </tfoot>
        </table>

        <!-- Footer & Bank details -->
        <div class="grid grid-cols-2 gap-6 text-xs pt-4 border-t border-slate-200">
          <div>
            <h4 class="font-bold text-slate-700 uppercase tracking-wide text-[10px]">Bank Transfer Details:</h4>
            <p class="text-slate-600 mt-1">${c.company_bank_details || 'HDFC Bank, Tirupur Main Branch | A/C: 50200012345678 | IFSC: HDFC0001234'}</p>
            <p class="text-slate-500 mt-2 text-[11px]">Note: Weights verified via digital scale. Goods once sold will not be taken back without authorization.</p>
          </div>
          <div class="text-right flex flex-col justify-between">
            <p class="text-xs font-bold text-slate-800">For ${c.company_name || 'Sri Krishna Textile Mills'}</p>
            <div class="pt-12">
              <p class="border-t border-slate-400 inline-block px-8 font-semibold text-slate-700">Authorized Signatory</p>
            </div>
          </div>
        </div>
      </div>
    `;

    document.getElementById('modal-invoice').classList.remove('hidden');
  } catch (e) {
    console.error('Error fetching invoice:', e);
  }
}

// --- Customers & Suppliers ---

async function loadCustomers() {
  await loadCustomersList();
  const tbody = document.getElementById('customers-table-body');
  if (!customersList.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-slate-400">No customers registered yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = customersList.map(c => `
    <tr class="hover:bg-slate-50 transition">
      <td class="py-3 px-4 font-bold text-slate-900">${c.name}</td>
      <td class="py-3 px-4">${c.contact_person || '-'}</td>
      <td class="py-3 px-4">${c.phone || ''} ${c.email ? '• ' + c.email : ''}</td>
      <td class="py-3 px-4 font-mono">${c.gstin || '-'}</td>
      <td class="py-3 px-4 text-right font-mono font-bold">${fmtKg(c.total_bought_kg)}</td>
      <td class="py-3 px-4 text-right font-mono font-bold text-emerald-700">${fmtCurr(c.total_sales_val)}</td>
      <td class="py-3 px-4 text-right font-mono ${c.outstanding_balance > 0 ? 'text-amber-700 font-bold' : 'text-slate-400'}">
        ${fmtCurr(c.outstanding_balance)}
      </td>
      <td class="py-3 px-4 text-center">
        <button onclick="startSaleForCustomer(${c.id})" class="px-2 py-1 bg-indigo-50 text-indigo-700 font-semibold rounded text-[11px] hover:bg-indigo-600 hover:text-white transition">
          + New Sale
        </button>
      </td>
    </tr>
  `).join('');
}

function startSaleForCustomer(cid) {
  openSaleModal();
  setTimeout(() => {
    document.getElementById('s-customer').value = cid;
  }, 100);
}

function openCustomerModal() {
  document.getElementById('form-customer').reset();
  document.getElementById('modal-customer').classList.remove('hidden');
}

async function submitCustomer(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById('cust-name').value,
    contact_person: document.getElementById('cust-contact').value,
    phone: document.getElementById('cust-phone').value,
    email: document.getElementById('cust-email').value,
    gstin: document.getElementById('cust-gstin').value,
    address: document.getElementById('cust-address').value
  };

  try {
    const res = await fetch('/api/customers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-customer');
      Swal.fire('Saved', data.message, 'success');
      loadCustomers();
    } else {
      Swal.fire('Error', data.message, 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Failed to save customer.', 'error');
  }
}

async function loadSuppliers() {
  await loadSuppliersList();
  const tbody = document.getElementById('suppliers-table-body');
  if (!suppliersList.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-slate-400">No suppliers registered yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = suppliersList.map(s => `
    <tr class="hover:bg-slate-50 transition">
      <td class="py-3 px-4 font-bold text-slate-900">${s.name}</td>
      <td class="py-3 px-4">${s.contact_person || '-'}</td>
      <td class="py-3 px-4">${s.phone || ''} ${s.email ? '• ' + s.email : ''}</td>
      <td class="py-3 px-4 font-mono">${s.gstin || '-'}</td>
      <td class="py-3 px-4 text-right font-mono font-bold">${fmtKg(s.total_supplied_kg)}</td>
      <td class="py-3 px-4 text-right font-mono font-bold text-blue-700">${fmtCurr(s.total_purchase_val)}</td>
      <td class="py-3 px-4 text-center">
        <button onclick="startPurchaseForSupplier(${s.id})" class="px-2 py-1 bg-blue-50 text-blue-700 font-semibold rounded text-[11px] hover:bg-blue-600 hover:text-white transition">
          + Purchase
        </button>
      </td>
    </tr>
  `).join('');
}

function startPurchaseForSupplier(sid) {
  openPurchaseModal();
  setTimeout(() => {
    document.getElementById('p-supplier').value = sid;
  }, 100);
}

function openSupplierModal() {
  document.getElementById('form-supplier').reset();
  document.getElementById('modal-supplier').classList.remove('hidden');
}

async function submitSupplier(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById('supp-name').value,
    contact_person: document.getElementById('supp-contact').value,
    phone: document.getElementById('supp-phone').value,
    email: document.getElementById('supp-email').value,
    gstin: document.getElementById('supp-gstin').value,
    address: document.getElementById('supp-address').value
  };

  try {
    const res = await fetch('/api/suppliers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-supplier');
      Swal.fire('Saved', data.message, 'success');
      loadSuppliers();
    } else {
      Swal.fire('Error', data.message, 'error');
    }
  } catch (err) {
    Swal.fire('Error', 'Failed to save supplier.', 'error');
  }
}

// --- Settings & Users Module ---

async function loadSettings() {
  await loadMasters();
  populateSettingsForm();
  loadUsers();
  loadActivityLogs();
}

function populateSettingsForm() {
  const s = mastersData.settings || {};
  if (document.getElementById('set-company-name')) {
    document.getElementById('set-company-name').value = s.company_name || '';
    document.getElementById('set-company-address').value = s.company_address || '';
    document.getElementById('set-company-gstin').value = s.company_gstin || '';
    document.getElementById('set-company-phone').value = s.company_phone || '';
    document.getElementById('set-company-bank').value = s.company_bank_details || '';
  }
}

async function saveSettings(e) {
  e.preventDefault();
  const payload = {
    company_name: document.getElementById('set-company-name').value,
    company_address: document.getElementById('set-company-address').value,
    company_gstin: document.getElementById('set-company-gstin').value,
    company_phone: document.getElementById('set-company-phone').value,
    company_bank_details: document.getElementById('set-company-bank').value
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      Swal.fire('Saved', 'Company settings updated successfully.', 'success');
      loadMasters();
    }
  } catch (e) {
    Swal.fire('Error', 'Failed to update settings.', 'error');
  }
}

async function loadUsers() {
  try {
    const res = await fetch('/api/users');
    const data = await res.json();
    const tbody = document.getElementById('users-table-body');
    if (!tbody) return;

    if (!data.success || !data.data.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-slate-400">Admin privileges required to view users.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.data.map(u => `
      <tr class="hover:bg-slate-50">
        <td class="py-2.5 px-4 font-semibold text-slate-900">${u.full_name}</td>
        <td class="py-2.5 px-4 font-mono">${u.username}</td>
        <td class="py-2.5 px-4"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 uppercase">${u.role}</span></td>
        <td class="py-2.5 px-4 text-center"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${u.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200'}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
        <td class="py-2.5 px-4 text-slate-400">${u.created_at || '-'}</td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Error loading users:', e);
  }
}

function openUserModal() {
  document.getElementById('form-user').reset();
  document.getElementById('modal-user').classList.remove('hidden');
}

async function submitUser(e) {
  e.preventDefault();
  const payload = {
    full_name: document.getElementById('u-fullname').value,
    username: document.getElementById('u-username').value,
    password: document.getElementById('u-password').value,
    role: document.getElementById('u-role').value
  };

  try {
    const res = await fetch('/api/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('modal-user');
      Swal.fire('Created', data.message, 'success');
      loadUsers();
    } else {
      Swal.fire('Error', data.message, 'error');
    }
  } catch (e) {
    Swal.fire('Error', 'Failed to create user.', 'error');
  }
}

async function loadActivityLogs() {
  try {
    const res = await fetch('/api/activity-logs');
    const data = await res.json();
    const container = document.getElementById('activity-log-container');
    if (!container || !data.success) return;

    container.innerHTML = data.data.map(l => `
      <div class="p-2 rounded bg-slate-100 border border-slate-200 flex items-center justify-between">
        <div>
          <span class="font-bold text-slate-800">[${l.action}]</span>
          <span class="text-slate-600">${l.details}</span>
        </div>
        <div class="text-right text-[10px] text-slate-400">
          <b>${l.username || 'System'}</b> • ${l.created_at}
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Error loading activity logs:', e);
  }
}

async function triggerResetDemo() {
  const result = await Swal.fire({
    title: 'Seed Sample Data?',
    text: 'This will reset the database and seed realistic textile spinning, production batches & sales records.',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#f59e0b',
    confirmButtonText: 'Yes, Seed Demo Data'
  });

  if (result.isConfirmed) {
    try {
      const res = await fetch('/api/system/reset-demo', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Success', data.message, 'success');
        await loadInitialData();
        navigateView('dashboard');
      } else {
        Swal.fire('Error', data.message, 'error');
      }
    } catch (e) {
      Swal.fire('Error', 'Failed to reset demo data.', 'error');
    }
  }
}

async function triggerClearAllData() {
  const result = await Swal.fire({
    title: 'CLEAR ALL DATA?',
    text: 'WARNING: This will delete ALL yarn purchases, production batches, finished goods stocks, sales invoices, and ledger records. All stock balances will be reset to 0.000 KG. This cannot be undone!',
    icon: 'warning',
    showCancelButton: true,
    confirmButtonColor: '#e11d48',
    cancelButtonColor: '#64748b',
    confirmButtonText: 'Yes, Clear All Data'
  });

  if (result.isConfirmed) {
    try {
      const res = await fetch('/api/system/clear-all-data', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        await Swal.fire('Cleared!', data.message, 'success');
        await loadInitialData();
        navigateView('dashboard');
      } else {
        Swal.fire('Action Denied', data.message, 'error');
      }
    } catch (e) {
      Swal.fire('Error', 'Failed to clear data.', 'error');
    }
  }
}

// --- Downloads (Excel & PDF) ---

function downloadReport(format, reportType) {
  let url = `/api/reports/export/${format}?type=${reportType}`;
  if (reportType === 'finished_stock' && currentFinishedStockTab) {
    url += `&product_type=${encodeURIComponent(currentFinishedStockTab)}`;
  }
  window.open(url, '_blank');
}

// Modal helper
function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}
