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

  function parseDecimal(value) {
    let normalized = String(value || '').trim().replace(/[^\d,.-]/g, '');
    if (normalized.includes(',') && normalized.includes('.')) {
      normalized = normalized.lastIndexOf(',') > normalized.lastIndexOf('.')
        ? normalized.replace(/\./g, '').replace(',', '.')
        : normalized.replace(/,/g, '');
    } else if (normalized.includes(',')) {
      normalized = normalized.replace(',', '.');
    }
    const number = Number(normalized);
    return Number.isFinite(number) ? number : 0;
  }

  function formatMoney(value) {
    return new Intl.NumberFormat('es-AR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value || 0);
  }

  function findRowFromInput(input) {
    return input?.closest?.('tr.form-row') || input?.closest?.('.dynamic-items') || input?.closest?.('tr');
  }

  function findQuantityInput(priceInput) {
    const name = priceInput.getAttribute('name') || '';
    const quantityName = name.replace(/-precio_unitario$/, '-cantidad');
    return document.querySelector(`[name="${quantityName}"]`);
  }

  function findDeleteInput(priceInput) {
    const name = priceInput.getAttribute('name') || '';
    const deleteName = name.replace(/-precio_unitario$/, '-DELETE');
    return document.querySelector(`[name="${deleteName}"]`);
  }

  function setRowSubtotal(priceInput) {
    const row = findRowFromInput(priceInput);
    const quantityInput = findQuantityInput(priceInput);
    const deleteInput = findDeleteInput(priceInput);
    const deleted = deleteInput?.checked;
    const subtotal = deleted
      ? 0
      : parseDecimal(priceInput.value) * Math.max(0, parseDecimal(quantityInput?.value || '1'));
    if (row) row.dataset.liveSubtotal = String(subtotal);

    const subtotalCell = row?.querySelector('.field-subtotal .readonly, .field-subtotal p, .field-subtotal');
    if (subtotalCell) subtotalCell.textContent = formatMoney(subtotal);
    return subtotal;
  }

  function ensureLiveTotalBox() {
    let box = document.getElementById('order-live-total-box');
    if (box) return box;

    const inlineGroup = document.querySelector('.inline-group');
    if (!inlineGroup) return null;

    box = document.createElement('div');
    box.id = 'order-live-total-box';
    box.style.margin = '12px 0';
    box.style.padding = '12px 14px';
    box.style.border = '1px solid #d0d7de';
    box.style.borderRadius = '8px';
    box.style.background = '#f6f8fa';
    box.style.fontWeight = '700';
    box.innerHTML = 'Total del pedido: <span id="order-live-total-value">0,00</span>';
    inlineGroup.appendChild(box);
    return box;
  }

  function recalcOrderTotal() {
    let total = 0;
    document.querySelectorAll('input[name$="-precio_unitario"]').forEach((priceInput) => {
      total += setRowSubtotal(priceInput);
    });
    const box = ensureLiveTotalBox();
    const value = box?.querySelector('#order-live-total-value');
    if (value) value.textContent = formatMoney(total);
  }

  function bindPriceInput(priceInput) {
    if (!priceInput || priceInput.dataset.priceManualBound === '1') return;
    priceInput.dataset.priceManualBound = '1';
    priceInput.addEventListener('input', function () {
      const lastAutofilled = lastAutofilledByInput.get(priceInput);
      if (String(priceInput.value || '') !== String(lastAutofilled || '')) {
        userEditedPriceInputs.add(priceInput);
      }
      recalcOrderTotal();
    });
    priceInput.addEventListener('change', function () {
      recalcOrderTotal();
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
      recalcOrderTotal();
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
    document.querySelectorAll('input[name$="-precio_unitario"]').forEach(bindPriceInput);
    document.querySelectorAll('input[name$="-cantidad"], input[name$="-DELETE"]').forEach((input) => {
      if (input.dataset.liveTotalBound === '1') return;
      input.dataset.liveTotalBound = '1';
      input.addEventListener('input', recalcOrderTotal);
      input.addEventListener('change', recalcOrderTotal);
    });
    recalcOrderTotal();
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
