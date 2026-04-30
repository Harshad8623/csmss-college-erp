// ═══════════════════════════════════════════════════════════════
// CSMSS College ERP — Main JavaScript
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {

  // ── CSRF: auto-inject token into all POST forms ───────────────
  const csrfMeta  = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
  if (csrfToken) {
    // Inject hidden field into every existing POST form that doesn't already have one
    document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(form => {
      if (!form.querySelector('input[name="csrf_token"]')) {
        const input = document.createElement('input');
        input.type  = 'hidden';
        input.name  = 'csrf_token';
        input.value = csrfToken;
        form.appendChild(input);
      }
    });

    // Patch fetch() globally to add X-CSRFToken header on all POST requests
    const _origFetch = window.fetch;
    window.fetch = function(url, opts = {}) {
      if (opts.method && opts.method.toUpperCase() === 'POST') {
        opts.headers = opts.headers || {};
        opts.headers['X-CSRFToken'] = csrfToken;
      }
      return _origFetch(url, opts);
    };
  }

  // ── Sidebar Toggle ────────────────────────────────────────────
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.getElementById('mainContent');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  let sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
  const isMobile = () => window.innerWidth <= 991;

  function applySidebarState() {
    if (!sidebar) return;
    if (isMobile()) {
      sidebar.classList.remove('collapsed');
      if (mainContent) mainContent.classList.remove('sidebar-collapsed');
      return;
    }
    if (sidebarCollapsed) {
      sidebar.classList.add('collapsed');
      if (mainContent) mainContent.classList.add('sidebar-collapsed');
    } else {
      sidebar.classList.remove('collapsed');
      if (mainContent) mainContent.classList.remove('sidebar-collapsed');
    }
  }

  applySidebarState();

  function openMobileSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('mobile-open');
    if (sidebarOverlay) {
      sidebarOverlay.style.opacity = '1';
      sidebarOverlay.style.pointerEvents = 'all';
    }
  }

  function closeMobileSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('mobile-open');
    if (sidebarOverlay) {
      sidebarOverlay.style.opacity = '0';
      sidebarOverlay.style.pointerEvents = 'none';
    }
  }

  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function () {
      if (isMobile()) {
        sidebar.classList.contains('mobile-open') ? closeMobileSidebar() : openMobileSidebar();
      } else {
        sidebarCollapsed = !sidebarCollapsed;
        localStorage.setItem('sidebarCollapsed', sidebarCollapsed);
        applySidebarState();
      }
    });
  }

  // Mobile bottom nav sidebar button
  const mobNavSidebarBtn = document.getElementById('mobNavSidebarBtn');
  if (mobNavSidebarBtn) {
    mobNavSidebarBtn.addEventListener('click', function () {
      sidebar.classList.contains('mobile-open') ? closeMobileSidebar() : openMobileSidebar();
    });
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeMobileSidebar);
  }

  window.addEventListener('resize', applySidebarState);

  // ── Swipe to close sidebar on mobile ──────────────────────────────────────
  let touchStartX = 0;
  let touchEndX = 0;
  document.addEventListener('touchstart', function(e) {
    touchStartX = e.changedTouches[0].screenX;
  }, { passive: true });
  document.addEventListener('touchend', function(e) {
    touchEndX = e.changedTouches[0].screenX;
    if (isMobile() && sidebar && sidebar.classList.contains('mobile-open')) {
      // Swipe left to close (drag at least 80px left)
      if (touchStartX - touchEndX > 80) {
        closeMobileSidebar();
      }
    }
    // Swipe right from edge (within 30px of left) to open
    if (isMobile() && sidebar && !sidebar.classList.contains('mobile-open')) {
      if (touchStartX < 30 && touchEndX - touchStartX > 80) {
        openMobileSidebar();
      }
    }
  }, { passive: true });

  // ── Active Nav Item (sidebar + bottom nav) ─────────────────────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('href');
    if (href && (currentPath === href || (currentPath.startsWith(href) && href !== '/'))) {
      item.classList.add('active');
    }
  });
  document.querySelectorAll('.mob-nav-item[href]').forEach(item => {
    const href = item.getAttribute('href');
    if (href && (currentPath === href || (currentPath.startsWith(href) && href !== '/'))) {
      item.classList.add('active');
    }
  });


  // ── Dropdown Menus ─────────────────────────────────────────────
  document.querySelectorAll('[data-dropdown]').forEach(trigger => {
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      const parent = this.closest('.dropdown-erp');
      const isOpen = parent.classList.contains('open');
      document.querySelectorAll('.dropdown-erp.open').forEach(d => d.classList.remove('open'));
      if (!isOpen) parent.classList.add('open');
    });
  });
  document.addEventListener('click', () => {
    document.querySelectorAll('.dropdown-erp.open').forEach(d => d.classList.remove('open'));
  });

  // ── Alert Auto-dismiss ─────────────────────────────────────────
  document.querySelectorAll('.alert-erp').forEach(alert => {
    const closeBtn = alert.querySelector('.alert-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        alert.style.animation = 'slideDown 0.3s ease reverse';
        setTimeout(() => alert.remove(), 300);
      });
    }
    // Auto dismiss after 5s
    setTimeout(() => {
      if (alert.parentNode) {
        alert.style.opacity = '0';
        alert.style.transition = 'opacity 0.5s';
        setTimeout(() => alert.remove(), 500);
      }
    }, 5000);
  });

  // ── Demo Login Buttons ─────────────────────────────────────────
  document.querySelectorAll('.demo-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const email = this.dataset.email;
      const pass  = this.dataset.pass;
      const emailInput = document.getElementById('email');
      const passInput  = document.getElementById('password');
      if (emailInput) emailInput.value = email;
      if (passInput)  passInput.value  = pass;
      // Animate
      this.style.background = 'rgba(59,130,246,0.2)';
      setTimeout(() => this.style.background = '', 300);
    });
  });

  // ── Attendance Toggle Buttons ──────────────────────────────────
  document.querySelectorAll('.att-toggle-wrap').forEach(wrap => {
    const presentBtn = wrap.querySelector('.att-present');
    const absentBtn  = wrap.querySelector('.att-absent');
    const hiddenInput = wrap.querySelector('input[type="hidden"]');

    function setPresent(present) {
      if (present) {
        presentBtn?.classList.add('present');
        absentBtn?.classList.remove('absent');
        if (hiddenInput) hiddenInput.disabled = false;
      } else {
        presentBtn?.classList.remove('present');
        absentBtn?.classList.add('absent');
        if (hiddenInput) hiddenInput.disabled = true;
      }
    }

    // Init from existing state
    const isPresent = wrap.dataset.present === 'true';
    setPresent(isPresent);

    presentBtn?.addEventListener('click', () => setPresent(true));
    absentBtn?.addEventListener('click', () => setPresent(false));
  });

  // ── Bulk Attendance ────────────────────────────────────────────
  const markAllPresentBtn = document.getElementById('markAllPresent');
  const markAllAbsentBtn  = document.getElementById('markAllAbsent');

  markAllPresentBtn?.addEventListener('click', () => {
    document.querySelectorAll('.att-toggle-wrap').forEach(wrap => {
      wrap.dataset.present = 'true';
      wrap.querySelector('.att-present')?.click();
    });
  });

  markAllAbsentBtn?.addEventListener('click', () => {
    document.querySelectorAll('.att-toggle-wrap').forEach(wrap => {
      wrap.dataset.present = 'false';
      wrap.querySelector('.att-absent')?.click();
    });
  });

  // ── Notification Polling ───────────────────────────────────────
  const notifBadge = document.getElementById('notifBadge');
  if (notifBadge) {
    function refreshNotifCount() {
      fetch('/notifications/api/unread')
        .then(r => r.json())
        .then(data => {
          if (data.count > 0) {
            notifBadge.textContent = data.count;
            notifBadge.style.display = 'flex';
          } else {
            notifBadge.style.display = 'none';
          }
        })
        .catch(() => {});
    }
    refreshNotifCount();
    setInterval(refreshNotifCount, 30000); // Every 30s
  }

  // ── Confirm Dialogs ────────────────────────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', function (e) {
      if (!confirm(this.dataset.confirm)) {
        e.preventDefault();
        e.stopPropagation();
      }
    });
  });

  // ── Form Validation ────────────────────────────────────────────
  document.querySelectorAll('form[data-validate]').forEach(form => {
    form.addEventListener('submit', function (e) {
      const required = this.querySelectorAll('[required]');
      let valid = true;
      required.forEach(field => {
        if (!field.value.trim()) {
          field.style.borderColor = 'var(--accent-red)';
          valid = false;
        } else {
          field.style.borderColor = '';
        }
      });
      if (!valid) {
        e.preventDefault();
        showToast('Please fill all required fields.', 'danger');
      }
    });
  });

  // ── Toast Helper ──────────────────────────────────────────────
  window.showToast = function (msg, type = 'info') {
    const container = document.getElementById('toast-container') || (() => {
      const el = document.createElement('div');
      el.id = 'toast-container';
      el.style.cssText = 'position:fixed;top:80px;right:20px;z-index:2000;display:flex;flex-direction:column;gap:8px;';
      document.body.appendChild(el);
      return el;
    })();

    const toast = document.createElement('div');
    toast.className = `alert-erp alert-${type} fade-in`;
    toast.style.cssText = 'min-width:280px;max-width:400px;';
    toast.innerHTML = `<span>${msg}</span><button class="alert-close">×</button>`;
    container.appendChild(toast);

    toast.querySelector('.alert-close').addEventListener('click', () => toast.remove());
    setTimeout(() => toast.remove(), 4000);
  };

  // ── Animate stat cards on page load ───────────────────────────
  document.querySelectorAll('.stat-card').forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    setTimeout(() => {
      card.style.transition = 'all 0.4s ease';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, i * 80);
  });

  // ── Number Counter Animation ───────────────────────────────────
  document.querySelectorAll('.count-up').forEach(el => {
    const target = parseInt(el.dataset.target || el.textContent, 10);
    if (isNaN(target)) return;
    let current = 0;
    const increment = target / 40;
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) { current = target; clearInterval(timer); }
      el.textContent = Math.floor(current);
    }, 25);
  });

  // ── Charts Helper ──────────────────────────────────────────────
  window.ERP = {
    chartDefaults: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#8b949e', font: { family: 'Inter', size: 12 } }
        }
      },
      scales: {
        x: {
          ticks: { color: '#8b949e', font: { family: 'Inter', size: 11 } },
          grid: { color: 'rgba(48,60,90,0.4)' }
        },
        y: {
          ticks: { color: '#8b949e', font: { family: 'Inter', size: 11 } },
          grid: { color: 'rgba(48,60,90,0.4)' }
        }
      }
    },

    donutDefaults: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#8b949e', font: { family: 'Inter', size: 12 } } }
      }
    },

    blueGradient(ctx) {
      const g = ctx.createLinearGradient(0, 0, 0, 300);
      g.addColorStop(0, 'rgba(59,130,246,0.4)');
      g.addColorStop(1, 'rgba(59,130,246,0)');
      return g;
    }
  };

  // ── Global Form Submit Loading Spinner ─────────────────────────
  // Shows a spinner on any submit button immediately on click so
  // users know the form was received (prevents double-clicks too).
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', function (e) {
      // Don't block forms with data-no-loading attribute
      if (form.dataset.noLoading !== undefined) return;

      const btn = e.submitter || form.querySelector('[type="submit"]');
      if (!btn || btn.disabled) return;

      // If the button has a name, append a hidden input to preserve its value
      // because disabling the button prevents its value from being sent.
      if (btn.name) {
        const hidden = document.createElement('input');
        hidden.type = 'hidden';
        hidden.name = btn.name;
        hidden.value = btn.value;
        form.appendChild(hidden);
      }

      // Store original content and disable immediately
      const originalHTML = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `<span class="btn-spinner"></span> ${btn.dataset.loadingText || 'Please wait…'}`;

      // Safety net: re-enable after 15s in case of network error
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
      }, 15000);
    });
  });

  // ── Double-click guard for anchor buttons ───────────────────────
  document.querySelectorAll('a.btn-erp[href]:not([href="#"])').forEach(link => {
    link.addEventListener('click', function () {
      if (this.dataset.clicked) return;
      this.dataset.clicked = 'true';
      setTimeout(() => delete this.dataset.clicked, 3000);
    });
  });

});
