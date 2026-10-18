// Fyller listorna "Species" och "Hybrids by other growers" under varje släkte
// på genera.html. Data kommer från plant-lists-data.js (skapas av build_hybrids.py).
(function () {
  function section(title, items) {
    if (!items.length) return '';
    var html = '<h3>' + title + '</h3><ul class="plant-list">';
    items.forEach(function (p) {
      html += '<li><a href="/' + p.page + '">' +
        (p.image ? '<img src="' + p.image + '" alt="">' : '<span class="plant-list-noimg"></span>') +
        '<span class="plant-list-name">' + p.name +
        (p.sub ? ' <small>' + p.sub + '</small>' : '') + '</span></a></li>';
    });
    return html + '</ul>';
  }
  document.querySelectorAll('.plant-lists').forEach(function (box) {
    var genus = box.getAttribute('data-genus');
    var pick = function (list) {
      return (typeof list === 'undefined' ? [] : list).filter(function (p) { return p.genus === genus; });
    };
    box.innerHTML =
      section('Species', pick(typeof speciesList === 'undefined' ? undefined : speciesList)) +
      section('Hybrids by other growers', pick(typeof otherHybridsList === 'undefined' ? undefined : otherHybridsList));
  });
})();
