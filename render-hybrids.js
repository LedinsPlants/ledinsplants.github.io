// ===========================================================
// RENDER HYBRID CARDS
// ===========================================================
// This reads the `hybrids` list from hybrids-data.js and
// builds the card HTML automatically. Used by both index.html
// (limit = 3) and hybrids.html (limit = none). 
// ===========================================================

// genus (valfritt): visa bara hybrider av den växtgruppen, t.ex. 'kohleria'.
// 'other' visar alla som inte är kohleria, achimenes eller sinningia.
const MAIN_GENERA = ['kohleria', 'achimenes', 'sinningia'];

function renderHybridCards(containerId, limit, genus) {
  const container = document.getElementById(containerId);
  if (!container) return;

  // Sort newest first
  const wanted = !genus ? hybrids : hybrids.filter(h =>
    genus === 'other' ? !MAIN_GENERA.includes(h.genus) : h.genus === genus);
  const sorted = [...wanted].sort((a, b) => new Date(b.date) - new Date(a.date));
  const toShow = limit ? sorted.slice(0, limit) : sorted;

  if (toShow.length === 0) {
    container.innerHTML = '<p>No hybrids published here yet.</p>';
    return;
  }

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
