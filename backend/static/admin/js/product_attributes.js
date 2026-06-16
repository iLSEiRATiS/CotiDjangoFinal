/**
 * CotiStore - High-End Responsive Variant Manager
 * Fixed interaction logic for perfect functionality.
 */
(function() {
    'use strict';

    function init() {
        if (document.querySelector('.coti-pro-wrapper')) return;

        const attrField = document.getElementById('id_atributos') || document.querySelector('[name="atributos"]');
        const stockField = document.getElementById('id_atributos_sin_stock') || document.querySelector('[name="atributos_sin_stock"]');

        if (!attrField || !stockField) return false;

        const style = document.createElement('style');
        style.innerHTML = `
            .coti-pro-wrapper {
                background: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 8px;
                margin: 20px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                overflow: hidden;
            }
            .coti-pro-header {
                background: #417690;
                color: #fff;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .coti-pro-body {
                padding: 20px;
                background: #fafafa;
            }
            .coti-pro-group {
                margin-bottom: 25px;
            }
            .coti-pro-group:last-child { margin-bottom: 0; }
            .coti-pro-group-title {
                font-size: 12px;
                color: #666;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .coti-pro-group-title::after {
                content: "";
                height: 1px;
                background: #ddd;
                flex: 1;
            }

            .coti-pro-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 12px;
            }
            @media (max-width: 600px) {
                .coti-pro-grid {
                    grid-template-columns: 1fr;
                }
            }

            /* Hacemos que TODA la tarjeta sea un <label> nativo */
            .coti-pro-item {
                background: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 12px 16px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                transition: all 0.2s ease;
                cursor: pointer;
                position: relative;
                box-sizing: border-box;
                margin: 0; /* Override label margins */
            }
            .coti-pro-item:hover {
                border-color: #417690;
                transform: translateY(-1px);
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }

            .coti-pro-info {
                display: flex;
                flex-direction: column;
                min-width: 0;
                flex: 1;
            }
            .coti-pro-label {
                font-size: 14px;
                font-weight: 600;
                color: #333;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                margin-bottom: 2px;
            }
            .coti-pro-badge {
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 2px 8px;
                border-radius: 4px;
                width: fit-content;
            }

            /* States */
            .coti-pro-item.is-on { border-left: 5px solid #28a745; }
            .coti-pro-item.is-on .coti-pro-badge { background: #e8f5e9; color: #2e7d32; }

            .coti-pro-item.is-off { 
                border-left: 5px solid #dc3545; 
                background: #fffcfc;
                border-color: #ffcdd2;
            }
            .coti-pro-item.is-off .coti-pro-badge { background: #ffebee; color: #c62828; }
            .coti-pro-item.is-off .coti-pro-label { color: #b71c1c; }

            /* Professional Toggle */
            .coti-pro-toggle {
                position: relative;
                width: 44px;
                height: 24px;
                margin-left: 15px;
                flex-shrink: 0;
            }
            .coti-pro-toggle input { opacity: 0; width: 0; height: 0; position: absolute; }
            .coti-pro-slider {
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background-color: #dee2e6;
                transition: .3s cubic-bezier(0.4, 0, 0.2, 1);
                border-radius: 24px;
                pointer-events: none; /* Dejamos que el click pase al label padre */
            }
            .coti-pro-slider:before {
                position: absolute;
                content: "";
                height: 18px; width: 18px;
                left: 3px; bottom: 3px;
                background-color: #fff;
                transition: .3s cubic-bezier(0.4, 0, 0.2, 1);
                border-radius: 50%;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }
            .coti-pro-toggle input:checked + .coti-pro-slider { background-color: #dc3545; }
            .coti-pro-toggle input:checked + .coti-pro-slider:before { transform: translateX(20px); }
        `;
        document.head.appendChild(style);

        const container = document.createElement('div');
        container.className = 'coti-pro-wrapper';
        container.innerHTML = `
            <div class="coti-pro-header">⚙️ Gestión de Disponibilidad por Atributo</div>
            <div class="coti-pro-body" id="coti-pro-root"></div>
        `;

        const target = stockField.closest('.form-row') || stockField.parentNode;
        target.parentNode.insertBefore(container, target);
        
        stockField.style.display = 'none';
        const help = stockField.parentNode.querySelector('.help');
        if (help) help.style.display = 'none';

        const root = container.querySelector('#coti-pro-root');

        function render() {
            root.innerHTML = '';
            let attrs = {}, sinStock = {};
            try {
                attrs = JSON.parse(attrField.value || '{}');
                sinStock = JSON.parse(stockField.value || '{}');
            } catch (e) {
                root.innerHTML = '<div style="color:red; font-size:13px; font-weight:bold;">⚠️ Error de datos JSON.</div>';
                return;
            }

            const groups = Object.keys(attrs);
            if (!groups.length) {
                root.innerHTML = '<div style="color:#999; text-align:center; padding: 20px; font-style:italic;">No hay variantes configuradas para este producto.</div>';
                return;
            }

            groups.forEach(groupName => {
                const groupDiv = document.createElement('div');
                groupDiv.className = 'coti-pro-group';
                groupDiv.innerHTML = `<div class="coti-pro-group-title">${groupName}</div>`;
                
                const grid = document.createElement('div');
                grid.className = 'coti-pro-grid';

                const values = Array.isArray(attrs[groupName]) ? attrs[groupName] : [attrs[groupName]];
                values.forEach(val => {
                    const isOff = sinStock[groupName] && sinStock[groupName].includes(val);
                    
                    // Usamos un elemento <label> para que envuelva todo el HTML.
                    // Esto garantiza que hacer clic en CUALQUIER parte de la tarjeta marque el input.
                    const item = document.createElement('label');
                    item.className = `coti-pro-item ${isOff ? 'is-off' : 'is-on'}`;
                    
                    item.innerHTML = `
                        <div class="coti-pro-info">
                            <span class="coti-pro-label" title="${val}">${val}</span>
                            <span class="coti-pro-badge">${isOff ? 'Sin Stock' : 'Habilitado'}</span>
                        </div>
                        <div class="coti-pro-toggle">
                            <input type="checkbox" ${isOff ? 'checked' : ''}>
                            <span class="coti-pro-slider"></span>
                        </div>
                    `;

                    // Solo escuchamos el evento "change" nativo del checkbox. Cero errores.
                    const input = item.querySelector('input');
                    input.addEventListener('change', (e) => {
                        update(groupName, val, e.target.checked);
                    });

                    grid.appendChild(item);
                });

                groupDiv.appendChild(grid);
                root.appendChild(groupDiv);
            });
        }

        function update(name, val, setOff) {
            let current = {};
            try { current = JSON.parse(stockField.value || '{}'); } catch(e){}
            if (!current[name]) current[name] = [];
            
            if (setOff) {
                if (!current[name].includes(val)) current[name].push(val);
            } else {
                current[name] = current[name].filter(x => x !== val);
                if (!current[name].length) delete current[name];
            }
            
            const newVal = JSON.stringify(current);
            stockField.value = newVal;
            stockField.textContent = newVal; 
            
            // SUPER-SAFE FORM SUBMISSION:
            // Creamos un input hidden propio para asegurar que se envíe el valor correcto.
            let hiddenSubmit = document.getElementById('coti-hidden-submit-stock');
            if (!hiddenSubmit) {
                hiddenSubmit = document.createElement('input');
                hiddenSubmit.type = 'hidden';
                hiddenSubmit.id = 'coti-hidden-submit-stock';
                hiddenSubmit.name = stockField.name || 'atributos_sin_stock';
                // Lo agregamos directamente al formulario principal
                const form = stockField.closest('form');
                if (form) {
                    form.appendChild(hiddenSubmit);
                    // Quitamos el 'name' al textarea original para evitar colisiones
                    stockField.removeAttribute('name');
                }
            }
            hiddenSubmit.value = newVal;

            stockField.dispatchEvent(new Event('input', { bubbles: true }));
            stockField.dispatchEvent(new Event('change', { bubbles: true }));

            render();
        }

        render();
        attrField.addEventListener('change', render);
        return true;
    }

    const start = () => { if (!init()) setTimeout(start, 500); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
})();
