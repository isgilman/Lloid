/* ── Shared streaming helper ─────────────────────────────────────────────── */

async function streamResponse(endpoint, messages, responseEl, extraData = {}) {
  let buffer = '';
  let fullText = '';

  const res = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, ...extraData }),
  });

  if (!res.ok) throw new Error(`Server error ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const event = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      for (const line of event.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.error) throw new Error(data.error);
          if (data.text) {
            fullText += data.text;
            responseEl.innerHTML = marked.parse(fullText);
            // Remove typing cursor if present
            const cursor = responseEl.querySelector('.typing-cursor');
            if (cursor) cursor.remove();
            // Scroll
            const msgs = responseEl.closest('.chat-messages');
            if (msgs) msgs.scrollTop = msgs.scrollHeight;
          }
        } catch (e) {
          if (e.message && !e.message.includes('JSON')) throw e;
        }
      }
    }
  }

  responseEl.classList.remove('streaming');
  return fullText;
}

/* ── Inventory: inline editing ───────────────────────────────────────────── */

function editRow(btn) {
  const row = btn.closest('.bottle-row');
  row.classList.add('editing');
  // Copy display values into inputs
  row.querySelectorAll('[name]').forEach(input => {
    const display = input.previousElementSibling;
    if (display && display.classList.contains('display-val')) {
      if (input.tagName === 'SELECT') {
        // value already set by template
      } else {
        input.value = display.textContent.trim();
      }
    }
  });
  row.querySelector('.edit-btns').style.display = 'flex';
}

function cancelEdit(btn) {
  const row = btn.closest('.bottle-row');
  row.classList.remove('editing');
  row.querySelector('.edit-btns').style.display = 'none';
}

async function saveRow(btn) {
  const row = btn.closest('.bottle-row');
  const idx = row.dataset.index;
  const form = new FormData();
  form.append('index', idx);
  row.querySelectorAll('.edit-input').forEach(input => {
    form.append(input.name, input.value);
  });

  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    const res = await fetch('/inventory/update', { method: 'POST', body: form });
    const data = await res.json();
    if (data.success) {
      // Update display values
      row.querySelectorAll('.edit-input').forEach(input => {
        const displayVal = row.querySelector(`td .display-val:has(+ [name="${input.name}"])`);
        // Simpler approach: find the td that contains this input
        const td = input.parentElement;
        const display = td.querySelector('.display-val');
        if (display && input.name === 'Use') {
          const val = input.value;
          display.innerHTML = val === 'Neat Only'
            ? '<span class="badge badge-dim">Neat Only</span>'
            : val === 'Premium Cocktail'
              ? '<span class="badge badge-premium">Premium</span>'
              : '<span class="badge badge-green">Cocktail</span>';
        } else if (display) {
          display.textContent = input.value;
        }
      });
      row.classList.remove('editing');
      row.querySelector('.edit-btns').style.display = 'none';
      showToast('Saved', 'success');
    }
  } catch (e) {
    showToast('Error saving changes', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save';
  }
}

/* ── Inventory: filter ───────────────────────────────────────────────────── */

function filterInventory() {
  const query = (document.getElementById('inv-search')?.value || '').toLowerCase();
  const cat   = (document.getElementById('inv-category')?.value || '').toLowerCase();
  const rows  = document.querySelectorAll('.bottle-row');
  let visible = 0;

  rows.forEach(row => {
    const name = (row.dataset.name || '').toLowerCase();
    const rowCat = (row.dataset.category || '').toLowerCase();
    const matchQuery = !query || name.includes(query);
    const matchCat   = !cat   || rowCat.toLowerCase() === cat;
    const show = matchQuery && matchCat;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  const empty = document.getElementById('inv-empty');
  if (empty) empty.style.display = visible === 0 ? 'block' : 'none';
}

/* ── Cocktails: filter & search ──────────────────────────────────────────── */

let makeableOnly = false;

function toggleMakeable() {
  makeableOnly = !makeableOnly;
  const btn = document.getElementById('cq-makeable-btn');
  if (btn) btn.classList.toggle('active', makeableOnly);
  filterCocktails();
}

function toggleFilterPanel() {
  const panel = document.getElementById('filter-panel');
  if (!panel) return;
  const open = panel.style.display === 'none' || panel.style.display === '';
  panel.style.display = open ? 'block' : 'none';
  document.getElementById('cq-filter-btn')?.classList.toggle('panel-open', open);
}

function clearFilters() {
  document.querySelectorAll('[name="cq-tag"],[name="cq-source"],[name="cq-creator"]')
    .forEach(el => { el.checked = false; });
  filterCocktails();
}

function _removeFilter(type, value) {
  const nameMap = { tag: 'cq-tag', source: 'cq-source', creator: 'cq-creator' };
  const cb = document.querySelector(`[name="${nameMap[type]}"][value="${CSS.escape(value)}"]`);
  if (cb) { cb.checked = false; filterCocktails(); }
}

function filterCocktails() {
  const query = (document.getElementById('cq-search')?.value || '').toLowerCase();

  const selectedTags     = [...document.querySelectorAll('[name="cq-tag"]:checked')].map(el => el.value);
  const selectedSources  = [...document.querySelectorAll('[name="cq-source"]:checked')].map(el => el.value);
  const selectedCreators = [...document.querySelectorAll('[name="cq-creator"]:checked')].map(el => el.value);

  const cards = document.querySelectorAll('.cocktail-card');
  let visible = 0;

  cards.forEach(card => {
    const name        = card.dataset.name || '';
    const cardTagsArr = (card.dataset.tags || '').split('|').filter(Boolean);
    const cardTagsStr = card.dataset.tags || '';   // for substring text search
    const cardSource  = card.dataset.source || '';
    const cardCreator = (card.dataset.creator || '').toLowerCase();
    const makeable    = card.dataset.makeable === 'true';
    const ings        = card.dataset.ingredients || '';

    // Text search (name + tags + ingredients + creator)
    const matchQuery = !query
      || name.includes(query)
      || cardTagsStr.includes(query)
      || ings.includes(query)
      || cardCreator.includes(query);

    // Tag filter: card must have ALL selected tags (AND within dimension).
    // 'tiki' also matches the legacy 'tropical' tag.
    const matchTags = selectedTags.length === 0 || selectedTags.every(st =>
      st === 'tiki'
        ? cardTagsArr.includes('tiki') || cardTagsArr.includes('tropical')
        : cardTagsArr.includes(st)
    );

    // Source filter: card must match ≥1 selected source (OR — a cocktail only
    // belongs to one source, so AND would always empty across sources).
    const matchSource = selectedSources.length === 0 || selectedSources.includes(cardSource);

    // Creator filter: OR — show cocktails by any of the selected creators.
    const matchCreator = selectedCreators.length === 0
      || selectedCreators.some(cr => cr.toLowerCase() === cardCreator);

    // Can Make toggle
    const matchMake = !makeableOnly || makeable;

    const show = matchQuery && matchTags && matchSource && matchCreator && matchMake;
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  // Count label
  const label = document.getElementById('cocktail-count-label');
  if (label) {
    const total = cards.length;
    label.textContent = visible === total
      ? `${total} recipe${total !== 1 ? 's' : ''}`
      : `${visible} of ${total} recipes`;
  }

  const empty = document.getElementById('cq-empty');
  if (empty) empty.style.display = visible === 0 ? 'block' : 'none';

  // Sync chip visual active state
  document.querySelectorAll('.filter-chip').forEach(chip => {
    const cb = chip.querySelector('input[type="checkbox"]');
    chip.classList.toggle('active', !!cb?.checked);
  });

  // Filter count badge
  const totalActive = selectedTags.length + selectedSources.length + selectedCreators.length;
  const badge = document.getElementById('cq-filter-count');
  if (badge) {
    badge.textContent = totalActive;
    badge.style.display = totalActive > 0 ? 'inline-flex' : 'none';
  }
  document.getElementById('cq-filter-btn')?.classList.toggle('active', totalActive > 0);

  // Active filter chips below the panel
  _renderActiveFilterChips(selectedTags, selectedSources, selectedCreators);
}

function _renderActiveFilterChips(tags, sources, creators) {
  const container = document.getElementById('active-filters');
  if (!container) return;
  container.innerHTML = '';

  const all = [
    ...tags.map(v     => ({ type: 'tag',     value: v, label: v })),
    ...sources.map(v  => ({ type: 'source',  value: v, label: v })),
    ...creators.map(v => ({ type: 'creator', value: v, label: v })),
  ];

  all.forEach(({ type, value, label }) => {
    const chip = document.createElement('span');
    chip.className = 'active-filter-chip';
    // escape value for safe inline onclick
    const safe = value.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    chip.innerHTML = `${label} <button aria-label="Remove filter" onclick="_removeFilter('${type}','${safe}')">&#215;</button>`;
    container.appendChild(chip);
  });
}

/* ── Toast ────────────────────────────────────────────────────────────────── */

function showToast(message, type = 'success') {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;

  Object.assign(toast.style, {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    padding: '12px 18px',
    borderRadius: '6px',
    fontSize: '13.5px',
    fontFamily: 'Inter, sans-serif',
    zIndex: '999',
    opacity: '0',
    transform: 'translateY(8px)',
    transition: 'opacity 0.2s ease, transform 0.2s ease',
    background: type === 'success' ? 'rgba(76,184,134,0.12)' : 'rgba(200,100,100,0.12)',
    color: type === 'success' ? '#4cb886' : '#c86464',
    border: `1px solid ${type === 'success' ? 'rgba(76,184,134,0.25)' : 'rgba(200,100,100,0.25)'}`,
  });

  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 200);
  }, 2500);
}

/* ── Auto-apply URL filter params ────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  // If on cocktails page, apply any URL filters
  if (document.getElementById('cq-search')) {
    const params = new URLSearchParams(window.location.search);
    if (params.get('filter') === 'makeable' && !makeableOnly) {
      toggleMakeable();
    }
    // Backward-compat: ?source=... pre-checks the matching source checkbox
    const srcParam = params.get('source');
    if (srcParam) {
      const cb = document.querySelector(`[name="cq-source"][value="${srcParam}"]`);
      if (cb) {
        cb.checked = true;
        const panel = document.getElementById('filter-panel');
        if (panel) panel.style.display = 'block';
        filterCocktails();
      }
    } else {
      // Run filter once to populate count label correctly on load
      filterCocktails();
    }
  }

  // Auto-dismiss flash messages
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s ease';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 3500);
  });
});
