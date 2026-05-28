(function () {
  const lastAutofilledByInput = new WeakMap();
  const lastSeenProductBySelect = new WeakMap();
  const lastSeenUserBySelect = new WeakMap();
  const userEditedPriceInputs = new WeakSet();
  let shippingAutofilledValue = '';
  let shippingManuallyEdited = false;

  function getPriceUrl(productId) {
    const path = window.location.pathname;
    const base = path
      .replace(/add\/?$/, '')
      .replace(/\d+\/change\/?$/, '');
    return `${base}product-price/${productId}/`;
  }

  function getUserShippingUrl(userId) {
    const path = window.location.pathname;
    const base = path
      .replace(/add\/?$/, '')
      .replace(/\d+\/change\/?$/, '');
    return `${base}user-shipping/${userId}/`;
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
    if (row && deleteInput) row.style.display = deleted ? 'none' : '';
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
    box.style.border = '2px solid #1f7a4d';
    box.style.borderRadius = '8px';
    box.style.background = '#ffffff';
    box.style.color = '#102a1f';
    box.style.fontWeight = '700';
    box.style.boxShadow = '0 2px 8px rgba(16, 42, 31, 0.08)';
    box.innerHTML = 'Total del pedido: <span id="order-live-total-value">0,00</span>';
    inlineGroup.appendChild(box);
    return box;
  }

  function recalcOrderTotal() {
    let total = 0;
    document.querySelectorAll('input[name$="-precio_unitario"]').forEach((priceInput) => {
      total += setRowSubtotal(priceInput);
    });
    syncDeletedItemRows();
    total += parseDecimal(document.querySelector('[name="envio"]')?.value || '0');
    const box = ensureLiveTotalBox();
    const value = box?.querySelector('#order-live-total-value');
    if (value) value.textContent = formatMoney(total);
  }

  function syncDeletedItemRows() {
    document.querySelectorAll('input[name$="-DELETE"]').forEach((deleteInput) => {
      const row = findRowFromInput(deleteInput);
      if (row) row.style.display = deleteInput.checked ? 'none' : '';
    });
  }

  function ensureSavedItemRemoveButton(deleteInput) {
    if (!deleteInput || deleteInput.dataset.orderRemoveBound === '1') return;
    deleteInput.dataset.orderRemoveBound = '1';
    deleteInput.style.display = 'none';
    const label = deleteInput.closest('label');
    if (label) {
      Array.from(label.childNodes).forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) node.textContent = '';
      });
    }

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'order-remove-item';
    button.textContent = 'Quitar producto';
    button.title = 'Quita este producto del pedido. No elimina el producto del catalogo.';
    button.addEventListener('click', function () {
      deleteInput.checked = true;
      deleteInput.dispatchEvent(new Event('change', { bubbles: true }));
      recalcOrderTotal();
    });
    deleteInput.insertAdjacentElement('afterend', button);
  }

  function simplifyInlineControls() {
    document.querySelectorAll('input[name$="-DELETE"]').forEach(ensureSavedItemRemoveButton);
    document.querySelectorAll('.inline-deletelink').forEach((link) => {
      link.textContent = 'Quitar producto';
      link.title = 'Quita este producto del pedido. No elimina el producto del catalogo.';
      link.classList.add('order-remove-item');
    });
    document.querySelectorAll('.inline-group .add-row a.addlink').forEach((link) => {
      link.textContent = '+ Agregar producto';
    });
  }

  function getInlinePrefix(row) {
    const field = row?.querySelector?.('[name*="-"]');
    const match = field?.getAttribute('name')?.match(/^(.+)-(\d+)-/);
    return match ? match[1] : '';
  }

  function reindexInlineRows(prefix) {
    if (!prefix) return;
    const totalForms = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
    const rows = Array.from(document.querySelectorAll(`.dynamic-${prefix}:not(.empty-row)`));
    if (totalForms) totalForms.value = String(rows.length);

    rows.forEach((row, index) => {
      const idPattern = new RegExp(`${prefix}-(\\d+|__prefix__)`, 'g');
      const replacement = `${prefix}-${index}`;
      if (row.id) row.id = row.id.replace(idPattern, replacement);
      row.querySelectorAll('[id], [name], [for]').forEach((field) => {
        if (field.id) field.id = field.id.replace(idPattern, replacement);
        if (field.name) field.name = field.name.replace(idPattern, replacement);
        if (field.htmlFor) field.htmlFor = field.htmlFor.replace(idPattern, replacement);
      });
    });
  }

  function fallbackRemoveInlineRow(deleteLink) {
    const row = deleteLink?.closest?.('tr.form-row');
    if (!row || row.classList.contains('has_original')) return;

    window.setTimeout(() => {
      if (!row.isConnected) {
        recalcOrderTotal();
        return;
      }
      const prefix = getInlinePrefix(row);
      row.remove();
      reindexInlineRows(prefix);
      recalcOrderTotal();
      document.dispatchEvent(new CustomEvent('formset:removed', {
        detail: { formsetName: prefix },
      }));
    }, 80);
  }

  function bindShippingInput() {
    const shippingInput = document.querySelector('[name="envio"]');
    if (!shippingInput || shippingInput.dataset.shippingBound === '1') return;
    shippingInput.dataset.shippingBound = '1';
    shippingInput.addEventListener('input', function () {
      if (String(shippingInput.value || '') !== String(shippingAutofilledValue || '')) {
        shippingManuallyEdited = true;
      }
      recalcOrderTotal();
    });
    shippingInput.addEventListener('change', recalcOrderTotal);
  }

  function setShippingHelp(message) {
    const shippingInput = document.querySelector('[name="envio"]');
    if (!shippingInput) return;
    let help = document.getElementById('order-shipping-help');
    if (!help) {
      help = document.createElement('div');
      help.id = 'order-shipping-help';
      help.className = 'help';
      help.style.marginTop = '6px';
      shippingInput.insertAdjacentElement('afterend', help);
    }
    help.textContent = message;
  }

  function shouldAutofillShipping(userChanged) {
    const shippingInput = document.querySelector('[name="envio"]');
    if (!shippingInput) return false;
    const current = String(shippingInput.value || '').trim();
    if (userChanged) return true;
    if (!current || current === '0' || current === '0.0' || current === '0.00') return true;
    return !shippingManuallyEdited;
  }

  async function updateShippingFromUser(select, forcedUserId) {
    const userId = String(forcedUserId || select.value || '').trim();
    const shippingInput = document.querySelector('[name="envio"]');
    if (!userId || !shippingInput) return;

    bindShippingInput();

    const previousUserId = lastSeenUserBySelect.get(select);
    const userChanged = previousUserId !== userId;

    try {
      const response = await fetch(getUserShippingUrl(userId), {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return;
      const data = await response.json();
      lastSeenUserBySelect.set(select, userId);
      if (!data.available || data.amount === '' || data.amount === null || data.amount === undefined) {
        if (userChanged && (!shippingInput.value || shippingInput.value === '0' || shippingInput.value === '0.00')) {
          shippingInput.value = '0.00';
          shippingAutofilledValue = '0.00';
          shippingManuallyEdited = false;
        }
        setShippingHelp('Este cliente no tiene presupuesto de envio cargado. Podes editar el envio manualmente.');
        recalcOrderTotal();
        return;
      }
      if (!shouldAutofillShipping(userChanged)) return;
      const nextAmount = String(data.amount);
      shippingInput.value = nextAmount;
      shippingAutofilledValue = nextAmount;
      shippingManuallyEdited = false;
      setShippingHelp(data.note ? `Envio del cliente: ${data.note}` : 'Envio cargado desde el presupuesto del cliente.');
      shippingInput.dispatchEvent(new Event('input', { bubbles: true }));
      shippingInput.dispatchEvent(new Event('change', { bubbles: true }));
      recalcOrderTotal();
    } catch (_) {
      setShippingHelp('No se pudo cargar el envio del cliente. Podes editarlo manualmente.');
    }
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
    simplifyInlineControls();
    document.querySelectorAll('select[name$="-product"]').forEach(bindSelect);
    bindShippingInput();
    document.querySelectorAll('select[name="user"]').forEach((select) => {
      if (select.dataset.shippingAutofillBound !== '1') {
        select.dataset.shippingAutofillBound = '1';
        select.addEventListener('change', () => updateShippingFromUser(select));
        select.addEventListener('input', () => updateShippingFromUser(select));
      }
      if (select.value && lastSeenUserBySelect.get(select) !== String(select.value)) {
        updateShippingFromUser(select);
      }
    });
    document.querySelectorAll('input[name$="-precio_unitario"]').forEach(bindPriceInput);
    document.querySelectorAll('input[name$="-cantidad"], input[name$="-DELETE"]').forEach((input) => {
      if (input.dataset.liveTotalBound === '1') return;
      input.dataset.liveTotalBound = '1';
      input.addEventListener('input', recalcOrderTotal);
      input.addEventListener('change', recalcOrderTotal);
      input.addEventListener('click', () => window.setTimeout(recalcOrderTotal, 0));
    });
    recalcOrderTotal();
  }

  document.addEventListener('DOMContentLoaded', bindAll);
  document.addEventListener('formset:added', bindAll);
  document.addEventListener('formset:removed', () => window.setTimeout(recalcOrderTotal, 0));
  document.addEventListener('click', function (event) {
    const deleteLink = event.target?.closest?.('.inline-deletelink');
    if (deleteLink) fallbackRemoveInlineRow(deleteLink);
  });
  document.addEventListener('change', function (event) {
    if (event.target?.matches?.('select[name$="-product"]')) {
      bindSelect(event.target);
      updatePrice(event.target);
    }
    if (event.target?.matches?.('select[name="user"]')) {
      updateShippingFromUser(event.target);
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
    window.django.jQuery(document).on('select2:select', 'select[name="user"]', function (event) {
      const userId = event?.params?.data?.id || this.value;
      window.setTimeout(() => updateShippingFromUser(this, userId), 0);
    });
    window.django.jQuery(document).on('select2:close change', 'select[name="user"]', function () {
      window.setTimeout(() => updateShippingFromUser(this), 0);
    });
  }

  window.setInterval(bindAll, 500);
})();
