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
      selectedPlan = 'basic';
      document.querySelectorAll('.modal-plan-card').forEach(function (card) {
        card.classList.toggle('selected', card.getAttribute('data-plan') === 'basic');
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
    if (planEl) planEl.textContent = selectedPlan === 'expert' ? 'Expert' : selectedPlan === 'pro' ? 'Pro' : 'Basic';
    if (emailEl) emailEl.textContent = (document.getElementById('modalEmail') || {}).value || '—';
    renderPayPalButton();
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

  if (su) { su.hidden = true; su.style.display = ''; }
  if (link) { link.setAttribute('href', '#'); link.style.display = 'inline-block'; }
  if (msg) msg.textContent = 'Your report is ready.';
  if (err) { err.textContent = ''; err.hidden = true; err.style.display = ''; }
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
  var progressBar = document.querySelector('.modal__progress');
  // Clear any inline display overrides from payment handler
  if (s1) { s1.hidden = false; s1.style.display = ''; }
  if (s2) { s2.hidden = true; s2.style.display = ''; }
  if (s3) { s3.hidden = true; s3.style.display = ''; }
  if (progressBar) { progressBar.hidden = false; progressBar.style.display = ''; }
  // Remove free progress bar if present (created dynamically)
  var freeWrap = document.getElementById('freeProgressWrap');
  var freeLabel = document.getElementById('freeProgressLabel');
  if (freeWrap) freeWrap.remove();
  if (freeLabel) freeLabel.remove();
  // Reset feedback widget
  var fbWidget = document.getElementById('feedbackWidget');
  if (fbWidget) fbWidget.style.display = 'none';
  // Reset email form
  var emailForm = document.getElementById('emailSendForm');
  var emailSent = document.getElementById('emailSentMessage');
  var emailError = document.getElementById('emailError');
  if (emailForm) { emailForm.hidden = false; emailForm.style.display = ''; }
  if (emailSent) { emailSent.hidden = true; emailSent.style.display = ''; }
  if (emailError) { emailError.hidden = true; emailError.style.display = ''; }
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

/* --- Helper: show success after analysis (used by both free and paid flows) --- */
function showAnalysisSuccess(data) {
  document.getElementById('modalStep1').hidden = true;
  document.getElementById('modalStep2').hidden = true;
  document.getElementById('modalStep3').hidden = true;
  document.getElementById('modalSuccess').hidden = false;
  var mpf = document.getElementById('modalProgressFill');
  if (mpf) mpf.style.width = '100%';
  var successMsg = document.getElementById('successMessage');
  if (successMsg) successMsg.textContent = data.company_name ? 'Report for «' + data.company_name + '» is ready.' : 'Your report is ready.';
  var link = document.getElementById('successDownload');
  if (link) { link.href = API_BASE + (data.pdf_url || ''); link.style.display = 'inline-block'; }
  window._lastAnalysisData = data.data || {};
  window._lastAnalysisData.company_name = data.company_name || window._lastAnalysisData.company_name;
  // Store report info for email sending
  window._lastReportId = data.report_id || '';
  window._lastReportType = data.report_type || 'investor';
  window._lastCompanyName = data.company_name || '';
  // Reset email form state
  var emailForm = document.getElementById('emailSendForm');
  if (emailForm) emailForm.hidden = false;
  var emailSent = document.getElementById('emailSentMessage');
  if (emailSent) emailSent.hidden = true;
  // Pre-fill email from modal form if available
  var reportEmail = document.getElementById('reportEmail');
  var modalEmail = document.getElementById('modalEmail');
  if (reportEmail && modalEmail && modalEmail.value) reportEmail.value = modalEmail.value;
  // Init feedback widget
  initFeedbackWidget();
}

/* --- Feedback Widget --- */
var _feedbackRating = 0;
var _feedbackSubmitted = false;

function initFeedbackWidget() {
  var widget = document.getElementById('feedbackWidget');
  var starsContainer = document.getElementById('feedbackStars');
  if (!widget || !starsContainer) return;
  // Reset state
  _feedbackRating = 0;
  _feedbackSubmitted = false;
  widget.style.display = 'block';
  document.getElementById('feedbackReasons').style.display = 'none';
  document.getElementById('feedbackThanks').style.display = 'none';
  var comment = document.getElementById('feedbackComment');
  if (comment) { comment.style.display = 'none'; comment.value = ''; }
  // Reset chips
  document.querySelectorAll('.fb-chip').forEach(function (chip) { chip.classList.remove('selected'); });
  // Build stars
  starsContainer.innerHTML = '';
  for (var i = 1; i <= 5; i++) {
    var star = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    star.setAttribute('class', 'fb-star');
    star.setAttribute('data-rating', i);
    star.setAttribute('viewBox', '0 0 24 24');
    star.setAttribute('width', '32');
    star.setAttribute('height', '32');
    star.setAttribute('fill', 'currentColor');
    star.setAttribute('stroke', 'none');
    star.innerHTML = '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.27 5.82 22 7 14.14 2 9.27l6.91-1.01L12 2z"/>';
    star.style.cursor = 'pointer';
    (function (rating) {
      star.addEventListener('mouseenter', function () { highlightStars(rating); });
      star.addEventListener('click', function () { selectRating(rating); });
    })(i);
    starsContainer.appendChild(star);
  }
  starsContainer.addEventListener('mouseleave', function () { highlightStars(_feedbackRating); });
  // Chip toggle
  document.querySelectorAll('.fb-chip').forEach(function (chip) {
    chip.onclick = function () {
      chip.classList.toggle('selected');
      var input = chip.querySelector('input');
      var commentEl = document.getElementById('feedbackComment');
      if (input && input.value === 'other') {
        commentEl.style.display = chip.classList.contains('selected') ? 'block' : 'none';
        if (chip.classList.contains('selected') && commentEl) commentEl.focus();
      }
    };
  });
}

function highlightStars(rating) {
  var stars = document.querySelectorAll('#feedbackStars .fb-star');
  stars.forEach(function (s) {
    var r = parseInt(s.getAttribute('data-rating'));
    s.classList.toggle('active', r <= rating);
  });
}

function selectRating(rating) {
  _feedbackRating = rating;
  highlightStars(rating);
  if (rating >= 4) {
    // Happy path: submit immediately
    doSubmitFeedback(rating, [], '');
  } else {
    // Show reasons
    document.getElementById('feedbackReasons').style.display = 'block';
  }
}

function submitFeedback() {
  var reasons = [];
  document.querySelectorAll('.fb-chip.selected input').forEach(function (input) {
    reasons.push(input.value);
  });
  var comment = (document.getElementById('feedbackComment') || {}).value || '';
  doSubmitFeedback(_feedbackRating, reasons, comment);
}

function doSubmitFeedback(rating, reasons, comment) {
  if (_feedbackSubmitted) return;
  _feedbackSubmitted = true;
  var reportId = window._lastReportId || '';
  fetch(API_BASE + '/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_id: reportId, rating: rating, reasons: reasons, comment: comment }),
  }).catch(function () {});
  // Show thank you
  var starsContainer = document.getElementById('feedbackStars');
  var reasons_el = document.getElementById('feedbackReasons');
  var thanks = document.getElementById('feedbackThanks');
  if (reasons_el) reasons_el.style.display = 'none';
  if (thanks) thanks.style.display = 'block';
  // Disable stars
  if (starsContainer) starsContainer.style.pointerEvents = 'none';
}

/* --- Free plan: progress bar + polling --- */
function showFreeAnalysisProgress(token) {
  // Hide steps, show success section with progress bar
  var s1 = document.getElementById('modalStep1');
  var s2 = document.getElementById('modalStep2');
  var s3 = document.getElementById('modalStep3');
  var su = document.getElementById('modalSuccess');
  var progressBar = document.querySelector('.modal__progress');
  var modalError = document.getElementById('modalError');
  if (s1) s1.style.display = 'none';
  if (s2) s2.style.display = 'none';
  if (s3) s3.style.display = 'none';
  if (progressBar) progressBar.style.display = 'none';
  if (modalError) { modalError.style.display = 'none'; }
  if (su) { su.hidden = false; su.style.display = ''; }

  var successMsg = document.getElementById('successMessage');
  if (successMsg) successMsg.textContent = 'Analyzing your deck\u2026';
  var link = document.getElementById('successDownload');
  if (link) link.style.display = 'none';
  var emailForm = document.getElementById('emailSendForm');
  if (emailForm) emailForm.style.display = 'none';
  var emailSent = document.getElementById('emailSentMessage');
  if (emailSent) emailSent.style.display = 'none';

  // Create progress bar elements
  var progressWrap = document.createElement('div');
  progressWrap.id = 'freeProgressWrap';
  progressWrap.style.cssText = 'width:100%;max-width:400px;margin:18px auto 8px;background:var(--color-surface-2,#f0f0f0);border-radius:8px;height:10px;overflow:hidden;';
  var progressFill = document.createElement('div');
  progressFill.id = 'freeProgressFill';
  progressFill.style.cssText = 'height:100%;width:0%;background:linear-gradient(90deg,#00e5c3,#00c4a7);border-radius:8px;transition:width 0.6s ease;';
  progressWrap.appendChild(progressFill);
  var progressLabel = document.createElement('p');
  progressLabel.id = 'freeProgressLabel';
  progressLabel.style.cssText = 'text-align:center;font-size:13px;color:var(--color-text-muted,#888);margin:6px 0 0;';
  progressLabel.textContent = '';
  if (successMsg && successMsg.parentNode) {
    successMsg.parentNode.insertBefore(progressWrap, successMsg.nextSibling);
    progressWrap.parentNode.insertBefore(progressLabel, progressWrap.nextSibling);
  }

  // Stage animation
  var stages = [
    { pct: 5,  text: 'Uploading deck\u2026',                            time: 0 },
    { pct: 15, text: 'Converting slides\u2026',                          time: 3000 },
    { pct: 30, text: 'AI analyzing slides (this may take 1\u20132 min)\u2026', time: 10000 },
    { pct: 50, text: 'Deep analysis in progress\u2026',                  time: 40000 },
    { pct: 70, text: 'Generating your report\u2026',                     time: 90000 },
    { pct: 85, text: 'Almost done\u2026',                                time: 140000 },
  ];
  var stageTimers = [];
  stages.forEach(function (stage) {
    var t = setTimeout(function () {
      progressFill.style.width = stage.pct + '%';
      progressLabel.textContent = stage.text;
    }, stage.time);
    stageTimers.push(t);
  });

  function stopProgress() {
    stageTimers.forEach(function (t) { clearTimeout(t); });
    progressFill.style.width = '100%';
    progressLabel.textContent = '';
    setTimeout(function () {
      progressWrap.style.display = 'none';
      progressLabel.style.display = 'none';
    }, 600);
  }

  // Poll for result
  var pollCount = 0;
  var maxPolls = 120; // 120 * 4s = 8 min
  function doPoll() {
    pollCount++;
    fetch(API_BASE + '/api/analyze-free-status?token=' + encodeURIComponent(token))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.status === 'done' && data.result) {
          stopProgress();
          showAnalysisSuccess(data.result);
        } else if (data.status === 'error') {
          stopProgress();
          if (successMsg) successMsg.textContent = 'Analysis failed: ' + (data.error || 'Unknown error') + '. Please try again.';
        } else if (pollCount < maxPolls) {
          setTimeout(doPoll, 4000);
        } else {
          stopProgress();
          if (successMsg) successMsg.textContent = 'Analysis is taking too long. Please try again later.';
        }
      })
      .catch(function (err) {
        console.error('Free analysis poll error:', err);
        if (pollCount < maxPolls) {
          setTimeout(doPoll, 5000);
        } else {
          stopProgress();
          if (successMsg) successMsg.textContent = 'Connection lost. Please try again.';
        }
      });
  }
  setTimeout(doPoll, 3000);
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
  if (btn) { btn.disabled = true; btn.textContent = 'Processing…'; }

  // ---- All plans go through Stripe Checkout ----
  if (!selectedPlan) selectedPlan = 'basic';
  try {
    if (btn) btn.textContent = 'Redirecting to payment…';
    var form = new FormData();
    form.append('file', selectedFile);
    form.append('plan', selectedPlan);
    form.append('email', (document.getElementById('modalEmail') || {}).value || '');
    form.append('company', (document.getElementById('modalCompany') || {}).value || '');
    form.append('stage', (document.getElementById('modalStage') || {}).value || '');
    form.append('report_type', 'investor');

    var res = await fetch(API_BASE + '/api/stripe/create-checkout-session', {
      method: 'POST',
      body: form,
    });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error(data.detail || data.message || 'Failed to create payment session');
    }

    // Save token for post-payment processing
    sessionStorage.setItem('ctd_payment_token', data.token || '');
    sessionStorage.setItem('ctd_session_id', data.session_id || '');

    // Redirect to Stripe Checkout
    window.location.href = data.url;

  } catch (err) {
    showUploadError(err.message || 'Payment setup failed. Try again.');
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
  var fundsDialog = document.getElementById('fundsModal');
  if (fundsDialog && typeof fundsDialog.close === 'function') fundsDialog.close();
  var fundsLoadingEl = document.getElementById('fundsLoading');
  if (fundsLoadingEl) fundsLoadingEl.hidden = true;
  loadFundsCountriesOnce();

  // Check if returning from Stripe payment (only URL params — sessionStorage is for the payment handler)
  var params = new URLSearchParams(window.location.search);
  var isPaymentReturn = params.get('session_id') || params.get('token');
  if (isPaymentReturn) {
    // Don't reset — payment handler below will set up the modal
    return;
  }
  // Normal page load — clear any stale payment tokens
  sessionStorage.removeItem('ctd_payment_token');
  sessionStorage.removeItem('ctd_session_id');
  // Normal page load — reset modal
  var dialog = document.getElementById('uploadModal');
  if (dialog && typeof dialog.close === 'function') dialog.close();
  resetUploadModal();
});

/* --- Send report to email --- */
async function sendReportEmail() {
  var emailInput = document.getElementById('reportEmail');
  var sendBtn = document.getElementById('emailSendBtn');
  var emailForm = document.getElementById('emailSendForm');
  var emailSent = document.getElementById('emailSentMessage');
  var emailError = document.getElementById('emailError');

  if (!emailInput || !emailInput.value || !emailInput.value.includes('@')) {
    if (emailError) { emailError.textContent = 'Please enter a valid email.'; emailError.hidden = false; }
    if (emailInput) emailInput.focus();
    return;
  }
  if (emailError) emailError.hidden = true;

  if (!window._lastReportId) {
    if (emailError) { emailError.textContent = 'No report available to send.'; emailError.hidden = false; }
    return;
  }

  var origText = sendBtn ? sendBtn.textContent : '';
  if (sendBtn) { sendBtn.disabled = true; sendBtn.textContent = 'Sending…'; }

  try {
    var res = await fetch(API_BASE + '/api/email/send-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: emailInput.value,
        report_id: window._lastReportId,
        report_type: window._lastReportType || 'investor',
        company_name: window._lastCompanyName || 'your deck',
      }),
    });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error(data.detail || data.message || 'Failed to send email');
    }
    // Show success
    if (emailForm) emailForm.hidden = true;
    if (emailSent) {
      emailSent.textContent = 'Report sent to ' + emailInput.value + ' \u2709';
      emailSent.hidden = false;
    }
  } catch (err) {
    if (emailError) { emailError.textContent = err.message || 'Failed to send. Try again.'; emailError.hidden = false; }
  } finally {
    if (sendBtn) { sendBtn.disabled = false; sendBtn.textContent = origText; }
  }
}

/* --- Contact Form --- */
async function submitContactForm(e) {
  e.preventDefault();
  var nameEl = document.getElementById('contactName');
  var emailEl = document.getElementById('contactEmail');
  var msgEl = document.getElementById('contactMessage');
  var btn = document.getElementById('contactSubmitBtn');
  var status = document.getElementById('contactStatus');

  if (!nameEl.value.trim() || !emailEl.value.trim() || !msgEl.value.trim()) return;

  var origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Sending…';
  status.hidden = true;

  try {
    var res = await fetch(API_BASE + '/api/email/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: nameEl.value.trim(),
        email: emailEl.value.trim(),
        message: msgEl.value.trim(),
      }),
    });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.detail || data.message || 'Failed to send');
    status.textContent = 'Message sent! We will get back to you soon.';
    status.className = 'support__form-status support__form-status--success';
    status.hidden = false;
    nameEl.value = '';
    emailEl.value = '';
    msgEl.value = '';
  } catch (err) {
    status.textContent = err.message || 'Failed to send. Please try again.';
    status.className = 'support__form-status support__form-status--error';
    status.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
}

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

/* --- Post-payment: handle return from Stripe Checkout --- */
/* Runs on DOMContentLoaded to ensure all DOM elements exist */
document.addEventListener('DOMContentLoaded', function () {
  var params = new URLSearchParams(window.location.search);
  var sessionId = params.get('session_id');
  var token = params.get('token');
  var paymentCancelled = params.get('payment');

  // Handle cancel
  if (paymentCancelled === 'cancelled') {
    window.history.replaceState({}, '', window.location.pathname);
    return;
  }

  // Handle success return from Stripe
  if (!sessionId && !token) {
    token = sessionStorage.getItem('ctd_payment_token');
    sessionId = sessionStorage.getItem('ctd_session_id');
    if (!token) return;
  }

  // Clean URL params
  window.history.replaceState({}, '', window.location.pathname);

  // Show processing modal — clean slate
  var dialog = document.getElementById('uploadModal');
  if (dialog && typeof dialog.showModal === 'function') {
    dialog.showModal();
  }

  // Hide EVERYTHING: all steps, progress bar, error
  // Using style.display because CSS .modal__step { display: block } overrides [hidden]
  var s1 = document.getElementById('modalStep1');
  var s2 = document.getElementById('modalStep2');
  var s3 = document.getElementById('modalStep3');
  var su = document.getElementById('modalSuccess');
  var progressBar = document.querySelector('.modal__progress');
  var modalError = document.getElementById('modalError');
  if (s1) s1.style.display = 'none';
  if (s2) s2.style.display = 'none';
  if (s3) s3.style.display = 'none';
  if (progressBar) progressBar.style.display = 'none';
  if (modalError) modalError.style.display = 'none';

  // Show only the success section with processing message
  if (su) { su.hidden = false; su.style.display = ''; }
  var successMsg = document.getElementById('successMessage');
  if (successMsg) successMsg.textContent = 'Payment received! Verifying payment\u2026';
  var link = document.getElementById('successDownload');
  if (link) link.style.display = 'none';
  // Hide email form during processing
  var emailForm = document.getElementById('emailSendForm');
  if (emailForm) emailForm.style.display = 'none';
  var emailSent = document.getElementById('emailSentMessage');
  if (emailSent) emailSent.style.display = 'none';

  // -- Create progress bar for analysis --
  var progressWrap = document.createElement('div');
  progressWrap.id = 'analysisProgressWrap';
  progressWrap.style.cssText = 'width:100%;max-width:400px;margin:18px auto 8px;background:var(--color-surface-2,#f0f0f0);border-radius:8px;height:10px;overflow:hidden;display:none;';
  var progressFill = document.createElement('div');
  progressFill.id = 'analysisProgressFill';
  progressFill.style.cssText = 'height:100%;width:0%;background:linear-gradient(90deg,#00e5c3,#00c4a7);border-radius:8px;transition:width 0.6s ease;';
  progressWrap.appendChild(progressFill);
  var progressLabel = document.createElement('p');
  progressLabel.id = 'analysisProgressLabel';
  progressLabel.style.cssText = 'text-align:center;font-size:13px;color:var(--color-text-muted,#888);margin:6px 0 0;';
  progressLabel.textContent = '';
  // Insert after successMessage
  if (successMsg && successMsg.parentNode) {
    successMsg.parentNode.insertBefore(progressWrap, successMsg.nextSibling);
    progressWrap.parentNode.insertBefore(progressLabel, progressWrap.nextSibling);
  }

  var analysisStages = [
    { pct: 5, text: 'Verifying payment\u2026', time: 0 },
    { pct: 15, text: 'Uploading deck\u2026', time: 3000 },
    { pct: 25, text: 'Converting slides\u2026', time: 8000 },
    { pct: 45, text: 'AI analyzing slides (this may take 1\u20132 min)\u2026', time: 20000 },
    { pct: 65, text: 'Deep analysis in progress\u2026', time: 60000 },
    { pct: 80, text: 'Generating your report\u2026', time: 120000 },
    { pct: 90, text: 'Almost done\u2026', time: 160000 },
  ];
  var stageTimers = [];
  function startAnalysisProgress() {
    progressWrap.style.display = 'block';
    analysisStages.forEach(function (stage) {
      var t = setTimeout(function () {
        progressFill.style.width = stage.pct + '%';
        progressLabel.textContent = stage.text;
      }, stage.time);
      stageTimers.push(t);
    });
  }
  function stopAnalysisProgress() {
    stageTimers.forEach(function (t) { clearTimeout(t); });
    progressFill.style.width = '100%';
    progressLabel.textContent = '';
    setTimeout(function () {
      progressWrap.style.display = 'none';
      progressLabel.style.display = 'none';
    }, 600);
  }

  // Poll for payment confirmation, then trigger analysis
  var attempts = 0;
  var maxAttempts = 30;
  var paymentMeta = null;

  function pollAndProcess() {
    attempts++;
    var verifyUrl = API_BASE + '/api/stripe/verify-payment?token=' + encodeURIComponent(token || '');
    if (sessionId) verifyUrl += '&session_id=' + encodeURIComponent(sessionId);

    fetch(verifyUrl)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.paid) {
          paymentMeta = data.meta || {};
          var plan = (paymentMeta.plan || 'basic').toLowerCase();
          if (plan === 'pro' || plan === 'expert') {
            // Pro/Expert: human review, show "coming in 24 hours"
            if (successMsg) successMsg.innerHTML = '<strong>Payment confirmed!</strong><br><br>Your deck is being analyzed by our AI engine. After that, our expert investor team will review it personally.<br><br>You will receive the full report at <strong>' + (paymentMeta.email || 'your email') + '</strong> within <strong>24 hours</strong>.';
            triggerAnalysis(); // still run GPT analysis as a draft
          } else {
            // Basic: instant GPT report
            if (successMsg) successMsg.textContent = 'Payment confirmed! Analyzing your deck\u2026';
            startAnalysisProgress();
            triggerAnalysis();
          }
        } else if (attempts < maxAttempts) {
          setTimeout(pollAndProcess, 2000);
        } else {
          if (successMsg) successMsg.textContent = 'Payment is processing. You will receive your report via email shortly.';
          sessionStorage.removeItem('ctd_payment_token');
          sessionStorage.removeItem('ctd_session_id');
        }
      })
      .catch(function (err) {
        console.error('Payment verification error:', err);
        if (attempts < maxAttempts) {
          setTimeout(pollAndProcess, 2000);
        } else {
          if (successMsg) successMsg.textContent = 'Something went wrong. Contact support.';
        }
      });
  }

  function triggerAnalysis() {
    // Step 1: Tell backend to start analysis (returns immediately with {status:"processing"})
    fetch(API_BASE + '/api/stripe/process-paid', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token, session_id: sessionId }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error('process-paid returned ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (data.status === 'done' && data.result) {
          // Already finished (cached from previous call)
          stopAnalysisProgress();
          showAnalysisSuccess(data.result);
          handleAutoEmail(data.result);
          sessionStorage.removeItem('ctd_payment_token');
          sessionStorage.removeItem('ctd_session_id');
        } else {
          // status === 'processing' — poll for results
          pollAnalysisStatus();
        }
      })
      .catch(function (err) {
        console.error('process-paid error:', err);
        stopAnalysisProgress();
        if (successMsg) successMsg.textContent = 'Failed to start analysis. Please refresh the page or contact support.';
      });

    // Step 2: Poll /analysis-status every 4 seconds until done/error
    function pollAnalysisStatus() {
      var pollCount = 0;
      var maxPolls = 120; // 120 * 4s = 8 minutes max

      function doPoll() {
        pollCount++;
        fetch(API_BASE + '/api/stripe/analysis-status?token=' + encodeURIComponent(token))
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.status === 'done' && data.result) {
              stopAnalysisProgress();
              showAnalysisSuccess(data.result);
              handleAutoEmail(data.result);
              sessionStorage.removeItem('ctd_payment_token');
              sessionStorage.removeItem('ctd_session_id');
            } else if (data.status === 'error') {
              stopAnalysisProgress();
              if (successMsg) successMsg.textContent = 'Analysis failed: ' + (data.error || 'Unknown error') + '. Please contact support.';
            } else if (pollCount < maxPolls) {
              setTimeout(doPoll, 4000);
            } else {
              stopAnalysisProgress();
              if (successMsg) successMsg.textContent = 'Analysis is taking too long. Your report will be sent to your email when ready.';
            }
          })
          .catch(function (err) {
            console.error('analysis-status poll error:', err);
            if (pollCount < maxPolls) {
              setTimeout(doPoll, 5000);
            } else {
              stopAnalysisProgress();
              if (successMsg) successMsg.textContent = 'Connection lost. Your report will be sent to your email when ready.';
            }
          });
      }

      // Start polling after a short delay (give backend time to begin)
      setTimeout(doPoll, 3000);
    }

    // Auto-send email (backend already does this, but show UI feedback)
    function handleAutoEmail(result) {
      var customerEmail = paymentMeta.email || '';
      if (customerEmail) {
        var emailSentEl = document.getElementById('emailSentMessage');
        if (emailSentEl) {
          emailSentEl.textContent = 'Report also sent to ' + customerEmail + ' \u2709';
          emailSentEl.hidden = false;
          emailSentEl.style.display = '';
        }
        var reportEmail = document.getElementById('reportEmail');
        if (reportEmail) reportEmail.value = customerEmail;
      }
    }
  }

  setTimeout(pollAndProcess, 1500);
});


/* --- PayPal Integration --- */
var _paypalToken = null;

function renderPayPalButton() {
  var container = document.getElementById('paypal-button-container');
  if (!container) return;
  container.innerHTML = '';
  _paypalToken = null;

  if (typeof paypal_sdk === 'undefined') {
    container.innerHTML = '<p style="color:var(--color-text-muted);font-size:13px;text-align:center;">PayPal loading\u2026</p>';
    setTimeout(renderPayPalButton, 1000);
    return;
  }

  // Upload file and get token first
  var form = new FormData();
  form.append('file', selectedFile);
  form.append('plan', selectedPlan || 'basic');
  form.append('email', (document.getElementById('modalEmail') || {}).value || '');
  form.append('company', (document.getElementById('modalCompany') || {}).value || '');
  form.append('stage', (document.getElementById('modalStage') || {}).value || '');
  form.append('report_type', 'investor');

  fetch(API_BASE + '/api/paypal/prepare-upload', { method: 'POST', body: form })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      _paypalToken = data.token;
      _doRenderPayPalButtons(container);
    })
    .catch(function(err) {
      container.innerHTML = '<p style="color:#f44;font-size:13px;text-align:center;">PayPal unavailable</p>';
    });
}

function _doRenderPayPalButtons(container) {
  paypal_sdk.Buttons({
    style: { layout: 'horizontal', color: 'gold', shape: 'rect', label: 'paypal', height: 45, tagline: false },
    createOrder: function() {
      return fetch(API_BASE + '/api/paypal/create-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: _paypalToken, plan: selectedPlan || 'basic' }),
      }).then(function(r) { return r.json(); })
        .then(function(data) { return data.id; });
    },
    onApprove: function(data) {
      var btn = document.getElementById('submitBtn');
      if (btn) { btn.disabled = true; btn.textContent = 'Processing\u2026'; }
      var ppContainer = document.getElementById('paypal-button-container');
      if (ppContainer) ppContainer.style.display = 'none';

      return fetch(API_BASE + '/api/paypal/capture-order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orderID: data.orderID }),
      }).then(function(r) { return r.json(); })
        .then(function(result) {
          if (result.status === 'success') {
            _startPayPalPolling(result.token, result.plan, result.email);
          } else {
            showUploadError('Payment failed. Please try again.');
            if (btn) { btn.disabled = false; btn.textContent = 'Pay with Card'; }
            if (ppContainer) ppContainer.style.display = '';
          }
        });
    },
    onCancel: function() { /* user closed popup */ },
    onError: function(err) {
      showUploadError('PayPal error. Please try card payment.');
    },
  }).render(container);
}

function _startPayPalPolling(token, plan, email) {
  var s3 = document.getElementById('modalStep3');
  var successEl = document.getElementById('modalSuccess');
  var successMsg = document.getElementById('successMessage');
  var downloadLink = document.getElementById('successDownload');
  var progressEl = document.querySelector('.modal__progress');

  if (s3) s3.hidden = true;
  if (progressEl) progressEl.hidden = true;
  if (successEl) { successEl.hidden = false; successEl.style.display = ''; }

  var isReviewPlan = (plan === 'pro' || plan === 'expert');
  if (isReviewPlan) {
    if (successMsg) successMsg.innerHTML = '<strong>Payment confirmed!</strong><br><br>Your deck is being analyzed. Our expert investor team will review it personally.<br><br>You will receive the full report at <strong>' + (email || 'your email') + '</strong> within <strong>24 hours</strong>.';
    if (downloadLink) downloadLink.style.display = 'none';
    return;
  }

  if (successMsg) successMsg.textContent = 'Payment confirmed! Analyzing your deck\u2026';
  if (downloadLink) downloadLink.style.display = 'none';

  function poll() {
    fetch(API_BASE + '/api/paypal/analysis-status?token=' + encodeURIComponent(token))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.status === 'done') {
          var result = data.result || {};
          if (successMsg) successMsg.textContent = 'Analysis complete!';
          if (downloadLink && result.pdf_url) {
            downloadLink.href = API_BASE + result.pdf_url;
            downloadLink.style.display = 'inline-block';
          }
          if (email) {
            var reportEmail = document.getElementById('reportEmail');
            if (reportEmail) reportEmail.value = email;
            var emailSentEl = document.getElementById('emailSentMessage');
            if (emailSentEl) { emailSentEl.textContent = 'Report also sent to ' + email + ' \u2709'; emailSentEl.hidden = false; }
          }
        } else if (data.status === 'error') {
          if (successMsg) successMsg.textContent = 'Analysis failed: ' + (data.error || 'Unknown error');
        } else {
          setTimeout(poll, 4000);
        }
      })
      .catch(function() { setTimeout(poll, 5000); });
  }
  setTimeout(poll, 3000);
}
