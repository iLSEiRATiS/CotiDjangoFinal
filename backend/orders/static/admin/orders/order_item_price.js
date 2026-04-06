(function () {
  const lastAutofilledByInput = new WeakMap();

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

  function shouldAutofillPrice(priceInput) {
    const current = String(priceInput.value || '').trim();
    if (!current) return true;
    if (current === '0' || current === '0.0' || current === '0.00') return true;
    return lastAutofilledByInput.get(priceInput) === current;
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
        if (!shouldAutofillPrice(priceInput)) return;
        const nextPrice = String(data.price);
        priceInput.value = nextPrice;
        lastAutofilledByInput.set(priceInput, nextPrice);
        priceInput.dispatchEvent(new Event('change', { bubbles: true }));
        priceInput.dispatchEvent(new Event('input', { bubbles: true }));
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
    select.addEventListener('input', () => updatePrice(select));
  }

  function bindAll() {
    document.querySelectorAll('select[name$="-product"]').forEach(bindSelect);
  }

  document.addEventListener('DOMContentLoaded', bindAll);
  document.addEventListener('formset:added', bindAll);
  document.addEventListener('change', function (event) {
    const select = event.target;
    if (select && select.matches && select.matches('select[name$="-product"]')) {
      bindSelect(select);
      updatePrice(select);
    }
  });

  if (window.django && window.django.jQuery) {
    window.django.jQuery(document).on('select2:select select2:close', 'select[name$="-product"]', function () {
      bindSelect(this);
      updatePrice(this);
    });
  }
})();
