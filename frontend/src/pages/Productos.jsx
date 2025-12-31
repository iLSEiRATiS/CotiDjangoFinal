import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Container, Row, Col, Button, Dropdown, Badge, Pagination, Form, Spinner, InputGroup
} from 'react-bootstrap';
import { useLocation, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useAuth } from '../context/AuthContext';
import SearchBar from '../components/SearchBar';
import productosData from '../data/productos.json';
import api, { API_BASE } from '../lib/api';

const slugify = (str = '') =>
  str
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');

const norm = (s = '') =>
  s
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

const money = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' });

const SORTERS = {
  relevancia: { label: 'Relevancia', fn: () => 0 },
  precio_asc: { label: 'Precio: menor a mayor', fn: (a, b) => (a.precio ?? 0) - (b.precio ?? 0) },
  precio_desc: { label: 'Precio: mayor a menor', fn: (a, b) => (b.precio ?? 0) - (a.precio ?? 0) },
  nombre_asc: { label: 'Nombre: A-Z', fn: (a, b) => a.nombre.localeCompare(b.nombre) },
  nombre_desc: { label: 'Nombre: Z-A', fn: (a, b) => b.nombre.localeCompare(a.nombre) }
};

function buildTreeFromApi(categories = []) {
  const byId = new Map();
  categories.forEach((c) => {
    const label = c.nombre || c.name || c.label || `Categoria ${c.id}`;
    const slugVal = c.slug || slugify(label);
    byId.set(c.id, { label, slug: slugVal, id: c.id, children: [] });
  });
  const roots = [];
  byId.forEach((node, id) => {
    const cat = categories.find((c) => c.id === id);
    const parentId = cat?.parent || cat?.parent_id || cat?.parentId;
    if (parentId) {
      const parent = byId.get(parentId);
      if (parent) parent.children.push(node);
      else roots.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

const findBySlug = (nodes, slug) => {
  for (const n of nodes) {
    if (n.slug === slug) return n;
    if (n.children) {
      const f = findBySlug(n.children, slug);
      if (f) return f;
    }
  }
  return null;
};
const getTopLevel = (tree) => tree || [];
const leafSlugs = (node) => {
  if (!node?.children || node.children.length === 0) return [node.slug];
  return node.children.flatMap(leafSlugs);
};

export default function Productos() {
  const { addToCart } = useCart();
  const { isLoggedIn } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const gridTopRef = useRef(null);

  const qs = new URLSearchParams(location.search);
  const [search, setSearch] = useState(qs.get('search') ?? '');
  const [sortKey, setSortKey] = useState(qs.get('sort') ?? 'relevancia');
  const [cat, setCat] = useState(qs.get('cat') ?? '');
  const [subcat, setSubcat] = useState(qs.get('subcat') ?? '');
  const [catTree, setCatTree] = useState(null);
  const [expandedL2, setExpandedL2] = useState(null);
  const [offers, setOffers] = useState([]);

  const initialPer = Number(qs.get('per') || 12);
  const initialPage = Number(qs.get('page') || 1);
  const [per, setPer] = useState([12, 24, 48].includes(initialPer) ? initialPer : 12);
  const [page, setPage] = useState(initialPage > 0 ? initialPage : 1);

  // Productos desde API (fuente principal)
  const [remote, setRemote] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const [totalRemote, setTotalRemote] = useState(0);
  const [pagesRemote, setPagesRemote] = useState(1);

  // Sincroniza filtros con la URL
  useEffect(() => {
    const params = new URLSearchParams();
    if (search.trim()) params.set('search', search.trim());
    if (sortKey !== 'relevancia') params.set('sort', sortKey);
    if (cat) params.set('cat', cat);
    if (subcat) params.set('subcat', subcat);
    if (per !== 12) params.set('per', String(per));
    if (page !== 1) params.set('page', String(page));
    navigate({ pathname: '/productos', search: params.toString() }, { replace: true });
  }, [search, sortKey, cat, subcat, per, page, navigate]);

  // Actualiza estado al cambiar la URL (p.ej. búsquedas desde el header)
  useEffect(() => {
    const qsLatest = new URLSearchParams(location.search);
    const nextSearch = qsLatest.get('search') ?? '';
    const nextSort = qsLatest.get('sort') ?? 'relevancia';
    const nextCat = qsLatest.get('cat') ?? '';
    const nextSub = qsLatest.get('subcat') ?? '';
    const perParam = Number(qsLatest.get('per') || 12);
    const nextPer = [12, 24, 48].includes(perParam) ? perParam : 12;
    const pageParam = Number(qsLatest.get('page') || 1);
    const nextPage = pageParam > 0 ? pageParam : 1;

    setSearch(nextSearch);
    setSortKey(nextSort);
    setCat(nextCat);
    setSubcat(nextSub);
    setPer(nextPer);
    setPage(nextPage);
  }, [location.search]);

  // Categorias desde API (sin fallback local: se cargan desde Django)
  useEffect(() => {
    let alive = true;
    async function loadCats() {
      try {
        const data = await api.products.categories();
        const raw = Array.isArray(data?.results) ? data.results : data;
        const tree = Array.isArray(raw) ? buildTreeFromApi(raw) : [];
        if (alive) setCatTree(tree);
      } catch {
        // sin categorias si falla
      }
    }
    loadCats();
    return () => { alive = false; };
  }, []);

  // Ofertas activas
  useEffect(() => {
    let alive = true;
    async function loadOffers() {
      try {
        const data = await api.products.offers();
        const list = Array.isArray(data?.results) ? data.results : (Array.isArray(data) ? data : []);
        if (alive) setOffers(list);
      } catch {
        if (alive) setOffers([]);
      }
    }
    loadOffers();
    return () => { alive = false; };
  }, []);

  // Carga remota con filtros
  useEffect(() => {
    let alive = true;
    async function run() {
      setErr(''); setLoading(true);
      try {
        const category = (subcat || cat) || undefined;
        const data = await api.products.list({ q: search.trim() || undefined, category, page, limit: per });
        const items = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : []);
        const mapped = items.map(p => {
          let img = Array.isArray(p.images) && p.images[0] ? p.images[0] : `https://placehold.co/600x400?text=${encodeURIComponent(p.name || 'Producto')}`;
          if (typeof img === 'string') {
            if (img.startsWith('/')) img = `${API_BASE}${img}`;
            else if (!img.startsWith('http://') && !img.startsWith('https://')) img = '';
          } else {
            img = '';
          }
          const offer = offers.find(o => {
            const pid = o.producto ?? o.product;
            const cid = o.categoria ?? o.category;
            const now = Date.now();
            const startsOk = !o.empieza || new Date(o.empieza).getTime() <= now;
            const endsOk = !o.termina || new Date(o.termina).getTime() >= now;
            const active = o.activo !== false && startsOk && endsOk;
            if (!active) return false;
            if (pid && (String(pid) === String(p._id) || String(pid) === String(p.id))) return true;
            if (cid && p.category?.id && String(cid) === String(p.category.id)) return true;
            return false;
          });
          const precioOriginal = Number(p.priceOriginal ?? p.precio ?? p.price ?? 0);
          const precioBase = Number(p.price ?? p.precio ?? precioOriginal);
          let descuentoPct = Number(p.discount?.percent ?? p.descuento?.percent ?? offer?.porcentaje ?? 0);
          if (!descuentoPct && precioOriginal > 0 && precioBase < precioOriginal) {
            descuentoPct = Math.max(0, Math.round((1 - (precioBase / precioOriginal)) * 100));
          }
          const precio = descuentoPct ? +(precioOriginal * (1 - descuentoPct / 100)).toFixed(2) : precioBase;
          const descuento = descuentoPct ? { percent: descuentoPct, ...(p.discount || p.descuento || {}), offerId: offer?.id || offer?._id } : null;
          return {
            id: p._id || p.slug,
            nombre: p.name,
            precio,
            precioOriginal,
            descuento,
            imagen: img,
            categoria: p.category?.name || 'General',
            categoria_id: p.category?.id,
            categoria_slug: p.category?.slug || (p.category?.name ? slugify(p.category.name) : 'general'),
            subcategoria: '',
            subcategoria_slug: ''
          };
        });
        if (alive) {
          setRemote(mapped);
          setTotalRemote(Number(data?.total) || mapped.length || 0);
          setPagesRemote(Number(data?.pages) || Math.max(1, Math.ceil((Number(data?.total) || mapped.length || 0) / per)));
        }
      } catch (e) {
        if (alive) setErr(e?.message || 'No se pudieron cargar productos');
      } finally {
        if (alive) setLoading(false);
      }
    }
    run();
    return () => { alive = false; };
  }, [search, cat, subcat, page, per]);

  useEffect(() => {
    const handler = (e) => {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key === 'ArrowLeft') { e.preventDefault(); setPage(prev => Math.max(1, prev - 1)); }
      if (e.key === 'ArrowRight') { e.preventDefault(); setPage(prev => prev + 1); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Fallback local (solo si falla backend)
  const localFiltered = useMemo(() => {
    const q = norm(search);
    const matchesText = (p) => {
      const fields = [p.nombre, p.categoria, p.subcategoria, p.subsubcategoria]
        .filter(Boolean).map(norm);
      if (!q) return true;
      return fields.some(f => f.includes(q));
    };
    const matchesCat = (p) => {
      if (!cat && !subcat) return true;
      const pCat = (p.categoria_slug || slugify(p.categoria || '')).toLowerCase();
      const pSub = (p.subcategoria_slug || slugify(p.subcategoria || p.subsubcategoria || '')).toLowerCase();
      if (cat && pCat !== cat) return false;
      if (!subcat) return true;
      const node = findBySlug((catTree || []), subcat);
      if (node?.children?.length) {
        const leaves = leafSlugs(node);
        return leaves.includes(pSub);
      }
      return pSub === subcat;
    };
    return productosData.filter(p => matchesText(p) && matchesCat(p)).sort(SORTERS[sortKey]?.fn ?? SORTERS.relevancia.fn);
  }, [search, sortKey, cat, subcat, catTree]);

  const usingFallback = !!err;
  const total = usingFallback ? localFiltered.length : totalRemote;
  const totalPages = usingFallback ? Math.max(1, Math.ceil(total / per)) : pagesRemote;
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * per;
  const endIdx = usingFallback ? Math.min(startIdx + per, total) : Math.min(startIdx + remote.length, total);
  const paginated = usingFallback ? localFiltered.slice(startIdx, endIdx) : remote;

  useEffect(() => { if (page > totalPages) setPage(totalPages); }, [page, totalPages]);

  useEffect(() => {
    if (gridTopRef.current) {
      const y = gridTopRef.current.getBoundingClientRect().top + window.scrollY - 16;
      window.scrollTo({ top: y, behavior: 'smooth' });
    }
  }, [safePage]);

  const renderPagination = () => {
    if (totalPages <= 1) return null;
    const items = [];
    const maxButtons = 11; // muestra mas paginas para navegar mejor
    const side = 2; // cuantas a cada lado
    const go = (p) => setPage(Math.max(1, Math.min(totalPages, p)));

    items.push(
      <Pagination.First key="first" disabled={safePage === 1} onClick={() => go(1)} />,
      <Pagination.Prev key="prev" disabled={safePage === 1} onClick={() => go(safePage - 1)} />
    );

    if (totalPages <= maxButtons) {
      for (let p = 1; p <= totalPages; p++) {
        items.push(
          <Pagination.Item key={p} active={p === safePage} onClick={() => go(p)}>
            {p}
          </Pagination.Item>
        );
      }
    } else {
      const start = Math.max(2, safePage - side);
      const end = Math.min(totalPages - 1, safePage + side);

      items.push(
        <Pagination.Item key={1} active={safePage === 1} onClick={() => go(1)}>
          1
        </Pagination.Item>
      );
      if (start > 2) items.push(<Pagination.Ellipsis key="ell-start" disabled />);

      for (let p = start; p <= end; p++) {
        items.push(
          <Pagination.Item key={p} active={p === safePage} onClick={() => go(p)}>
            {p}
          </Pagination.Item>
        );
      }

      if (end < totalPages - 1) items.push(<Pagination.Ellipsis key="ell-end" disabled />);
      items.push(
        <Pagination.Item key={totalPages} active={safePage === totalPages} onClick={() => go(totalPages)}>
          {totalPages}
        </Pagination.Item>
      );
    }

    items.push(
      <Pagination.Next key="next" disabled={safePage === totalPages} onClick={() => go(safePage + 1)} />,
      <Pagination.Last key="last" disabled={safePage === totalPages} onClick={() => go(totalPages)} />
    );

    return (
      <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div className="text-muted small">
          Página {safePage} de {totalPages} · {total} productos
        </div>
        <Pagination className="mb-0">{items}</Pagination>
      </div>
    );
  };

  return (
    <Container className="py-4">
      <Row className="mb-3 align-items-center">
        <Col>
          <h2 className="mb-0">Catalogo</h2>
          <small className="text-muted">
            Filtra por categoria o busca por nombre/subcategoria.
          </small>
        </Col>
        <Col className="d-flex justify-content-end align-items-center gap-2">
          {err && <span className="text-danger small me-2">{err}</span>}
          <span className="text-muted small">Ordenar por</span>
          <Dropdown align="end">
            <Dropdown.Toggle size="sm" variant="light">
              {SORTERS[sortKey].label}
            </Dropdown.Toggle>
            <Dropdown.Menu>
              {Object.entries(SORTERS).map(([k, v]) => (
                <Dropdown.Item key={k} active={k === sortKey} onClick={() => setSortKey(k)}>
                  {v.label}
                </Dropdown.Item>
              ))}
            </Dropdown.Menu>
          </Dropdown>
        </Col>
      </Row>

      <Row className="g-4">
        <Col lg={3}>
          <aside className="side-panel">
            <div className="side-section">
              <div className="d-flex align-items-center justify-content-between mb-2">
                <h6 className="m-0">Categorias</h6>
                <button className="btn btn-link p-0 small" onClick={() => { setCat(''); setSubcat(''); setExpandedL2(null); }}>
                  Limpiar
                </button>
              </div>
              <ul className="list-unstyled mb-0">
                {(!getTopLevel(catTree) || getTopLevel(catTree).length === 0) && (
                  <li className="text-muted small">Cargá categorías en el admin de Django.</li>
                )}
                {(getTopLevel(catTree)).map(group => {
                  const isActiveGroup = cat === group.slug;
                  return (
                    <li key={group.slug} className="mb-2">
                      <button
                        className={`side-head ${isActiveGroup ? 'active' : ''}`}
                        onClick={() => {
                          setCat(isActiveGroup ? '' : group.slug);
                          setSubcat('');
                          setExpandedL2(null);
                        }}
                      >
                        <span>{group.label}</span>
                        <span className="chev"></span>
                      </button>

                      {isActiveGroup && (
                        <ul className="list-unstyled ps-3 pt-1">
                          {!group.children?.length && (
                            <li className="text-muted small">Sin subcategorias</li>
                          )}

                          {group.children?.map(l2 => {
                            const l2HasChildren = !!l2.children?.length;
                            const isL2Expanded = expandedL2 === l2.slug;
                            const isL2Chosen = subcat === l2.slug;

                            return (
                              <li key={l2.slug} className="mb-1">
                                <button
                                  className={`side-leaf ${isL2Chosen ? 'active' : ''}`}
                                  onClick={() => {
                                    if (l2HasChildren) {
                                      setExpandedL2(isL2Expanded ? null : l2.slug);
                                    } else {
                                      setSubcat(isL2Chosen ? '' : l2.slug);
                                    }
                                  }}
                                >
                                  {l2.label}{l2HasChildren ? ' >' : ''}
                                </button>

                                {l2HasChildren && isL2Expanded && (
                                  <ul className="list-unstyled ps-3 pt-1">
                                    {l2.children.map(l3 => {
                                      const isL3Chosen = subcat === l3.slug;
                                      return (
                                        <li key={l3.slug}>
                                          <button
                                            className={`side-leaf ${isL3Chosen ? 'active' : ''}`}
                                            onClick={() => setSubcat(isL3Chosen ? '' : l3.slug)}
                                          >
                                            {l3.label}
                                          </button>
                                        </li>
                                      );
                                    })}
                                  </ul>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="side-section mt-4">
              <h6 className="mb-2">Buscar</h6>
              <SearchBar
                value={search}
                onChange={(val) => { setSearch(val); setPage(1); }}
                onSubmit={() => setPage(1)}
                placeholder="Por nombre o categoria"
                ariaLabel="Buscar productos"
              />
            </div>
          </aside>
        </Col>

        <Col lg={9}>
          <div ref={gridTopRef} />
          {loading && (
            <div className="text-center py-4"><Spinner animation="border" /></div>
          )}
          {(() => {
            const chips = [];
            if (cat) {
              const n1 = findBySlug((catTree || []), cat);
              if (n1) chips.push(n1.label);
            }
            if (subcat) {
              const n = findBySlug((catTree || []), subcat);
              if (n) chips.push(n.label);
            }
            if (search.trim()) chips.push(`"${search.trim()}"`);

            if (!chips.length) return null;
            return (
              <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
                {chips.map((c, i) => (
                  <Badge key={`${c}-${i}`} bg="warning" text="dark" className="filter-chip">{c}</Badge>
                ))}
                <Button size="sm" variant="outline-secondary" onClick={() => { setCat(''); setSubcat(''); setSearch(''); setExpandedL2(null); }}>
                  Quitar filtros
                </Button>
              </div>
            );
          })()}

          <div className="d-flex flex-wrap justify-content-between align-items-center mb-3">
            <div className="text-muted small">
              {total === 0
                ? 'Sin resultados'
                : `Mostrando ${startIdx + 1}-${endIdx} de ${total}`}
            </div>
            <div className="d-flex align-items-center gap-2">
              <span className="text-muted small">Ver</span>
              <Form.Select
                size="sm"
                value={per}
                onChange={(e) => setPer(Number(e.target.value))}
                style={{ width: 96 }}
                aria-label="Cantidad por pagina"
              >
                <option value={12}>12</option>
                <option value={24}>24</option>
                <option value={48}>48</option>
              </Form.Select>
              <span className="text-muted small">por pagina</span>
            </div>
          </div>

          <Row className="g-4">
            {paginated.map(p => (
              <Col key={p.id || `${p.categoria}-${p.nombre}`} xs={12} sm={6} md={4}>
                <div className="product-card h-100 d-flex flex-column">
                  <div className="product-img-wrap">
                    {p.imagen ? (
                      <img
                        src={p.imagen}
                        alt={p.nombre}
                        onError={(e) => { e.currentTarget.onerror = null; e.currentTarget.src = 'https://placehold.co/600x400?text=Imagen'; }}
                      />
                    ) : (
                      <div
                        className="d-flex align-items-center justify-content-center bg-light"
                        style={{ height: 160, borderRadius: 8, color: '#9aa' }}
                      >
                        Sin imagen
                      </div>
                    )}
                    <span className="badge badge-category">{p.categoria}</span>
                  </div>
                  <div className="p-3 d-flex flex-column flex-grow-1">
                    <h6 className="mb-2" style={{ lineHeight: 1.2 }}>{p.nombre}</h6>
                    <div className="text-muted small mb-2">
                      {(p.subsubcategoria ? `${p.subcategoria} - ${p.subsubcategoria}` : p.subcategoria) || '-'}
                    </div>

                    {isLoggedIn ? (
                      <>
                        <div className="fw-bold mb-3">
                          {p.descuento?.percent ? (
                            <div>
                              <div className="text-muted text-decoration-line-through small">
                                {money.format(p.precioOriginal ?? p.precio ?? 0)}
                              </div>
                              <div className="d-flex align-items-center gap-2">
                                <span>{money.format(p.precio ?? 0)}</span>
                                <Badge bg="success">-{p.descuento.percent}%</Badge>
                              </div>
                            </div>
                          ) : (
                            money.format(p.precio ?? 0)
                          )}
                        </div>

                        <div className="mt-auto">
                          <div className="small text-muted mb-1">Cantidad</div>
                          <InputGroup className="flex-nowrap">
                            <Form.Control
                              type="number"
                              min={1}
                              max={999}
                              defaultValue={1}
                              size="sm"
                              onChange={(e) => {
                                const val = Math.max(1, Math.min(999, Number(e.target.value) || 1));
                                e.target.value = val;
                              }}
                              onClick={(e) => e.stopPropagation()}
                              style={{ maxWidth: 120 }}
                              aria-label="Cantidad"
                            />
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                const input = e.currentTarget.parentElement.querySelector('input[type=\"number\"]');
                                const qty = input ? Number(input.value) || 1 : 1;
                                addToCart(p, Math.max(1, Math.min(999, qty)));
                              }}
                            >
                              Agregar al carrito
                            </Button>
                          </InputGroup>
                        </div>
                      </>
                    ) : (
                      <div className="mt-auto text-muted small" style={{ fontStyle: 'italic' }}>
                        Inicia sesión para ver precios y comprar
                      </div>
                    )}
                  </div>
                </div>
              </Col>
            ))}
            {paginated.length === 0 && (
              <Col>
                <div className="empty-state text-center py-5">
                  <div className="display-6 mb-2">:)</div>
                  <p>No hay productos con esos filtros.</p>
                  <Button variant="outline-secondary" size="sm" onClick={() => { setCat(''); setSubcat(''); setSearch(''); setExpandedL2(null); }}>
                    Ver todo
                  </Button>
                </div>
              </Col>
            )}
          </Row>

          <div className="d-flex justify-content-center mt-4">
            {renderPagination()}
          </div>
        </Col>
      </Row>
    </Container>
  );
}
