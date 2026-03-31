// ============================================================
// CodyCross Answers — App Logic v4.0
// ============================================================
// Data Source: CodyCross Production API
// Format: All worlds with groups, clues, and answers
// ============================================================

const DATA_URL = 'data/answers.json';

// ============================================================
// DATA LOADING
// ============================================================

let appData = null;

async function loadData() {
  const res = await fetch(DATA_URL + '?t=' + Date.now());
  if (!res.ok) throw new Error('Failed to load answer data');
  return res.json();
}

// ============================================================
// HELPERS
// ============================================================

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function highlightMatch(text, query) {
  if (!query) return escapeHtml(text);
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escaped})`, 'gi');
  return escapeHtml(text).replace(regex, '<mark>$1</mark>');
}

// ============================================================
// WORLD TABS
// ============================================================

let activeWorldIndex = 0;
let searchQuery = '';

function renderWorldTabs(worlds, activeIndex) {
  const container = document.getElementById('world-tabs');
  if (!container) return;

  container.innerHTML = worlds.map((w, i) => `
    <button class="world-tab ${i === activeIndex ? 'active' : ''}"
            data-world="${i}"
            title="World ${w.world}: ${escapeHtml(w.worldName)} — ${w.stats.clues} clues">
      <span class="tab-num">${w.world}</span>
      <span class="tab-name">${escapeHtml(w.worldName)}</span>
    </button>
  `).join('');

  // Bind click events
  container.querySelectorAll('.world-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      activeWorldIndex = parseInt(tab.dataset.world);
      renderWorldTabs(worlds, activeWorldIndex);
      renderWorldContent(worlds, activeWorldIndex, searchQuery);
    });
  });
}

// ============================================================
// WORLD CONTENT
// ============================================================

function renderWorldContent(worlds, worldIdx, query) {
  const container = document.getElementById('world-content');
  if (!container || !worlds || !worlds[worldIdx]) return;

  const world = worlds[worldIdx];

  if (query) {
    renderSearchResults(container, worlds, query);
    return;
  }

  container.innerHTML = `
    <div class="world-header">
      <h3>World ${world.world}: ${escapeHtml(world.worldName)}</h3>
      <div class="world-stats">
        <span class="stat-badge">${world.stats.groups} groups</span>
        <span class="stat-badge">${world.stats.clues} clues</span>
      </div>
    </div>
    <div class="groups-list">
      ${world.groups.map((g, gi) => renderGroupCard(g, gi)).join('')}
    </div>
  `;

  // Bind accordion toggle
  container.querySelectorAll('.group-card').forEach(card => {
    card.querySelector('.group-header').addEventListener('click', () => {
      const puzzles = card.querySelector('.puzzles');
      const isShown = puzzles.style.display !== 'none';
      puzzles.style.display = isShown ? 'none' : 'block';
      card.classList.toggle('expanded', !isShown);
    });
  });
}

function renderGroupCard(group, index) {
  const puzzles = group.puzzles.map(p => `
    <div class="puzzle-row">
      <span class="clue">${escapeHtml(p.clue)}</span>
      <span class="answer">${escapeHtml(p.answer)}</span>
    </div>
  `).join('');

  const mainPuzzles = group.puzzles.filter(p => p.isMain);

  return `
    <div class="group-card">
      <div class="group-header">
        <span class="group-number">${group.groupNumber}</span>
        <div class="group-info">
          <h4>Group ${group.groupNumber}</h4>
          <span class="group-meta">${group.puzzles.length} clues</span>
        </div>
        <span class="expand-icon">&#x25BC;</span>
      </div>
      <div class="puzzles" style="display:none">
        ${puzzles}
      </div>
    </div>
  `;
}

// ============================================================
// SEARCH
// ============================================================

function renderSearchResults(container, worlds, query) {
  const q = query.toLowerCase();
  let results = [];
  let totalCount = 0;

  worlds.forEach(world => {
    world.groups.forEach(group => {
      group.puzzles.forEach(puzzle => {
        const clueMatch = puzzle.clue.toLowerCase().includes(q);
        const answerMatch = puzzle.answer.toLowerCase().includes(q);
        if (clueMatch || answerMatch) {
          results.push({
            worldNumber: world.world,
            worldName: world.worldName,
            groupNumber: group.groupNumber,
            clue: puzzle.clue,
            answer: puzzle.answer,
            clueMatch,
            answerMatch,
          });
          totalCount++;
        }
      });
    });
  });

  // Update search stats
  const statsEl = document.getElementById('search-stats');
  if (statsEl) {
    statsEl.textContent = totalCount > 0
      ? `${totalCount} result${totalCount !== 1 ? 's' : ''} found`
      : 'No results found';
  }

  if (results.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <p>No clues or answers matching "<strong>${escapeHtml(query)}</strong>"</p>
        <p class="hint">Try different keywords or check your spelling</p>
      </div>
    `;
    return;
  }

  // Limit display to 200 results for performance
  const displayResults = results.slice(0, 200);
  const truncated = results.length > 200;

  container.innerHTML = `
    <div class="search-results">
      ${displayResults.map(r => `
        <div class="search-result-item">
          <div class="result-meta">
            <span class="result-world">World ${r.worldNumber}: ${escapeHtml(r.worldName)}</span>
            <span class="result-group">Group ${r.groupNumber}</span>
          </div>
          <div class="result-row">
            <span class="clue">${highlightMatch(r.clue, query)}</span>
            <span class="answer ${r.answerMatch ? 'answer-match' : ''}">${highlightMatch(r.answer, query)}</span>
          </div>
        </div>
      `).join('')}
      ${truncated ? `<p class="truncated-notice">Showing 200 of ${results.length} results. Narrow your search for more specific results.</p>` : ''}
    </div>
  `;
}

// ============================================================
// WORLDS PAGE INIT
// ============================================================

async function initWorldsPage() {
  const container = document.getElementById('world-content');
  const titleEl = document.getElementById('page-title');
  const subtitleEl = document.getElementById('page-subtitle');
  const searchInput = document.getElementById('search-input');
  const updatedEl = document.getElementById('last-updated');
  const statsEl = document.getElementById('search-stats');

  try {
    const data = await loadData();
    appData = data;

    const worlds = data.answers || [];
    if (worlds.length === 0) {
      container.innerHTML = renderError('No puzzle data available yet. The site auto-updates daily.');
      return;
    }

    // Update header
    if (titleEl) titleEl.textContent = `${data.site.totalWorlds} Worlds — ${data.site.totalClues.toLocaleString()} Clues`;
    if (subtitleEl) subtitleEl.textContent = `Complete CodyCross puzzle database`;
    if (updatedEl) updatedEl.textContent = `Updated: ${data.site.lastUpdated}`;

    // Render tabs
    renderWorldTabs(worlds, 0);

    // Render first world (expanded first group by default)
    renderWorldContent(worlds, 0, '');

    // Expand first group
    setTimeout(() => {
      const firstCard = container.querySelector('.group-card');
      if (firstCard) {
        const puzzles = firstCard.querySelector('.puzzles');
        puzzles.style.display = 'block';
        firstCard.classList.add('expanded');
      }
    }, 50);

    // Search
    if (searchInput) {
      searchInput.addEventListener('input', debounce((e) => {
        searchQuery = e.target.value.trim();
        if (searchQuery) {
          renderWorldContent(worlds, activeWorldIndex, searchQuery);
        } else {
          statsEl.textContent = '';
          renderWorldContent(worlds, activeWorldIndex, '');
          // Re-expand first group if no search
          setTimeout(() => {
            const firstCard = container.querySelector('.group-card');
            if (firstCard) {
              const puzzles = firstCard.querySelector('.puzzles');
              puzzles.style.display = 'block';
              firstCard.classList.add('expanded');
            }
          }, 10);
        }
      }, 200));

      // Keyboard shortcut: / to focus search
      document.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== searchInput) {
          e.preventDefault();
          searchInput.focus();
        }
        if (e.key === 'Escape') {
          searchInput.value = '';
          searchQuery = '';
          statsEl.textContent = '';
          searchInput.blur();
          renderWorldContent(worlds, activeWorldIndex, '');
        }
      });
    }

  } catch (err) {
    container.innerHTML = renderError(`Error: ${err.message}`);
  }
}

// ============================================================
// ARCHIVE PAGE
// ============================================================

async function loadArchive() {
  const container = document.getElementById('archive-container');
  const updatedEl = document.getElementById('last-updated');
  const searchInput = document.getElementById('search-input');

  try {
    const data = await loadData();
    const worlds = data.answers || [];

    if (updatedEl && data.site) {
      updatedEl.textContent = `Updated: ${data.site.lastUpdated || 'Unknown'}`;
    }

    if (worlds.length === 0) {
      container.innerHTML = '<p class="empty-state">No data yet. The site auto-updates daily.</p>';
      return;
    }

    renderArchiveList(worlds, '');

    if (searchInput) {
      searchInput.addEventListener('input', debounce((e) => {
        renderArchiveList(worlds, e.target.value.trim().toLowerCase());
      }, 200));
    }
  } catch (err) {
    container.innerHTML = `<div class="error-box"><h3>Error</h3><p>${err.message}</p></div>`;
  }
}

function renderArchiveList(worlds, query) {
  const container = document.getElementById('archive-container');
  if (!container) return;

  const filtered = query
    ? worlds.filter(w =>
        w.worldName.toLowerCase().includes(query) ||
        w.groups.some(g =>
          g.puzzles.some(p =>
            p.clue.toLowerCase().includes(query) ||
            p.answer.toLowerCase().includes(query)
          )
        )
      )
    : worlds;

  if (filtered.length === 0) {
    container.innerHTML = '<p class="empty-state">No matching worlds found.</p>';
    return;
  }

  container.innerHTML = filtered.map(world => {
    const groupBadges = world.groups.map(g =>
      `<span class="archive-group-badge">Group ${g.groupNumber}: ${g.puzzles.length} clues</span>`
    ).join('');

    const expandedContent = world.groups.slice(0, 5).map(g => `
      <div class="mini-group">
        <h4>Group ${g.groupNumber}</h4>
        ${g.puzzles.slice(0, 8).map(p => `
          <div class="mini-puzzle">
            <span class="clue">${escapeHtml(p.clue)}</span>
            <span class="answer">${escapeHtml(p.answer)}</span>
          </div>
        `).join('')}
        ${g.puzzles.length > 8 ? `<p class="more-clues">+ ${g.puzzles.length - 8} more clues</p>` : ''}
      </div>
    `).join('');

    const hasMoreGroups = world.groups.length > 5;

    return `
      <div class="archive-item" onclick="toggleArchiveItem(this)">
        <div class="archive-meta">
          <span class="archive-world">World ${world.world}</span>
          <span class="archive-stats">${world.stats.groups} groups &middot; ${world.stats.clues} clues</span>
        </div>
        <div class="archive-theme">${escapeHtml(world.worldName)}</div>
        <div class="archive-preview">${groupBadges}</div>
        <div class="archive-expanded" style="display:none">${expandedContent}</div>
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
// SHARED RENDERING
// ============================================================

function renderError(msg) {
  return `
    <div class="error-box">
      <h3>&#x26A0;&#xFE0F; ${msg}</h3>
      <p>This site auto-updates daily via GitHub Actions.</p>
      <p>Check back in a few hours, or visit the <a href="archive.html">archive</a>.</p>
    </div>
  `;
}
