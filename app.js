// ============================================================
// CodeCross Daily Answers — App Logic
// ============================================================
// Data Source: CodyCross API (codydev.fulano.com.br)
// Auto-updated via GitHub Actions
// ============================================================

const DATA_URL = 'data/answers.json';

// ============================================================
// DATA LOADING
// ============================================================

async function loadData() {
  const res = await fetch(DATA_URL + '?t=' + Date.now()); // Cache bust
  if (!res.ok) throw new Error('Failed to load answer data');
  return res.json();
}

// ============================================================
// DATE HELPERS
// ============================================================

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}

function getTodayStr() {
  return new Date().toISOString().split('T')[0];
}

function daysAgo(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const now = new Date();
  now.setHours(0,0,0,0);
  const diff = Math.floor((now - d) / (1000 * 60 * 60 * 24));
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  return `${diff} days ago`;
}

// ============================================================
// RENDERING
// ============================================================

function renderGroupCard(group, index) {
  const puzzles = group.puzzles.map(p => `
    <div class="puzzle-row">
      <span class="clue">${escapeHtml(p.clue)}</span>
      <span class="answer">${escapeHtml(p.answer)}</span>
    </div>
  `).join('');

  return `
    <div class="group-card">
      <div class="group-header">
        <span class="group-number">${index + 1}</span>
        <h3>${escapeHtml(group.name)}</h3>
      </div>
      <div class="puzzles">${puzzles}</div>
    </div>
  `;
}

function renderLoading() {
  return `
    <div class="loading-spinner">
      <div class="spinner"></div>
      <p>Loading puzzle answers...</p>
    </div>
  `;
}

function renderError(msg) {
  return `
    <div class="error-box">
      <h3>⚠️ ${msg}</h3>
      <p>This usually means the data hasn't been fetched yet. The site auto-updates daily via GitHub Actions.</p>
      <p>Check back in a few hours, or visit the <a href="archive.html">archive</a> for past answers.</p>
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ============================================================
// TODAY'S PAGE
// ============================================================

async function loadToday() {
  const container = document.getElementById('answers-container');
  const dateEl = document.getElementById('today-date');
  const themeEl = document.getElementById('today-theme');

  try {
    const data = await loadData();
    const today = getTodayStr();

    // Find today's entry (or most recent)
    let entry = data.answers.find(a => a.date === today);
    if (!entry && data.answers.length > 0) {
      entry = data.answers[0]; // Use most recent
    }

    if (!entry) {
      dateEl.textContent = 'No data yet';
      themeEl.textContent = 'No answers available';
      container.innerHTML = renderError('No puzzle data available yet');
      return;
    }

    dateEl.textContent = formatDate(entry.date);
    if (entry.date !== today) {
      dateEl.textContent += ` (${daysAgo(entry.date)})`;
    }
    themeEl.textContent = entry.theme;
    document.title = `${entry.theme} — CodeCross Daily Answers`;

    if (!entry.groups || entry.groups.length === 0) {
      container.innerHTML = renderError('Puzzle data is encrypted — decryption key needed');
      return;
    }

    container.innerHTML = entry.groups.map((g, i) => renderGroupCard(g, i)).join('');
  } catch (err) {
    dateEl.textContent = 'Error';
    themeEl.textContent = 'Could not load data';
    container.innerHTML = renderError(`Error: ${err.message}`);
  }
}

// ============================================================
// ARCHIVE PAGE
// ============================================================

let allAnswers = [];

async function loadArchive() {
  const container = document.getElementById('archive-container');
  const updatedEl = document.getElementById('last-updated');
  const searchInput = document.getElementById('search-input');

  try {
    const data = await loadData();
    allAnswers = data.answers || [];

    if (updatedEl && data.site) {
      updatedEl.textContent = `Last updated: ${data.site.lastUpdated || 'Unknown'}`;
    }

    if (allAnswers.length === 0) {
      container.innerHTML = '<p class="empty-state">No archive entries yet. The site auto-updates daily.</p>';
      return;
    }

    renderArchiveList(allAnswers);

    // Search functionality
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const filtered = allAnswers.filter(a =>
          a.date.includes(query) ||
          (a.theme && a.theme.toLowerCase().includes(query))
        );
        renderArchiveList(filtered);
      });
    }
  } catch (err) {
    container.innerHTML = `<p class="error-box">Error loading archive: ${err.message}</p>`;
  }
}

function renderArchiveList(answers) {
  const container = document.getElementById('archive-container');

  container.innerHTML = answers.map(day => {
    const hasGroups = day.groups && day.groups.length > 0;
    const preview = hasGroups
      ? day.groups.map(g =>
          `<span class="archive-group-badge">${escapeHtml(g.name)}: ${g.puzzles.length} clues</span>`
        ).join('')
      : '<span class="archive-group-badge encrypted">🔒 Encrypted — needs decryption key</span>';

    const expanded = hasGroups ? day.groups.map((g, i) => `
      <div class="mini-group">
        <h4>${escapeHtml(g.name)}</h4>
        ${g.puzzles.map(p => `
          <div class="mini-puzzle">
            <span class="clue">${escapeHtml(p.clue)}</span>
            <span class="answer">${escapeHtml(p.answer)}</span>
          </div>
        `).join('')}
      </div>
    `).join('') : '<p style="padding:16px;color:var(--text-muted)">Encrypted data — decryption key extraction in progress</p>';

    return `
      <div class="archive-item" onclick="toggleArchiveItem(this)">
        <div class="archive-meta">
          <span class="archive-date">${formatDate(day.date)} — ${daysAgo(day.date)}</span>
          ${day.world ? `<span class="archive-world">World ${day.world}</span>` : ''}
        </div>
        <div class="archive-theme">${escapeHtml(day.theme)}</div>
        <div class="archive-preview">${preview}</div>
        <div class="archive-expanded" style="display:none">${expanded}</div>
      </div>
    `;
  }).join('');
}

function toggleArchiveItem(el) {
  const expanded = el.querySelector('.archive-expanded');
  const isShown = expanded.style.display !== 'none';
  expanded.style.display = isShown ? 'none' : 'grid';

  // Close others
  document.querySelectorAll('.archive-item').forEach(item => {
    if (item !== el) {
      item.querySelector('.archive-expanded').style.display = 'none';
    }
  });
}

// ============================================================
// AUTO-INIT
// ============================================================

if (document.getElementById('answers-container')) {
  document.addEventListener('DOMContentLoaded', loadToday);
}
