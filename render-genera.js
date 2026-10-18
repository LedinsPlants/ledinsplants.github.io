// Fyller genera.html med kort för arter och andra odlares hybrider under varje släkte.
// Samma kortdesign som på My Hybrids-sidorna. Data kommer från plant-lists-data.js
// (skapas av build_hybrids.py). Tomma grupper visas inte.
(function () {
  function cards(items) {
    return '<div class="hybrid-grid">' + items.map(function (p) {
      return '<a class="hybrid-card" href="/' + p.page + '">' +
        (p.image ? '<img src="' + p.image + '" alt="">' : '<div class="card-noimg"></div>') +
        '<div class="card-body"><h3>' + p.name + '</h3>' +
        (p.sub ? '<div class="meta">' + p.subLabel + ': ' + p.sub + '</div>' : '') +
        (p.summary ? '<p>' + p.summary + '</p>' : '') +
        '<span class="read-more">Read more →</span></div></a>';
    }).join('') + '</div>';
  }
  var GROUPS = [
    { list: 'speciesList', title: 'Species',
      intro: 'Here I collect the species I grow, with photos and details about each plant.' },
    { list: 'otherHybridsList', title: 'Hybrids by other growers',
      intro: 'Here I collect hybrids and cultivars from other hybridizers that I grow, with photos and details about each plant.' }
  ];
  document.querySelectorAll('.plant-lists').forEach(function (box) {
    var genus = box.getAttribute('data-genus');
    box.innerHTML = GROUPS.map(function (g) {
      var all = (g.list === 'speciesList' && typeof speciesList !== 'undefined') ? speciesList :
                (g.list === 'otherHybridsList' && typeof otherHybridsList !== 'undefined') ? otherHybridsList : [];
      var items = all.filter(function (p) { return p.genus === genus; });
      return items.length ? '<h3>' + g.title + '</h3><p>' + g.intro + '</p>' + cards(items) : '';
    }).join('');
  });
})();
