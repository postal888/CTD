/* ===== CrackTheDeck — App JS ===== */

/* --- Dark Mode Toggle --- */
(function () {
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  let theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  root.setAttribute('data-theme', theme);
  updateToggleIcon();

  if (toggle) {
    toggle.addEventListener('click', () => {
      theme = theme === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', theme);
      toggle.setAttribute('aria-label', 'Switch to ' + (theme === 'dark' ? 'light' : 'dark') + ' mode');
      updateToggleIcon();
    });
  }

  function updateToggleIcon() {
    if (!toggle) return;
    toggle.innerHTML = theme === 'dark'
      ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
})();

/* --- Header Scroll State --- */
(function () {
  const header = document.getElementById('header');
  let lastScroll = 0;
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    header.classList.toggle('header--scrolled', y > 20);
    lastScroll = y;
  }, { passive: true });
})();

/* --- Mobile Menu --- */
function toggleMobileMenu() {
  document.getElementById('mobileMenu').classList.toggle('open');
}
function closeMobileMenu() {
  document.getElementById('mobileMenu').classList.remove('open');
}

/* --- Upload Modal (3 steps) --- */
// Dev: front on :5500 → backend :8000. Production: same origin, nginx proxies /api to backend.
// When front is on :5500 → API on :8000. When front is on :8000 (served by backend) → same origin.
const API_BASE = (window.location.hostname === 'localhost' && window.location.port === '5500') ? 'http://localhost:8000' : '';
let selectedFile = null;
let selectedPlan = null;

function setProgress(step) {
  var fill = document.getElementById('modalProgressFill');
  var progress = document.querySelector('.modal__progress');
  if (fill) fill.style.width = (step / 3 * 100) + '%';
  if (progress) progress.setAttribute('aria-valuenow', step);
}

function goToStep(step) {
  hideUploadError();
  if (step === 2) {
    if (!selectedFile) {
      showUploadError('Please select a PDF or PPTX file first.');
      return;
    }
    var email = document.getElementById('modalEmail');
    if (!email || !email.value || !email.value.includes('@')) {
      showUploadError('Please enter your email.');
      if (email) email.focus();
      return;
    }
    if (!selectedPlan) {
      selectedPlan = 'pro';
      document.querySelectorAll('.modal-plan-card').forEach(function (card) {
        card.classList.toggle('selected', card.getAttribute('data-plan') === 'pro');
      });
    }
  }
  var s1 = document.getElementById('modalStep1');
  var s2 = document.getElementById('modalStep2');
  var s3 = document.getElementById('modalStep3');
  if (s1) s1.hidden = step !== 1;
  if (s2) s2.hidden = step !== 2;
  if (s3) s3.hidden = step !== 3;
  setProgress(step);
  if (step === 3) {
    var planEl = document.getElementById('donePlan');
    var emailEl = document.getElementById('doneEmail');
    if (planEl) planEl.textContent = selectedPlan === 'expert' ? 'Expert' : selectedPlan === 'pro' ? 'Pro' : 'Free';
    if (emailEl) emailEl.textContent = (document.getElementById('modalEmail') || {}).value || '—';
  }
}

function selectPlan(planId) {
  selectedPlan = planId;
  document.querySelectorAll('.modal-plan-card').forEach(function (card) {
    card.classList.toggle('selected', card.getAttribute('data-plan') === planId);
  });
  goToStep(3);
}

/** Full reset: step 1, no plan, clear fields */
function resetUploadModal() {
  var su = document.getElementById('modalSuccess');
  var link = document.getElementById('successDownload');
  var msg = document.getElementById('successMessage');
  var err = document.getElementById('modalError');
  var email = document.getElementById('modalEmail');
  var company = document.getElementById('modalCompany');
  var fileInput = document.getElementById('fileInput');

  if (su) su.hidden = true;
  if (link) { link.setAttribute('href', '#'); link.style.display = 'inline-block'; }
  if (msg) msg.textContent = 'Your report is ready.';
  if (err) { err.textContent = ''; err.hidden = true; }
  if (email) email.value = '';
  if (company) company.value = '';
  if (fileInput) fileInput.value = '';

  selectedFile = null;
  selectedPlan = null;
  var dz = document.getElementById('dropzone');
  if (dz) {
    var nameEl = dz.querySelector('.dropzone__filename');
    if (nameEl) nameEl.remove();
  }
  document.querySelectorAll('.modal-plan-card').forEach(function (card) { card.classList.remove('selected'); });
  var s1 = document.getElementById('modalStep1');
  var s2 = document.getElementById('modalStep2');
  var s3 = document.getElementById('modalStep3');
  if (s1) s1.hidden = false;
  if (s2) s2.hidden = true;
  if (s3) s3.hidden = true;
  setProgress(1);
}

function openUploadModal() {
  resetUploadModal();
  document.getElementById('uploadModal').showModal();
}

function closeUploadModal() {
  resetUploadModal();
  document.getElementById('uploadModal').close();
}

function resetDropzone() {
  const dz = document.getElementById('dropzone');
  const existing = dz.querySelector('.dropzone__filename');
  if (existing) existing.remove();
  document.getElementById('fileInput').value = '';
}

function showUploadError(msg) {
  const el = document.getElementById('modalError');
  el.textContent = msg;
  el.hidden = false;
}

function hideUploadError() {
  const el = document.getElementById('modalError');
  el.textContent = '';
  el.hidden = true;
}

function handleFileSelect(input) {
  if (input.files && input.files[0]) {
    selectedFile = input.files[0];
    showFileName(selectedFile.name);
    hideUploadError();
  }
}

function showFileName(name) {
  const dz = document.getElementById('dropzone');
  let el = dz.querySelector('.dropzone__filename');
  if (!el) {
    el = document.createElement('p');
    el.className = 'dropzone__filename';
    dz.appendChild(el);
  }
  el.textContent = name;
}

async function submitUpload() {
  hideUploadError();
  if (!selectedFile) {
    showUploadError('Please select a PDF or PPTX file first.');
    return;
  }
  var ext = (selectedFile.name || '').split('.').pop().toLowerCase();
  if (ext !== 'pdf' && ext !== 'pptx' && ext !== 'ppt') {
    showUploadError('Only PDF and PPTX files are supported.');
    return;
  }
  var btn = document.getElementById('submitBtn');
  var origText = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = 'Analyzing…'; }

  try {
    var form = new FormData();
    form.append('file', selectedFile);
    form.append('report_type', 'investor');
    var res = await fetch(API_BASE + '/api/analyze', { method: 'POST', body: form });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      var detail = data.detail;
      if (Array.isArray(detail) && detail[0] && detail[0].msg) detail = detail[0].msg;
      else if (typeof detail !== 'string') detail = detail ? String(detail) : '';
      throw new Error(detail || data.message || (res.status + ' ' + res.statusText) || 'Upload failed');
    }
    document.getElementById('modalStep1').hidden = true;
    document.getElementById('modalStep2').hidden = true;
    document.getElementById('modalStep3').hidden = true;
    document.getElementById('modalSuccess').hidden = false;
    document.getElementById('modalProgressFill').style.width = '100%';
    var successMsg = document.getElementById('successMessage');
    if (successMsg) successMsg.textContent = data.company_name ? 'Report for «' + data.company_name + '» is ready.' : 'Your report is ready.';
    var link = document.getElementById('successDownload');
    if (link) { link.href = API_BASE + (data.pdf_url || ''); link.style.display = 'inline-block'; }
    window._lastAnalysisData = data.data || {};
    window._lastAnalysisData.company_name = data.company_name || window._lastAnalysisData.company_name;
  } catch (err) {
    showUploadError(err.message || 'Something went wrong. Try again.');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = origText; }
  }
}

// Drag & drop
(function () {
  const dz = document.getElementById('dropzone');
  if (!dz) return;

  ['dragenter', 'dragover'].forEach(evt => {
    dz.addEventListener(evt, e => { e.preventDefault(); dz.classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(evt => {
    dz.addEventListener(evt, e => { e.preventDefault(); dz.classList.remove('dragover'); });
  });
  dz.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      selectedFile = files[0];
      showFileName(selectedFile.name);
    }
  });
  dz.addEventListener('click', e => {
    if (e.target.tagName !== 'BUTTON') {
      document.getElementById('fileInput').click();
    }
  });
})();

// Drag & drop for Find matching funds deck upload
(function () {
  var zone = document.getElementById('fundsUploadZone');
  var fileInput = document.getElementById('fundsDeckFile');
  if (!zone || !fileInput) return;
  ['dragenter', 'dragover'].forEach(function (evt) {
    zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(function (evt) {
    zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.remove('dragover'); });
  });
  zone.addEventListener('drop', function (e) {
    var files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
    }
  });
})();

// Close modal on Escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeUploadModal();
    closeFundsModal();
  }
});

/* --- Find matching funds modal --- */
function openFundsModal() {
  var dialog = document.getElementById('fundsModal');
  if (dialog && typeof dialog.showModal === 'function') {
    dialog.showModal();
    dialog.classList.add('funds-modal--form');
    var formSection = document.getElementById('fundsFormSection');
    if (formSection) formSection.hidden = false;
    document.getElementById('fundsFormWrap').hidden = false;
    document.getElementById('fundsError').hidden = true;
    var loadingEl = document.getElementById('fundsLoading');
    if (loadingEl) { loadingEl.hidden = true; }
    var loadingTxt = document.getElementById('fundsLoadingText');
    if (loadingTxt) loadingTxt.textContent = 'Matching funds…';
    document.getElementById('fundsResults').hidden = true;
    loadFundsCountriesOnce();
    var last = window._lastAnalysisData;
    if (last) {
      var companyEl = document.getElementById('fundsCompany');
      var sectorEl = document.getElementById('fundsSector');
      var stageEl = document.getElementById('fundsStage');
      var raiseEl = document.getElementById('fundsRaise');
      var geoEl = document.getElementById('fundsGeography');
      var descEl = document.getElementById('fundsDescription');
      if (companyEl && last.company_name) companyEl.value = last.company_name;
      if (sectorEl && last.sector) sectorEl.value = (last.sector || '').toLowerCase().replace(/\s+/g, '-');
      if (stageEl && last.stage) stageEl.value = (last.stage || '').toLowerCase().replace(/\s+/g, '-');
      if (raiseEl && last.target_raise) raiseEl.value = last.target_raise;
      if (geoEl && last.geography) geoEl.value = last.geography;
      if (descEl && last.overall_summary) descEl.value = last.overall_summary;
    }
  }
}

var _fundsCountriesLoaded = false;
var FUNDS_COUNTRIES_FALLBACK = [
  'United States', 'United Kingdom', 'Germany', 'France', 'Netherlands', 'Israel', 'Singapore',
  'Canada', 'India', 'Australia', 'Sweden', 'Switzerland', 'Spain', 'Italy', 'Japan', 'China',
  'Brazil', 'South Korea', 'Ireland', 'Estonia', 'Poland', 'Ukraine', 'United Arab Emirates'
];
function loadFundsCountriesOnce() {
  var sel = document.getElementById('fundsGeography');
  if (!sel) return;
  if (_fundsCountriesLoaded) return;
  fetch(API_BASE + '/api/match-funds/countries')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var list = (data && data.countries && data.countries.length) ? data.countries : FUNDS_COUNTRIES_FALLBACK;
      for (var i = 0; i < list.length; i++) {
        var opt = document.createElement('option');
        opt.value = list[i];
        opt.textContent = list[i];
        sel.appendChild(opt);
      }
      _fundsCountriesLoaded = true;
    })
    .catch(function () {
      for (var j = 0; j < FUNDS_COUNTRIES_FALLBACK.length; j++) {
        var o = document.createElement('option');
        o.value = FUNDS_COUNTRIES_FALLBACK[j];
        o.textContent = FUNDS_COUNTRIES_FALLBACK[j];
        sel.appendChild(o);
      }
      _fundsCountriesLoaded = true;
    });
}

function closeFundsModal() {
  var dialog = document.getElementById('fundsModal');
  if (dialog && typeof dialog.close === 'function') dialog.close();
  var loadingEl = document.getElementById('fundsLoading');
  if (loadingEl) loadingEl.hidden = true;
}

function showFundsError(msg) {
  var el = document.getElementById('fundsError');
  if (el) { el.textContent = msg; el.hidden = false; }
}

function hideFundsError() {
  var el = document.getElementById('fundsError');
  if (el) el.hidden = true;
}

function renderFundsResults(data, fromDeck) {
  var summaryEl = document.getElementById('fundsSummary');
  var listEl = document.getElementById('fundsList');
  var profileEl = document.getElementById('fundsProfileFromDeck');
  var loading = document.getElementById('fundsLoading');
  if (loading) loading.hidden = true;
  if (summaryEl) summaryEl.textContent = data.summary || '';
  if (profileEl) {
    if (fromDeck && data.profile) {
      var p = data.profile;
      var parts = [];
      if (p.company_name) parts.push(p.company_name);
      if (p.sector) parts.push('Sector: ' + p.sector);
      if (p.stage) parts.push('Stage: ' + p.stage);
      if (p.target_raise) parts.push('Raise: ' + p.target_raise);
      if (p.geography) parts.push('Geo: ' + p.geography);
      profileEl.textContent = 'From your deck: ' + (parts.length ? parts.join(' · ') : '—');
      profileEl.hidden = false;
    } else {
      profileEl.hidden = true;
    }
  }
  if (listEl) {
    listEl.innerHTML = '';
    var recs = data.recommendations || [];
    if (recs.length === 0) {
      var emptyMsg = document.createElement('p');
      emptyMsg.className = 'funds-results__empty';
      emptyMsg.textContent = 'No matching funds found. Try different sector/stage or geography; if the list stays empty, ensure the funds database is indexed (see funds-rag-service).';
      listEl.appendChild(emptyMsg);
    }
    recs.forEach(function (rec) {
      var card = document.createElement('div');
      card.className = 'funds-card';
      var link = rec.website ? '<a href="' + rec.website + '" target="_blank" rel="noopener" class="funds-card__link">Website</a>' : '';
      var hq = '';
      if (rec.city && rec.country) hq = rec.city + ', ' + rec.country;
      else if (rec.country) hq = rec.country;

      var gridHtml = '';
      if (hq || rec.check_size || rec.business_models) {
        gridHtml = '<div class="funds-card__grid">';
        if (hq) {
          gridHtml += '' +
            '<div class="funds-card__cell">' +
              '<div class="funds-card__cell-label">HQ</div>' +
              '<div class="funds-card__cell-value">' + hq + '</div>' +
            '</div>';
        }
        if (rec.check_size) {
          gridHtml += '' +
            '<div class="funds-card__cell">' +
              '<div class="funds-card__cell-label">Check size</div>' +
              '<div class="funds-card__cell-value">' + rec.check_size + '</div>' +
            '</div>';
        }
        if (rec.business_models) {
          gridHtml += '' +
            '<div class="funds-card__cell">' +
              '<div class="funds-card__cell-label">Focus</div>' +
              '<div class="funds-card__cell-value">' + rec.business_models + '</div>' +
            '</div>';
        }
        gridHtml += '</div>';
      }

      card.innerHTML =
        '<div class="funds-card__name">' + (rec.investor_name || '') + '</div>' +
        gridHtml +
        (rec.reasoning ? '<p class="funds-card__reasoning">' + rec.reasoning + '</p>' : '') +
        '<div class="funds-card__links">' + link + '</div>';
      listEl.appendChild(card);
    });
  }
}

async function submitMatchFundsFromDeck() {
  hideFundsError();
  var fileInput = document.getElementById('fundsDeckFile');
  var file = fileInput && fileInput.files && fileInput.files[0];
  if (!file) {
    showFundsError('Please select a PDF or PPTX file.');
    return;
  }
  var formWrap = document.getElementById('fundsFormWrap');
  var dialog = document.getElementById('fundsModal');
  var deckBlock = document.querySelector('.funds-upload');
  var loading = document.getElementById('fundsLoading');
  var loadingText = document.getElementById('fundsLoadingText');
  var results = document.getElementById('fundsResults');
  var btn = document.getElementById('fundsDeckSubmitBtn');
  if (formWrap) formWrap.hidden = true;
  if (deckBlock) deckBlock.style.pointerEvents = 'none';
  if (results) results.hidden = true;
  if (btn) btn.disabled = true;

  var formData = new FormData();
  formData.append('file', file);

  try {
    if (loading) { loading.hidden = false; if (loadingText) loadingText.textContent = 'Analyzing deck and matching funds…'; }
    var res = await fetch(API_BASE + '/api/match-funds-from-deck', {
      method: 'POST',
      body: formData,
    });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error(data.detail || data.message || res.statusText || 'Failed to analyze and match.');
    }
    if (formWrap) formWrap.hidden = true;
    if (loading) loading.hidden = true;
    if (results) results.hidden = false;
    dialog.classList.remove('funds-modal--form');
    var formSection = document.getElementById('fundsFormSection');
    if (formSection) formSection.hidden = true;
    renderFundsResults(data, true);
    if (data.profile) {
      window._lastAnalysisData = {
        company_name: data.profile.company_name,
        sector: data.profile.sector,
        stage: data.profile.stage,
        target_raise: data.profile.target_raise,
        geography: data.profile.geography,
        overall_summary: data.profile.description,
      };
    }
  } catch (err) {
    if (loading) loading.hidden = true;
    showFundsError(err.message || 'Something went wrong. Try again.');
    if (formWrap) formWrap.hidden = false;
    if (results) results.hidden = true;
    if (dialog) dialog.classList.add('funds-modal--form');
    var formSection = document.getElementById('fundsFormSection');
    if (formSection) formSection.hidden = false;
  } finally {
    if (loading) loading.hidden = true;
    if (deckBlock) deckBlock.style.pointerEvents = '';
    if (btn) btn.disabled = false;
  }
}

async function submitMatchFunds() {
  hideFundsError();
  var sector = (document.getElementById('fundsSector') || {}).value;
  var stage = (document.getElementById('fundsStage') || {}).value;
  if (!sector || !stage) {
    showFundsError('Please select at least Sector and Stage.');
    return;
  }
  var formWrap = document.getElementById('fundsFormWrap');
  var loading = document.getElementById('fundsLoading');
  var results = document.getElementById('fundsResults');
  var btn = document.getElementById('fundsSubmitBtn');
  if (formWrap) formWrap.hidden = true;
  if (results) results.hidden = true;
  if (btn) btn.disabled = true;

  var geography = (document.getElementById('fundsGeography') || {}).value || null;
  if (geography === '') geography = null;
  var body = {
    company_name: (document.getElementById('fundsCompany') || {}).value || null,
    sector: sector,
    stage: stage,
    geography: geography,
    target_raise: (document.getElementById('fundsRaise') || {}).value || null,
    description: (document.getElementById('fundsDescription') || {}).value || null,
    language: 'en',
  };

  try {
    if (loading) loading.hidden = false;
    var res = await fetch(API_BASE + '/api/match-funds', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error(data.detail || data.message || res.statusText || 'Fund matching failed');
    }
    if (formWrap) formWrap.hidden = true;
    if (loading) loading.hidden = true;
    if (results) results.hidden = false;
    var fundsDialog = document.getElementById('fundsModal');
    if (fundsDialog) fundsDialog.classList.remove('funds-modal--form');
    var formSection = document.getElementById('fundsFormSection');
    if (formSection) formSection.hidden = true;
    var profileEl = document.getElementById('fundsProfileFromDeck');
    if (profileEl) profileEl.hidden = true;
    renderFundsResults(data, false);
  } catch (err) {
    if (loading) loading.hidden = true;
    var msg = err.message || 'Something went wrong. Try again.';
    showFundsError(msg);
    if (formWrap) formWrap.hidden = false;
    if (results) results.hidden = true;
    var formSection = document.getElementById('fundsFormSection');
    if (formSection) formSection.hidden = false;
  } finally {
    if (loading) loading.hidden = true;
    if (btn) btn.disabled = false;
  }
}

// On page load: close modal and reset so no previous file/result is ever shown; preload countries for funds modal
document.addEventListener('DOMContentLoaded', function () {
  var dialog = document.getElementById('uploadModal');
  if (dialog && typeof dialog.close === 'function') dialog.close();
  resetUploadModal();
  var fundsDialog = document.getElementById('fundsModal');
  if (fundsDialog && typeof fundsDialog.close === 'function') fundsDialog.close();
  var fundsLoadingEl = document.getElementById('fundsLoading');
  if (fundsLoadingEl) fundsLoadingEl.hidden = true;
  loadFundsCountriesOnce();
});

/* --- Newsletter --- */
function handleNewsletter(e) {
  e.preventDefault();
  const input = e.target.querySelector('input[type="email"]');
  if (input && input.value) {
    input.value = '';
    input.placeholder = 'Subscribed!';
    setTimeout(() => { input.placeholder = 'your@email.com'; }, 2000);
  }
}

/* --- IntersectionObserver Fade-in (universal — works on all browsers) --- */
(function () {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.fade-in').forEach(el => {
    // CSS class controls opacity:0 — no inline styles that could conflict
    el.classList.add('fade-in--ready');
    observer.observe(el);
  });
})();

/* --- Animate scorecard bars on scroll --- */
(function () {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.querySelectorAll('.metric__fill').forEach(bar => {
          const score = bar.dataset.score;
          bar.style.width = score + '%';
        });
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  const card = document.querySelector('.scorecard__card');
  if (card) {
    // Start bars at 0
    card.querySelectorAll('.metric__fill').forEach(bar => {
      bar.style.width = '0%';
    });
    observer.observe(card);
  }
})();

/* --- Deals Ticker --- */
(async function initDealsTicker() {
  const tickerEl = document.getElementById('dealsTicker');
  if (!tickerEl) return;

  const API_URL = (window.location.hostname === 'localhost' && window.location.port === '5500')
    ? 'http://localhost:8000/api/deals/latest?limit=20'
    : '/api/deals/latest?limit=20';

  try {
    const res = await fetch(API_URL);
    if (!res.ok) throw new Error('Failed to fetch deals');
    const data = await res.json();
    const deals = data.deals;

    if (!deals || deals.length === 0) {
      tickerEl.style.display = 'none';
      return;
    }

    const escapeHtml = (s) => {
      const div = document.createElement('div');
      div.textContent = s;
      return div.innerHTML;
    };

    const buildItems = () => deals.map(deal => {
      const roundBadge = deal.round
        ? `<span class="deals-ticker__round">${escapeHtml(deal.round)}</span>`
        : '';
      return `
        <span class="deals-ticker__item">
          <a href="${escapeHtml(deal.url || '#')}" target="_blank" rel="noopener">
            <span class="deals-ticker__company">${escapeHtml(deal.company)}</span>
            raises
            <span class="deals-ticker__amount">${escapeHtml(deal.amount)}</span>
            ${roundBadge}
          </a>
        </span>
        <span class="deals-ticker__separator">·</span>
      `;
    }).join('');

    const track = tickerEl.querySelector('.deals-ticker__track');
    const itemsHTML = buildItems();
    track.innerHTML = itemsHTML + itemsHTML;

    const halfWidth = track.scrollWidth / 2;
    const speed = Math.max(30, halfWidth / 25);
    track.style.animationDuration = `${speed}s`;
  } catch (err) {
    console.warn('Deals ticker unavailable:', err.message);
    tickerEl.style.display = 'none';
  }
})();
