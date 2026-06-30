// ===========================================================
// RENDER HYBRID CARDS
// ===========================================================
// This reads the `hybrids` list from hybrids-data.js and
// builds the card HTML automatically. Used by both index.html
// (limit = 3) and hybrids.html (limit = none).
// ===========================================================

function renderHybridCards(containerId, limit) {
  const container = document.getElementById(containerId);
  if (!container) return;

  // Sort newest first
  const sorted = [...hybrids].sort((a, b) => new Date(b.date) - new Date(a.date));
  const toShow = limit ? sorted.slice(0, limit) : sorted;

  container.innerHTML = toShow.map(h => `
    <a class="hybrid-card" href="${h.page}">
      <img src="${h.image}" alt="${h.name}">
      <div class="card-body">
        <h3>${h.name}</h3>
        <div class="meta">Published ${h.dateDisplay}</div>
        <p>${h.summary}</p>
        <span class="read-more">Read more →</span>
      </div>
    </a>
  `).join('');
}
