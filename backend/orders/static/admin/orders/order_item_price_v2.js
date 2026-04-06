(function () {
  const lastAutofilledByInput = new WeakMap();
  const lastSeenProductBySelect = new WeakMap();
  const userEditedPriceInputs = new WeakSet();

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

  function bindPriceInput(priceInput) {
    if (!priceInput || priceInput.dataset.priceManualBound === '1') return;
    priceInput.dataset.priceManualBound = '1';
    priceInput.addEventListener('input', function () {
      const lastAutofilled = lastAutofilledByInput.get(priceInput);
      if (String(priceInput.value || '') !== String(lastAutofilled || '')) {
        userEditedPriceInputs.add(priceInput);
      }
    });
  }

  function shouldAutofillPrice(priceInput, productChanged) {
    if (productChanged) return true;
    const current = String(priceInput.value || '').trim();
    if (!current || current === '0' || current === '0.0' || current === '0.00') return true;
    return !userEditedPriceInputs.has(priceInput);
  }

  async function updatePrice(select, forcedProductId) {
    const productId = String(forcedProductId || select.value || '').trim();
    const priceInput = findPriceInput(select);
    if (!productId || !priceInput) return;

    bindPriceInput(priceInput);

    const previousProductId = lastSeenProductBySelect.get(select);
    const productChanged = previousProductId !== productId;

    try {
      const response = await fetch(getPriceUrl(productId), {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return;
      const data = await response.json();
      if (data.price === undefined || data.price === null) return;
      if (!shouldAutofillPrice(priceInput, productChanged)) return;

      const nextPrice = String(data.price);
      priceInput.value = nextPrice;
      lastAutofilledByInput.set(priceInput, nextPrice);
      lastSeenProductBySelect.set(select, productId);
      userEditedPriceInputs.delete(priceInput);
      priceInput.dispatchEvent(new Event('input', { bubbles: true }));
      priceInput.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (_) {
      // Si falla la consulta, el admin mantiene el precio editable manualmente.
    }
  }

  function syncSelect(select) {
    if (!select || !/-product$/.test(select.getAttribute('name') || '')) return;
    const productId = String(select.value || '').trim();
    if (!productId) return;
    if (lastSeenProductBySelect.get(select) !== productId) {
      updatePrice(select, productId);
    }
  }

  function bindSelect(select) {
    if (!select || !/-product$/.test(select.getAttribute('name') || '')) return;
    if (select.dataset.priceAutofillBound !== '1') {
      select.dataset.priceAutofillBound = '1';
      select.addEventListener('change', () => updatePrice(select));
      select.addEventListener('input', () => updatePrice(select));
    }
    const priceInput = findPriceInput(select);
    bindPriceInput(priceInput);
    syncSelect(select);
  }

  function bindAll() {
    document.querySelectorAll('select[name$="-product"]').forEach(bindSelect);
  }

  document.addEventListener('DOMContentLoaded', bindAll);
  document.addEventListener('formset:added', bindAll);
  document.addEventListener('change', function (event) {
    if (event.target?.matches?.('select[name$="-product"]')) {
      bindSelect(event.target);
      updatePrice(event.target);
    }
  });

  if (window.django && window.django.jQuery) {
    window.django.jQuery(document).on('select2:select', 'select[name$="-product"]', function (event) {
      bindSelect(this);
      const productId = event?.params?.data?.id || this.value;
      window.setTimeout(() => updatePrice(this, productId), 0);
    });
    window.django.jQuery(document).on('select2:close change', 'select[name$="-product"]', function () {
      bindSelect(this);
      window.setTimeout(() => updatePrice(this), 0);
    });
  }

  window.setInterval(bindAll, 500);
})();
