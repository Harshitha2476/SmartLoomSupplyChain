// Smart Loom — minimal JS
document.addEventListener('DOMContentLoaded', function () {

  // Mark active nav link based on current Flask route
  const path = window.location.pathname;

  document.querySelectorAll('.sl-nav-link').forEach(link => {
    const href = link.getAttribute('href');

    if (href === path) {
      link.classList.add('active');
    }

    // Special case for homepage
    if (path === '/' && href === '/') {
      link.classList.add('active');
    }
  });

  // Login/Register tab toggle
  document.querySelectorAll('[data-sl-tab]').forEach(btn => {
    btn.addEventListener('click', function () {

      const target = this.getAttribute('data-sl-tab');

      document.querySelectorAll('[data-sl-tab]').forEach(b => {
        b.classList.remove('active');
      });

      this.classList.add('active');

      document.querySelectorAll('[data-sl-tab-panel]').forEach(panel => {

        if (panel.getAttribute('data-sl-tab-panel') === target) {
          panel.style.display = 'block';
        } else {
          panel.style.display = 'none';
        }

      });
    });
  });

  // Role selector
  document.querySelectorAll('[data-sl-role-group]').forEach(group => {

    group.querySelectorAll('.sl-role-btn').forEach(btn => {

      btn.addEventListener('click', function () {

        group.querySelectorAll('.sl-role-btn').forEach(b => {
          b.classList.remove('active');
        });

        this.classList.add('active');

        const hidden = group.querySelector('input[type="hidden"]');

        if (hidden) {
          hidden.value = this.dataset.role;
        }

      });

    });

  });

  // Simple table search
  document.querySelectorAll('[data-sl-search]').forEach(input => {

    input.addEventListener('input', function () {

      const target = document.querySelector(this.dataset.slSearch);

      if (!target) return;

      const q = this.value.toLowerCase();

      target.querySelectorAll('tbody tr').forEach(row => {

        if (row.innerText.toLowerCase().includes(q)) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }

      });

    });

  });

});