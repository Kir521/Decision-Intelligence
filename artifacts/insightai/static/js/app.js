/* InsightAI — Main JS */
'use strict';

// ── Sidebar toggle ──────────────────────────────────────────────────────────
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  if (sb) sb.classList.toggle('open');
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
  const sb = document.getElementById('sidebar');
  const toggle = document.querySelector('.topbar-toggle');
  if (sb && sb.classList.contains('open') && !sb.contains(e.target) && e.target !== toggle && !toggle.contains(e.target)) {
    sb.classList.remove('open');
  }
});

// ── Alert auto-dismiss ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(alert => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Animate numbers on dashboard
  animateCounters();
  
  // Initialize tooltips
  const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach(el => new bootstrap.Tooltip(el));
});

// ── Counter animation ───────────────────────────────────────────────────────
function animateCounters() {
  const counters = document.querySelectorAll('.kpi-value');
  counters.forEach(counter => {
    const rawText = counter.textContent.trim();
    const numMatch = rawText.match(/[\d.]+/);
    if (!numMatch) return;
    const target = parseFloat(numMatch[0]);
    if (!target || isNaN(target)) return;
    const suffix = rawText.replace(numMatch[0], '');
    const isFloat = rawText.includes('.');
    let current = 0;
    const duration = 1200;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      counter.textContent = isFloat ? current.toFixed(1) + suffix : Math.floor(current) + suffix;
      if (current >= target) clearInterval(timer);
    }, 16);
  });
}

// ── Score bar animation ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const bars = document.querySelectorAll('.score-bar');
  bars.forEach(bar => {
    const targetWidth = bar.style.width;
    bar.style.width = '0%';
    requestAnimationFrame(() => {
      setTimeout(() => { bar.style.width = targetWidth; }, 100);
    });
  });
});

// ── Landing page scroll effects ─────────────────────────────────────────────
const observerOptions = { threshold: 0.12, rootMargin: '0px 0px -40px 0px' };
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, observerOptions);

document.addEventListener('DOMContentLoaded', () => {
  const animatable = document.querySelectorAll('.feature-card, .step-card, .output-item, .kpi-card');
  animatable.forEach((el, i) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(24px)';
    el.style.transition = `opacity .5s ease ${i * 0.06}s, transform .5s ease ${i * 0.06}s`;
    observer.observe(el);
  });
});
