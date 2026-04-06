(function () {
  function getPriceUrl(productId) {
    const path = window.location.pathname;
    const base = path
      .replace(/add\/?$/, '')
      .replace(/\d+\/change\/?$/, '');
    return `${base}product-price/${productId}/`;
  }

  function findPriceInput(select) {
    const name = select.getAttribute('name') || '';
    const priceName = name.replace(/-product$/, '-precio_unitario');
    return document.querySelector(`[name="${priceName}"]`);
  }

  async function updatePrice(select) {
    const productId = select.value;
    const priceInput = findPriceInput(select);
    if (!productId || !priceInput) return;

    try {
      const response = await fetch(getPriceUrl(productId), {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return;
      const data = await response.json();
      if (data.price !== undefined && data.price !== null) {
        priceInput.value = data.price;
        priceInput.dispatchEvent(new Event('change', { bubbles: true }));
      }
    } catch (_) {
      // Si falla la consulta, el admin mantiene el precio editable manualmente.
    }
  }

  function bindSelect(select) {
    if (!select || select.dataset.priceAutofillBound === '1') return;
    if (!/-product$/.test(select.getAttribute('name') || '')) return;
    select.dataset.priceAutofillBound = '1';
    select.addEventListener('change', () => updatePrice(select));
  }

  function bindAll() {
    document.querySelectorAll('select[name$="-product"]').forEach(bindSelect);
  }

  document.addEventListener('DOMContentLoaded', bindAll);
  document.addEventListener('formset:added', bindAll);

  if (window.django && window.django.jQuery) {
    window.django.jQuery(document).on('select2:select', 'select[name$="-product"]', function () {
      updatePrice(this);
    });
  }
})();
