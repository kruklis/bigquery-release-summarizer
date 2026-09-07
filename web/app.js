/**
 * BigQuery Release Intelligence - Client Application
 * Vanilla JS state management, API integration, interactive filters & Markdown rendering
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- App State ---
  const state = {
    days: 30,
    category: 'all',
    stage: 'all',
    search: '',
    mode: 'executive',
    offline: false,
    customQuery: '',
    items: [],
    stats: null,
    latestSummaryMarkdown: '',
    isSynthesizing: false
  };

  // --- DOM Elements ---
  const statTotalItems = document.getElementById('stat-total-items');
  const statTotalEntries = document.getElementById('stat-total-entries');
  const statGaCount = document.getElementById('stat-ga-count');
  const statPreviewCount = document.getElementById('stat-preview-count');
  const statChangesCount = document.getElementById('stat-changes-count');

  const releaseStream = document.getElementById('release-stream');
  const feedFilteredCount = document.getElementById('feed-filtered-count');
  const feedSearchInput = document.getElementById('feed-search-input');
  const categorySelect = document.getElementById('category-select');
  const refreshFeedBtn = document.getElementById('refresh-feed-btn');
  const spinIcon = refreshFeedBtn.querySelector('.spin-icon');

  const modePills = document.querySelectorAll('.mode-pill');
  const customQueryContainer = document.getElementById('custom-query-container');
  const customQueryInput = document.getElementById('custom-query-input');
  const suggestionChips = document.querySelectorAll('.suggestion-chip');
  const offlineModeToggle = document.getElementById('offline-mode-toggle');
  const generateSummaryBtn = document.getElementById('generate-summary-btn');
  const btnSynthesizeText = document.getElementById('btn-synthesize-text');

  const summaryContent = document.getElementById('summary-content');
  const summaryEngineName = document.getElementById('summary-engine-name');
  const summaryEngineBadge = document.getElementById('summary-engine-badge');
  const summaryTimeframeTag = document.getElementById('summary-timeframe-tag');
  const summaryCountTag = document.getElementById('summary-count-tag');
  const copySummaryBtn = document.getElementById('copy-summary-btn');
  const downloadSummaryBtn = document.getElementById('download-summary-btn');
  const toastContainer = document.getElementById('toast-container');

  // --- Helper: Toast Notifications ---
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓ ' : (type === 'error' ? '✕ ' : 'ℹ ');
    toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // --- Lightweight Markdown Parser ---
  function renderMarkdown(md) {
    if (!md) return '';
    let html = md;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');

    // Horizontal rules
    html = html.replace(/^---$/gim, '<hr>');

    // Blockquotes
    html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

    // Bold and italics
    html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Parse Markdown tables
    html = html.replace(/((?:\|[^\n]+\|\n?)+)/g, (match) => {
      const rows = match.trim().split('\n').map(r => r.trim()).filter(Boolean);
      if (rows.length < 2) return match;
      let tableHtml = '<table><thead>';
      
      // Header row
      const headerCols = rows[0].split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      tableHtml += '<tr>' + headerCols.map(c => `<th>${c}</th>`).join('') + '</tr></thead><tbody>';

      // Skip row 1 if it's separator e.g. |:---|:---|
      const dataRows = rows.slice(1).filter(r => !/^\|[-:|\s]+\|$/.test(r));
      for (const row of dataRows) {
        const cols = row.split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
        tableHtml += '<tr>' + cols.map(c => `<td>${c}</td>`).join('') + '</tr>';
      }
      tableHtml += '</tbody></table>';
      return tableHtml;
    });

    // Unordered lists
    html = html.replace(/^\s*[\*\-]\s+(.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');
    html = html.replace(/<\/ul>\s*<ul>/g, ''); // merge adjacent <ul>

    // Badges inside text [GA], [Preview], [Fixed]
    html = html.replace(/\[GA\]/g, '<span class="tag-badge stage-badge-ga">GA</span>');
    html = html.replace(/\[Preview\]/g, '<span class="tag-badge stage-badge-preview">Preview</span>');
    html = html.replace(/\[Fixed\]/g, '<span class="tag-badge cat-fixed">Fixed</span>');
    html = html.replace(/\[Change\]/g, '<span class="tag-badge cat-change">Change</span>');

    // Line breaks outside tags
    const paragraphs = html.split('\n\n').map(p => {
      p = p.trim();
      if (!p) return '';
      if (p.startsWith('<h') || p.startsWith('<table') || p.startsWith('<ul') || p.startsWith('<hr') || p.startsWith('<blockquote')) {
        return p;
      }
      return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    });

    return paragraphs.join('');
  }

  // --- Fetch KPI Stats ---
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.stats = data;

      statTotalItems.textContent = data.total_items || '0';
      statTotalEntries.textContent = `Across ${data.total_entries || 0} release cycles`;
      statGaCount.textContent = data.stages?.GA || '0';
      statPreviewCount.textContent = data.stages?.Preview || '0';

      const changeCount = (data.categories?.Change || 0) + (data.categories?.Fixed || 0) + (data.categories?.Deprecated || 0);
      statChangesCount.textContent = changeCount;
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }

  // --- Fetch Release Notes Feed ---
  async function loadNotes(forceRefresh = false) {
    releaseStream.setAttribute('aria-busy', 'true');
    releaseStream.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading BigQuery updates...</p>
      </div>
    `;

    try {
      const params = new URLSearchParams();
      if (state.days && state.days !== 'all') params.append('days', state.days);
      if (state.category && state.category !== 'all') params.append('category', state.category);
      if (state.stage && state.stage !== 'all') params.append('stage', state.stage);
      if (state.search) params.append('search', state.search);
      if (forceRefresh) params.append('refresh', 'true');

      const res = await fetch(`/api/notes?${params.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      state.items = data.items || [];
      renderReleaseStream(state.items);
      feedFilteredCount.textContent = `Showing ${state.items.length} update${state.items.length === 1 ? '' : 's'}`;

      // Update AI studio tags
      const timeframeText = state.days === 'all' ? 'All Time' : `Last ${state.days} Days`;
      summaryTimeframeTag.textContent = `Target: ${timeframeText}`;
      summaryCountTag.textContent = `${state.items.length} updates in scope`;
    } catch (err) {
      console.error('Failed to load release notes:', err);
      releaseStream.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <h3>Failed to Load Feed</h3>
          <p>${escapeHtml(err.message)}</p>
          <button class="btn btn-secondary btn-sm" onclick="location.reload()" style="margin-top:12px">Retry</button>
        </div>
      `;
    } finally {
      releaseStream.setAttribute('aria-busy', 'false');
    }
  }

  // --- Render Release Stream Cards ---
  function renderReleaseStream(items) {
    if (!items || items.length === 0) {
      releaseStream.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <h3>No Updates Found</h3>
          <p>No release notes match your current search and filter criteria. Try adjusting the timeframe or category filters.</p>
        </div>
      `;
      return;
    }

    const cardsHtml = items.map(item => {
      const catClass = `cat-${(item.category || 'general').toLowerCase()}`;
      const stageBadge = item.stage === 'GA' 
        ? `<span class="tag-badge stage-badge-ga">GA</span>`
        : (item.stage === 'Preview' ? `<span class="tag-badge stage-badge-preview">Preview</span>` : '');

      return `
        <article class="release-card" id="${escapeHtml(item.id)}">
          <div class="card-top">
            <div class="card-date-group">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              <span class="date-badge">${escapeHtml(item.date)}</span>
            </div>
            <div class="card-tags">
              <span class="tag-badge ${catClass}">${escapeHtml(item.category)}</span>
              ${stageBadge}
            </div>
          </div>
          <div class="card-body">
            ${item.html || escapeHtml(item.text)}
          </div>
          <div class="card-footer">
            <a href="${escapeHtml(item.entry_url)}" target="_blank" rel="noopener noreferrer" class="doc-link">
              <span>View in Official Changelog</span>
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3"/>
              </svg>
            </a>
          </div>
        </article>
      `;
    }).join('');

    releaseStream.innerHTML = cardsHtml;
  }

  // --- AI Synthesis Action ---
  async function generateSummary() {
    if (state.isSynthesizing) return;
    state.isSynthesizing = true;

    generateSummaryBtn.disabled = true;
    btnSynthesizeText.textContent = 'Synthesizing with AI...';
    generateSummaryBtn.classList.add('loading');

    summaryContent.innerHTML = `
      <div class="loading-state">
        <div class="spinner"></div>
        <p><strong>Analyzing ${state.items.length} BigQuery updates...</strong></p>
        <span style="font-size:0.8rem; color:var(--text-tertiary)">Generating structured synthesis via Google Cloud Antigravity CLI</span>
      </div>
    `;

    try {
      const payload = {
        days: state.days === 'all' ? null : state.days,
        category: state.category,
        stage: state.stage,
        search: state.search,
        mode: state.mode,
        custom_question: state.mode === 'custom' ? customQueryInput.value.trim() : null,
        offline: state.offline
      };

      const res = await fetch('/api/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      state.latestSummaryMarkdown = data.summary || '';
      
      // Update engine badge
      const engineName = data.engine === 'agy-ai' ? 'Google Antigravity AI' : 'Fast Analytical Engine';
      summaryEngineName.textContent = engineName;
      summaryEngineBadge.querySelector('.badge-dot').classList.add('active');

      // Render markdown
      const renderedHtml = renderMarkdown(state.latestSummaryMarkdown);
      summaryContent.innerHTML = renderedHtml;

      showToast(`Intelligence report generated (${engineName})!`, 'success');
    } catch (err) {
      console.error('Synthesis error:', err);
      summaryContent.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">❌</div>
          <h3>Synthesis Failed</h3>
          <p>${escapeHtml(err.message)}</p>
        </div>
      `;
      showToast('Synthesis failed. Check logs.', 'error');
    } finally {
      state.isSynthesizing = false;
      generateSummaryBtn.disabled = false;
      btnSynthesizeText.textContent = 'Generate AI Briefing';
      generateSummaryBtn.classList.remove('loading');
    }
  }

  // --- Copy Summary to Clipboard ---
  copySummaryBtn.addEventListener('click', async () => {
    if (!state.latestSummaryMarkdown) {
      showToast('No summary generated to copy!', 'error');
      return;
    }
    try {
      await navigator.clipboard.writeText(state.latestSummaryMarkdown);
      showToast('Markdown copied to clipboard!', 'success');
    } catch (err) {
      showToast('Could not copy to clipboard', 'error');
    }
  });

  // --- Download Summary as .md File ---
  downloadSummaryBtn.addEventListener('click', () => {
    if (!state.latestSummaryMarkdown) {
      showToast('No summary generated to export!', 'error');
      return;
    }
    const blob = new Blob([state.latestSummaryMarkdown], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const dateStamp = new Date().toISOString().split('T')[0];
    link.setAttribute('href', url);
    link.setAttribute('download', `bigquery_release_summary_${state.mode}_${dateStamp}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast('Report exported successfully!', 'success');
  });

  // --- Event Listeners ---

  // Mode Selection
  modePills.forEach(pill => {
    pill.addEventListener('click', () => {
      modePills.forEach(p => {
        p.classList.remove('active');
        p.setAttribute('aria-checked', 'false');
      });
      pill.classList.add('active');
      pill.setAttribute('aria-checked', 'true');

      state.mode = pill.dataset.mode;
      if (state.mode === 'custom') {
        customQueryContainer.classList.remove('hidden');
        customQueryInput.focus();
      } else {
        customQueryContainer.classList.add('hidden');
      }
    });
  });

  // Suggestion Chips
  suggestionChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const promptText = chip.dataset.prompt;
      customQueryInput.value = promptText;
      customQueryInput.focus();
    });
  });

  // Offline Mode Toggle
  offlineModeToggle.addEventListener('change', (e) => {
    state.offline = e.target.checked;
    const modeLabel = state.offline ? 'Offline Heuristic Engine' : 'Google Antigravity AI';
    showToast(`Engine mode: ${modeLabel}`);
  });

  // Generate Summary Click
  generateSummaryBtn.addEventListener('click', generateSummary);

  // Timeframe Filter Pills
  document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.days = pill.dataset.days === 'all' ? 'all' : parseInt(pill.dataset.days, 10);
      loadNotes();
    });
  });

  // Launch Stage Pills
  document.querySelectorAll('.stage-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.stage-pill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      state.stage = pill.dataset.stage;
      loadNotes();
    });
  });

  // Category Dropdown
  categorySelect.addEventListener('change', (e) => {
    state.category = e.target.value;
    loadNotes();
  });

  // Search Input with Debounce
  let searchTimer;
  feedSearchInput.addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = e.target.value.trim();
      loadNotes();
    }, 250);
  });

  // Refresh Feed Button
  refreshFeedBtn.addEventListener('click', async () => {
    spinIcon.classList.add('spinning');
    refreshFeedBtn.disabled = true;
    try {
      const res = await fetch('/api/refresh', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      showToast(`Refreshed! ${data.total_entries} release drops found.`, 'success');
      await Promise.all([loadStats(), loadNotes(true)]);
    } catch (err) {
      showToast(`Refresh failed: ${err.message}`, 'error');
    } finally {
      spinIcon.classList.remove('spinning');
      refreshFeedBtn.disabled = false;
    }
  });

  // Keyboard shortcut: '/' or 'Ctrl+K' to focus search
  window.addEventListener('keydown', (e) => {
    if ((e.key === '/' || (e.ctrlKey && e.key === 'k')) && document.activeElement !== feedSearchInput && document.activeElement !== customQueryInput) {
      e.preventDefault();
      feedSearchInput.focus();
    }
  });

  // --- Initial Ingestion & Load ---
  loadStats();
  loadNotes();
});
