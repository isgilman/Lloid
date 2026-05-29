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

/* ── Cocktails: sort ─────────────────────────────────────────────────────── */

let _savedOrder = null;   // null = currently in random/default order

function toggleSort() {
  const grid = document.getElementById('cocktail-grid');
  if (!grid) return;
  const btn = document.getElementById('cq-sort-btn');

  if (_savedOrder === null) {
    // Switch to A→Z: save current DOM order, then sort all cards by name
    const cards = [...grid.querySelectorAll('.cocktail-card')];
    _savedOrder = cards;
    cards
      .slice()
      .sort((a, b) => (a.dataset.name || '').localeCompare(b.dataset.name || ''))
      .forEach(c => grid.appendChild(c));
    if (btn) { btn.classList.add('active'); btn.textContent = 'A → Z ✓'; }
  } else {
    // Restore random order
    _savedOrder.forEach(c => grid.appendChild(c));
    _savedOrder = null;
    if (btn) { btn.classList.remove('active'); btn.textContent = 'A → Z'; }
  }
}

/* ── Cocktails: filter & search ──────────────────────────────────────────── */

let makeableOnly = false;
let triedOnly = false;
let favoritedOnly = false;
let _spiritFilter = null;  // array of keywords when ?spirit= param is active

// Multi-keyword lookup for ?spirit= URL param
const _SPIRIT_KEYWORDS = {
  rum:      ['rum', 'rhum'],
  whiskey:  ['whiskey', 'whisky', 'bourbon', 'rye', 'scotch'],
  tequila:  ['tequila', 'mezcal', 'sotol'],
  gin:      ['gin'],
  vodka:    ['vodka'],
  cognac:   ['cognac', 'brandy', 'calvados', 'armagnac'],
  amaro:    ['amaro', 'campari', 'aperol', 'cynar', 'fernet'],
  vermouth: ['vermouth', 'sherry', 'port'],
};

function toggleMakeable() {
  makeableOnly = !makeableOnly;
  const btn = document.getElementById('cq-makeable-btn');
  if (btn) btn.classList.toggle('active', makeableOnly);
  filterCocktails();
}

function toggleTriedFilter() {
  triedOnly = !triedOnly;
  const btn = document.getElementById('cq-tried-btn');
  if (btn) btn.classList.toggle('active', triedOnly);
  filterCocktails();
}

function toggleFavoritedFilter() {
  favoritedOnly = !favoritedOnly;
  const btn = document.getElementById('cq-fav-btn');
  if (btn) btn.classList.toggle('active', favoritedOnly);
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
  _spiritFilter = null;
  const container = document.getElementById('active-filters');
  if (container) container.innerHTML = '';
  filterCocktails();
}

function _clearSpiritFilter() {
  _spiritFilter = null;
  // Remove the spirit chip and re-render active chips
  const container = document.getElementById('active-filters');
  if (container) container.innerHTML = '';
  filterCocktails();
}

function _removeFilter(type, value) {
  const nameMap = { tag: 'cq-tag', source: 'cq-source', creator: 'cq-creator' };
  const cb = document.querySelector(`[name="${nameMap[type]}"][value="${CSS.escape(value)}"]`);
  if (cb) { cb.checked = false; filterCocktails(); }
}

/** Normalize a search string: lowercase, trim whitespace, collapse
 *  punctuation/apostrophes to spaces so that e.g. "ti punch" matches
 *  "Ti' Punch" and a trailing space in the query is ignored. */
function normSearch(s) {
  return (s || '').toLowerCase().trim().replace(/['''`\-\.]/g, ' ').replace(/\s+/g, ' ').trim();
}

function filterCocktails() {
  const query = normSearch(document.getElementById('cq-search')?.value || '');

  const selectedTags     = [...document.querySelectorAll('[name="cq-tag"]:checked')].map(el => el.value);
  const selectedSources  = [...document.querySelectorAll('[name="cq-source"]:checked')].map(el => el.value);
  const selectedCreators = [...document.querySelectorAll('[name="cq-creator"]:checked')].map(el => el.value);

  const cards = document.querySelectorAll('.cocktail-card');
  let visible = 0;

  cards.forEach(card => {
    const name        = normSearch(card.dataset.name || '');
    const cardTagsArr = (card.dataset.tags || '').split('|').filter(Boolean);
    const cardTagsStr = normSearch(card.dataset.tags || '');
    const cardSource  = card.dataset.source || '';
    const cardCreator = normSearch(card.dataset.creator || '');
    const makeable    = card.dataset.makeable === 'true';
    const tried      = card.dataset.tried === 'true';
    const favorited  = card.dataset.favorited === 'true';
    const ings        = normSearch(card.dataset.ingredients || '');

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
    const matchTried     = !triedOnly     || tried;
    const matchFavorited = !favoritedOnly || favorited;

    // Spirit filter (from ?spirit= URL param)
    const matchSpirit = !_spiritFilter ||
      _spiritFilter.some(kw => ings.includes(kw) || name.includes(kw));

    const show = matchQuery && matchTags && matchSource && matchCreator && matchMake && matchTried && matchFavorited && matchSpirit;
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


/* ── Cocktail feedback bar ───────────────────────────────────────────────── */

async function _postFeedback(payload) {
  const bar = document.getElementById('feedback-bar');
  if (!bar) return null;
  const id = bar.dataset.cocktailId;
  try {
    const res = await fetch('/cocktails/' + id + '/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return await res.json();
  } catch (e) {
    showToast('Error saving feedback', 'error');
    return null;
  }
}

function _applyFeedbackState(fb) {
  if (!fb) return;
  const bar = document.getElementById('feedback-bar');
  if (!bar) return;

  bar.dataset.tried     = fb.tried;
  bar.dataset.rating    = fb.rating || '';
  bar.dataset.favorited = fb.favorited;

  const triedBtn = document.getElementById('fb-tried-btn');
  if (triedBtn) {
    triedBtn.classList.toggle('active', fb.tried);
    triedBtn.textContent = fb.tried ? '✓ Tried' : 'Tried it?';
  }

  const ratingGroup = document.getElementById('fb-rating-group');
  if (ratingGroup) ratingGroup.classList.toggle('visible', fb.tried);

  const likeBtn    = document.getElementById('fb-like-btn');
  const dislikeBtn = document.getElementById('fb-dislike-btn');
  const needsBtn   = document.getElementById('fb-needs-btn');
  if (likeBtn)    likeBtn.classList.toggle('active-like',    fb.rating === 'like');
  if (dislikeBtn) dislikeBtn.classList.toggle('active-dislike', fb.rating === 'dislike');
  if (needsBtn)   needsBtn.classList.toggle('active-needs',  fb.rating === 'needs-work');

  const favBtn = document.getElementById('fb-fav-btn');
  if (favBtn) {
    favBtn.classList.toggle('active', fb.favorited);
    favBtn.textContent = fb.favorited ? '♥' : '♡';
  }
}

async function toggleTried() {
  const bar = document.getElementById('feedback-bar');
  if (!bar) return;
  const current = bar.dataset.tried === 'true';
  const fb = await _postFeedback({ tried: !current });
  if (fb) {
    _applyFeedbackState(fb);
    showToast(fb.tried ? 'Marked as tried!' : 'Removed from tried', 'success');
  }
}

async function setRating(rating) {
  const bar = document.getElementById('feedback-bar');
  if (!bar) return;
  const current = bar.dataset.rating;
  const newRating = current === rating ? '' : rating;
  const fb = await _postFeedback({ rating: newRating });
  if (fb) _applyFeedbackState(fb);
}

async function toggleFavorite() {
  const bar = document.getElementById('feedback-bar');
  if (!bar) return;
  const current = bar.dataset.favorited === 'true';
  const fb = await _postFeedback({ favorited: !current });
  if (fb) {
    _applyFeedbackState(fb);
    showToast(fb.favorited ? 'Added to favorites!' : 'Removed from favorites', 'success');
  }
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

    // ?filter=makeable
    if (params.get('filter') === 'makeable' && !makeableOnly) toggleMakeable();

    // ?spirit=rum — multi-keyword OR filter from home page stat links
    const spiritParam = params.get('spirit');
    if (spiritParam && _SPIRIT_KEYWORDS[spiritParam]) {
      _spiritFilter = _SPIRIT_KEYWORDS[spiritParam];
      // Show a dismissible active-filter chip for the spirit
      const container = document.getElementById('active-filters');
      if (container) {
        const chip = document.createElement('span');
        chip.className = 'active-filter-chip';
        const label = spiritParam.charAt(0).toUpperCase() + spiritParam.slice(1);
        chip.innerHTML = label + ' <button aria-label="Remove filter" onclick="_clearSpiritFilter()">&#215;</button>';
        container.appendChild(chip);
      }
    }

    // ?source=... pre-checks the matching source checkbox
    const srcParam = params.get('source');
    if (srcParam) {
      const cb = document.querySelector(`[name="cq-source"][value="${srcParam}"]`);
      if (cb) {
        cb.checked = true;
        const panel = document.getElementById('filter-panel');
        if (panel) panel.style.display = 'block';
      }
    }

    filterCocktails();
  }

  // If on inventory page, apply ?category= and/or ?search= URL params
  if (document.getElementById('bottle-grid')) {
    const params = new URLSearchParams(window.location.search);
    const catParam    = params.get('category');
    const searchParam = params.get('search');
    if (catParam) {
      const sel = document.getElementById('inv-category');
      if (sel) { sel.value = catParam; }
    }
    if (searchParam) {
      const inp = document.getElementById('inv-search');
      if (inp) { inp.value = searchParam; }
    }
    if ((catParam || searchParam) && typeof filterBottles === 'function') filterBottles();
  }

  // Wire up feedback rating buttons (avoids inline onclick with string args)
  document.querySelectorAll('.feedback-rating-btn').forEach(function(btn) {
    btn.addEventListener('click', function() { setRating(btn.dataset.rating); });
  });

  // Auto-dismiss flash messages
  document.querySelectorAll('.flash').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s ease';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 3500);
  });
});
