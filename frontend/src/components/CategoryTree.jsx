// src/components/CategoryTree.jsx
import { useMemo, useState } from 'react';
import { CATEGORIAS } from '../data/categorias';

const Leaf = ({ label, onClick, active }) => (
  <button
    type="button"
    className={`cat-leaf ${active ? 'active' : ''}`}
    onClick={onClick}
  >
    {label}
  </button>
);

const Node = ({ title, children }) => (
  <div className="cat-node">
    <div className="cat-node-title">{title}</div>
    <div className="cat-node-children">{children}</div>
  </div>
);

/**
 * props:
 * - value: {cat, sub, leaf} objeto con selección actual
 * - onChange: (obj) => void
 * - onClear: () => void
 */
const CategoryTree = ({ value, onChange, onClear }) => {
  const [open, setOpen] = useState({}); // control de expand/collapse

  const toggle = (key) =>
    setOpen((s) => ({ ...s, [key]: !s[key] }));

  const tree = useMemo(() => CATEGORIAS, []);

  return (
    <aside className="category-sidebar">
      <div className="d-flex align-items-center justify-content-between mb-2">
        <h6 className="m-0">Categorías</h6>
        <button className="btn btn-link p-0 cat-clear" onClick={onClear}>Limpiar</button>
      </div>

      <ul className="cat-list list-unstyled mb-0">
        {tree.map((cat) => {
          const catKey = cat.nombre;
          const isOpen = open[catKey] ?? true;
          const activeCat = value?.cat === cat.nombre;

          return (
            <li key={catKey} className={`cat-item ${activeCat ? 'is-active' : ''}`}>
              <button
                className="cat-toggle"
                onClick={() => toggle(catKey)}
                aria-expanded={isOpen}
                type="button"
              >
                <span className="caret">{isOpen ? '▾' : '▸'}</span>
                <span className="label" onClick={(e) => { e.stopPropagation(); onChange({ cat: cat.nombre, sub: null, leaf: null }); }}>
                  {cat.nombre}
                </span>
              </button>

              {isOpen && (
                <div className="cat-block">
                  {cat.subcategorias.map((sc) => {
                    if (typeof sc === 'string') {
                      const activeLeaf = activeCat && value?.leaf === sc && !value?.sub;
                      return (
                        <Leaf
                          key={sc}
                          label={sc}
                          active={activeLeaf}
                          onClick={() => onChange({ cat: cat.nombre, sub: null, leaf: sc })}
                        />
                      );
                    }
                    // sc = { nombre, hijos: [] }
                    const subKey = `${catKey}::${sc.nombre}`;
                    const subOpen = open[subKey] ?? true;
                    const activeSub = activeCat && value?.sub === sc.nombre;

                    return (
                      <Node key={subKey} title={
                        <button className={`cat-sub ${activeSub ? 'active' : ''}`} onClick={() => onChange({ cat: cat.nombre, sub: sc.nombre, leaf: null })}>
                          {sc.nombre}
                        </button>
                      }>
                        <button
                          className="cat-sub-toggle"
                          onClick={() => toggle(subKey)}
                          type="button"
                          aria-expanded={subOpen}
                          title="Expandir/contraer"
                        >
                          {subOpen ? 'Ocultar' : 'Mostrar'}
                        </button>
                        {subOpen && (
                          <ul className="list-unstyled ms-2">
                            {sc.hijos.map((h) => {
                              const activeH = activeCat && value?.sub === sc.nombre && value?.leaf === h;
                              return (
                                <li key={h}>
                                  <Leaf
                                    label={h}
                                    active={activeH}
                                    onClick={() => onChange({ cat: cat.nombre, sub: sc.nombre, leaf: h })}
                                  />
                                </li>
                              );
                            })}
                          </ul>
                        )}
                      </Node>
                    );
                  })}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
};

export default CategoryTree;
