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

function filterCocktails() {
  const query  = (document.getElementById('cq-search')?.value || '').toLowerCase();
  const source = (document.getElementById('cq-source')?.value || '');
  const cards  = document.querySelectorAll('.cocktail-card');
  let visible  = 0;

  cards.forEach(card => {
    const name       = (card.dataset.name || '');
    const cardSource = (card.dataset.source || '');
    const makeable   = card.dataset.makeable === 'true';
    const tags       = (card.dataset.tags || '');
    const ings       = (card.dataset.ingredients || '');

    const matchQuery  = !query
      || name.includes(query)
      || tags.includes(query)
      || ings.includes(query);
    const matchSource = !source || cardSource === source;
    const matchMake   = !makeableOnly || makeable;

    const show = matchQuery && matchSource && matchMake;
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  });

  const empty = document.getElementById('cq-empty');
  if (empty) empty.style.display = visible === 0 ? 'block' : 'none';

  const label = document.getElementById('cocktail-count-label');
  if (label) {
    const total = cards.length;
    label.textContent = visible === total
      ? `${total} recipe${total !== 1 ? 's' : ''}`
      : `${visible} of ${total} recipes`;
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
    if (params.get('filter') === 'makeable' && !makeableOnly) {
      toggleMakeable();
    }
    if (params.get('source')) {
      const sel = document.getElementById('cq-source');
      if (sel) { sel.value = params.get('source'); filterCocktails(); }
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
