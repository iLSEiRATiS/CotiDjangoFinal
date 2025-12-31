Paginationimport { useEffect, useState } from 'react';
import { Card, Tabs, Tab, Form, Row, Col, Button, Alert, Spinner, Table } from 'react-bootstrap';
import { Link } from 'react-router-dom';
import * as XLSX from 'xlsx';
import { useAuth } from '../context/AuthContext';
import api, { API_BASE } from '../lib/api';

const safeAvatarSrc = (url) => {
  if (!url) return '';
  const trimmed = String(url).trim();
  if (trimmed.startsWith('blob:')) return trimmed;
  if (trimmed.startsWith('/')) return `${API_BASE}${trimmed}`;
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
  return '';
};

export default function Account() {
  const { token, user, login } = useAuth();
  const [tab, setTab] = useState('profile');
  const PRODUCT_HEADERS = [
    'sku',
    'parent_sku',
    'nombre',
    'slug',
    'descripcion',
    'categoria',
    'subcategoria',
    'marca',
    'precio',
    'costo',
    'moneda',
    'stock',
    'activo',
    'opcion_1_nombre',
    'opcion_1_valor',
    'opcion_2_nombre',
    'opcion_2_valor',
    'imagen_1',
    'imagen_2',
    'meta_title',
    'meta_description',
    'peso',
    'largo',
    'ancho',
    'alto',
    'es_destacado',
    'requiere_envio',
    'gestion_stock'
  ];
  const SAMPLE_ROWS = [
    {
      sku: 'REM-BAS-001',
      parent_sku: '',
      nombre: 'Remera basica',
      slug: 'remera-basica',
      descripcion: 'Remera algodon lisa',
      categoria: 'Ropa',
      subcategoria: 'Remeras',
      marca: 'Acme',
      precio: 8999,
      costo: 4500,
      moneda: 'ARS',
      stock: 120,
      activo: true,
      opcion_1_nombre: '',
      opcion_1_valor: '',
      opcion_2_nombre: '',
      opcion_2_valor: '',
      imagen_1: 'https://example.com/rem-bas-001.jpg',
      imagen_2: '',
      meta_title: 'Remera basica',
      meta_description: 'Remera de algodon basica',
      peso: 0.3,
      largo: 30,
      ancho: 25,
      alto: 2,
      es_destacado: true,
      requiere_envio: true,
      gestion_stock: true
    },
    {
      sku: 'REM-BAS-001-M-NEGRO',
      parent_sku: 'REM-BAS-001',
      nombre: 'Remera basica M Negro',
      slug: 'remera-basica-m-negro',
      descripcion: 'Remera algodon talla M color negro',
      categoria: 'Ropa',
      subcategoria: 'Remeras',
      marca: 'Acme',
      precio: 8999,
      costo: 4500,
      moneda: 'ARS',
      stock: 40,
      activo: true,
      opcion_1_nombre: 'Talle',
      opcion_1_valor: 'M',
      opcion_2_nombre: 'Color',
      opcion_2_valor: 'Negro',
      imagen_1: 'https://example.com/rem-bas-001-m-negro.jpg',
      imagen_2: '',
      meta_title: 'Remera basica M negro',
      meta_description: 'Remera negra basica talla M',
      peso: 0.3,
      largo: 30,
      ancho: 25,
      alto: 2,
      es_destacado: false,
      requiere_envio: true,
      gestion_stock: true
    }
  ];

  // perfil
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [form, setForm] = useState({ name: '', email: '', phone: '' });
  const [avatarFile, setAvatarFile] = useState(null);

  // dirección de envío
  const [ship, setShip] = useState({ name: '', address: '', city: '', zip: '', phone: '' });
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingShip, setSavingShip] = useState(false);

  // seguridad
  const [pwd, setPwd] = useState({ currentPassword: '', newPassword: '', confirm: '' });
  const [savingPwd, setSavingPwd] = useState(false);

  // pedidos
  const [orders, setOrders] = useState([]);
  const [oLoading, setOLoading] = useState(true);
  const [oErr, setOErr] = useState('');
  const [bulkFile, setBulkFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importErr, setImportErr] = useState('');
  const [importMsg, setImportMsg] = useState('');
  const [previewRows, setPreviewRows] = useState([]);

  useEffect(() => {
    let alive = true;
    async function boot() {
      setErr(''); setLoading(true);
      try {
        const data = await api.account.profile(token);
        const u = data?.user || user;
        if (!u) return;
        if (alive) {
          setForm({ name: u.name || '', email: u.email || '', phone: u.profile?.phone || '' });
          setShip({
            name: u.shipping?.name || '',
            address: u.shipping?.address || '',
            city: u.shipping?.city || '',
            zip: u.shipping?.zip || '',
            phone: u.shipping?.phone || ''
          });
        }
      } catch (e) {
        if (alive) setErr(e?.message || 'No se pudo cargar el perfil');
      } finally {
        if (alive) setLoading(false);
      }
    }
    async function loadOrders() {
      setOErr(''); setOLoading(true);
      try {
        const data = await api.orders.mine(token);
        const rows = Array.isArray(data?.orders) ? data.orders : [];
        if (alive) setOrders(rows.slice(0, 5));
      } catch (e) {
        if (alive) setOErr(e?.message || 'No se pudieron cargar los pedidos');
      } finally {
        if (alive) setOLoading(false);
      }
    }
    if (token) {
      boot();
      loadOrders();
    }
    return () => { alive = false; };
  }, [token]);

  async function onSaveProfile(e) {
    e.preventDefault();
    try {
      setSavingProfile(true);
      const phoneRe = /^\+?[0-9\s\-]{6,15}$/;
      if (form.phone && !phoneRe.test(form.phone)) {
        window.alert('Teléfono inválido. Usa solo dígitos, espacios o guiones (6-15).');
        return;
      }
      let updated;
      if (avatarFile) {
        const fd = new FormData();
        fd.append('name', form.name);
        fd.append('email', form.email);
        if ((form.phone || '').trim()) fd.append('profilePhone', form.phone);
        fd.append('avatar', avatarFile);
        const res = await api.account.updateProfile(token, fd);
        updated = res.user;
      } else {
        const res = await api.account.updateProfile(token, { name: form.name, email: form.email, profile: { phone: form.phone } });
        updated = res.user;
      }
      if (updated) login({ token, user: { ...user, ...updated } });
    } catch (e) {
      window.alert(e?.message || 'No se pudo actualizar el perfil');
    } finally {
      setSavingProfile(false);
    }
  }

  async function onRemoveAvatar() {
    try {
      setSavingProfile(true);
      const res = await api.account.updateProfile(token, { removeAvatar: true });
      const updated = res.user;
      if (updated) {
        setAvatarFile(null);
        login({ token, user: { ...user, ...updated } });
      }
    } catch (e) {
      window.alert(e?.message || 'No se pudo quitar el avatar');
    } finally {
      setSavingProfile(false);
    }
  }

  async function onSaveShip(e) {
    e.preventDefault();
    try {
      setSavingShip(true);
      const phoneRe = /^\+?[0-9\s\-]{6,15}$/;
      const zipRe = /^[A-Za-z0-9\-\s]{3,10}$/;
      if (ship.phone && !phoneRe.test(ship.phone)) { window.alert('Teléfono de envío inválido.'); return; }
      if (ship.zip && !zipRe.test(ship.zip)) { window.alert('Código postal inválido.'); return; }
      const { user: updated } = await api.account.updateProfile(token, { shipping: ship });
      if (updated) login({ token, user: { ...user, ...updated } });
    } catch (e) {
      window.alert(e?.message || 'No se pudo guardar la dirección');
    } finally {
      setSavingShip(false);
    }
  }

  async function onChangePassword(e) {
    e.preventDefault();
    if (!pwd.newPassword || pwd.newPassword.length < 6) {
      window.alert('La nueva contraseña debe tener al menos 6 caracteres');
      return;
    }
    if (pwd.newPassword !== pwd.confirm) {
      window.alert('Las contraseñas no coinciden');
      return;
    }
    try {
      setSavingPwd(true);
      await api.account.changePassword(token, { currentPassword: pwd.currentPassword, newPassword: pwd.newPassword });
      setPwd({ currentPassword: '', newPassword: '', confirm: '' });
      window.alert('Contraseña actualizada');
    } catch (e) {
      window.alert(e?.message || 'No se pudo cambiar la contraseña');
    } finally {
      setSavingPwd(false);
    }
  }

  function downloadTemplate(withSample = false) {
    try {
      const rows = withSample ? SAMPLE_ROWS : [Object.fromEntries(PRODUCT_HEADERS.map((h) => [h, '']))];
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.json_to_sheet(rows, { header: PRODUCT_HEADERS });
      XLSX.utils.book_append_sheet(wb, ws, 'Productos');
      XLSX.writeFile(wb, withSample ? 'productos_ejemplo.xlsx' : 'plantilla_productos.xlsx');
    } catch (e) {
      window.alert('No se pudo generar la plantilla: ' + (e?.message || 'error inesperado'));
    }
  }

  function onFileSelect(e) {
    const file = e.target.files && e.target.files[0] ? e.target.files[0] : null;
    setBulkFile(file);
    setImportErr('');
    setImportMsg('');
    setPreviewRows([]);
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const data = new Uint8Array(evt.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        const sheet = workbook.Sheets[workbook.SheetNames[0]];
        const json = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: false });
        setPreviewRows(json.slice(0, 5));
      } catch (err) {
        setImportErr(err?.message || 'No se pudo leer el archivo XLSX');
      }
    };
    reader.readAsArrayBuffer(file);
  }

  async function onImportProducts(e) {
    e.preventDefault();
    if (!bulkFile) { window.alert('Selecciona un archivo XLSX primero.'); return; }
    try {
      setImporting(true);
      setImportErr('');
      setImportMsg('');
      const fd = new FormData();
      fd.append('file', bulkFile);
      const res = await api.admin.importProductsXlsx(token, fd);
      const summary = res?.message || `Importacion enviada. Importados: ${res?.imported ?? 'desconocido'}`;
      setImportMsg(summary);
      if (res?.errors?.length) setImportErr(res.errors.join('; '));
    } catch (e) {
      setImportErr(e?.message || 'No se pudo importar el XLSX');
    } finally {
      setImporting(false);
    }
  }

  if (!user) return null;

  return (
    <div className="container my-4">
      <Card>
        <Card.Header><strong>Mi cuenta</strong></Card.Header>
        <Card.Body>
          {err && <Alert variant="danger" className="mb-3">{err}</Alert>}
          {loading ? (
            <div className="text-center py-5"><Spinner animation="border" /></div>
          ) : (
            <Tabs activeKey={tab} onSelect={(k)=>setTab(k||'profile')} className="mb-3">
              <Tab eventKey="profile" title="Perfil">
                <Form onSubmit={onSaveProfile} className="mb-4 mt-3">
                  <Row className="g-3">
                    <Col md="auto" className="text-center">
                      {(() => {
                        let preview = '';
                        if (avatarFile) {
                          try { preview = URL.createObjectURL(avatarFile); } catch {}
                        } else {
                          let a = user?.profile?.avatar || '';
                          preview = safeAvatarSrc(a);
                        }
                        return preview ? (
                          <img src={preview} alt="avatar" style={{ width: 72, height: 72, borderRadius: '50%', objectFit: 'cover' }} />
                        ) : (
                          <div className="bg-light rounded-circle" style={{ width: 72, height: 72 }} />
                        );
                      })()}
                      <Form.Group className="mt-2">
                        <Form.Control type="file" accept="image/*" onChange={e=>setAvatarFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)} />
                      </Form.Group>
                      {(user?.profile?.avatar || avatarFile) && (
                        <div className="mt-2">
                          <Button variant="outline-danger" size="sm" onClick={onRemoveAvatar} disabled={savingProfile}>Quitar avatar</Button>
                        </div>
                      )}
                    </Col>
                    <Col md>
                      <Form.Label>Nombre</Form.Label>
                      <Form.Control value={form.name} onChange={e=>setForm(v=>({...v, name:e.target.value}))} required />
                    </Col>
                    <Col md>
                      <Form.Label>Email</Form.Label>
                      <Form.Control type="email" value={form.email} onChange={e=>setForm(v=>({...v, email:e.target.value}))} required />
                    </Col>
                    <Col md>
                      <Form.Label>Teléfono</Form.Label>
                      <Form.Control value={form.phone} onChange={e=>setForm(v=>({...v, phone:e.target.value}))} />
                    </Col>
                  </Row>
                  <div className="mt-3">
                    <Button type="submit" disabled={savingProfile}>{savingProfile ? 'Guardando...' : 'Guardar cambios'}</Button>
                  </div>
                </Form>
              </Tab>
              <Tab eventKey="address" title="Dirección">
                <Form onSubmit={onSaveShip} className="mb-4 mt-3">
                  <Row className="g-3">
                    <Col md>
                      <Form.Label>Nombre de recepción</Form.Label>
                      <Form.Control value={ship.name} onChange={e=>setShip(v=>({...v, name:e.target.value}))} />
                    </Col>
                    <Col md>
                      <Form.Label>Teléfono</Form.Label>
                      <Form.Control value={ship.phone} onChange={e=>setShip(v=>({...v, phone:e.target.value}))} />
                    </Col>
                  </Row>
                  <Row className="g-3 mt-1">
                    <Col md>
                      <Form.Label>Dirección</Form.Label>
                      <Form.Control value={ship.address} onChange={e=>setShip(v=>({...v, address:e.target.value}))} />
                    </Col>
                    <Col md>
                      <Form.Label>Ciudad</Form.Label>
                      <Form.Control value={ship.city} onChange={e=>setShip(v=>({...v, city:e.target.value}))} />
                    </Col>
                    <Col md="auto">
                      <Form.Label>CP</Form.Label>
                      <Form.Control style={{minWidth:120}} value={ship.zip} onChange={e=>setShip(v=>({...v, zip:e.target.value}))} />
                    </Col>
                  </Row>
                  <div className="mt-3">
                    <Button type="submit" disabled={savingShip}>{savingShip ? 'Guardando...' : 'Guardar dirección'}</Button>
                  </div>
                </Form>
              </Tab>
              <Tab eventKey="security" title="Seguridad">
                <Form onSubmit={onChangePassword} className="mb-4 mt-3" style={{maxWidth:560}}>
                  <Form.Group className="mb-3">
                    <Form.Label>Contraseña actual</Form.Label>
                    <Form.Control type="password" value={pwd.currentPassword} onChange={e=>setPwd(v=>({...v, currentPassword:e.target.value}))} required />
                  </Form.Group>
                  <Form.Group className="mb-3">
                    <Form.Label>Nueva contraseña</Form.Label>
                    <Form.Control type="password" value={pwd.newPassword} onChange={e=>setPwd(v=>({...v, newPassword:e.target.value}))} required />
                  </Form.Group>
                  <Form.Group className="mb-3">
                    <Form.Label>Confirmar contraseña</Form.Label>
                    <Form.Control type="password" value={pwd.confirm} onChange={e=>setPwd(v=>({...v, confirm:e.target.value}))} required />
                  </Form.Group>
                  <div>
                    <Button type="submit" disabled={savingPwd}>{savingPwd ? 'Guardando...' : 'Cambiar contraseña'}</Button>
                  </div>
                </Form>
              </Tab>
              <Tab eventKey="orders" title="Pedidos">
                {oErr && <Alert variant="danger" className="mb-3">{oErr}</Alert>}
                {oLoading ? (
                  <div className="text-center py-5"><Spinner animation="border" /></div>
                ) : (
                  <>
                    <Table striped bordered hover responsive>
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Items</th>
                          <th>Monto</th>
                          <th>Estado</th>
                          <th>Fecha</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orders.map(o => (
                          <tr key={o._id}>
                            <td>{o._id}</td>
                            <td>{o.totals?.items}</td>
                            <td>${o.totals?.amount?.toFixed ? o.totals.amount.toFixed(2) : o.totals?.amount}</td>
                            <td>{o.status}</td>
                            <td>{new Date(o.createdAt).toLocaleString()}</td>
                          </tr>
                        ))}
                        {orders.length === 0 && (
                          <tr><td colSpan={5} className="text-center py-3">Sin pedidos.</td></tr>
                        )}
                      </tbody>
                    </Table>
                    <div className="text-end">
                      <Button as={Link} to="/orders" variant="outline-primary">Ver todos</Button>
                    </div>
                  </>
                )}
              </Tab>
              <Tab eventKey="products" title="Productos">
                <div className="mt-3">
                  <p className="text-muted" style={{ maxWidth: 760 }}>
                    Carga masiva via XLSX. Usa estos encabezados: sku, parent_sku, nombre, slug, descripcion,
                    categoria, subcategoria, marca, precio, costo, moneda, stock, activo, opcion_1_nombre,
                    opcion_1_valor, opcion_2_nombre, opcion_2_valor, imagen_1, imagen_2, meta_title,
                    meta_description, peso, largo, ancho, alto, es_destacado, requiere_envio, gestion_stock.
                  </p>
                  <div className="d-flex gap-2 mb-3">
                    <Button variant="outline-secondary" onClick={() => downloadTemplate(false)}>Descargar plantilla</Button>
                    <Button variant="outline-primary" onClick={() => downloadTemplate(true)}>Descargar ejemplo</Button>
                  </div>
                  <Form onSubmit={onImportProducts}>
                    <Form.Group className="mb-2" controlId="bulkProductsFile">
                      <Form.Label>Archivo XLSX de productos</Form.Label>
                      <Form.Control type="file" accept=".xlsx" onChange={onFileSelect} />
                      <Form.Text className="text-muted">
                        Verifica que sku sea unico, que las categorias existan y que precio/stock sean numericos.
                        Para variantes usa parent_sku y las columnas opcion_1/2.
                      </Form.Text>
                    </Form.Group>
                    {previewRows.length > 0 && (
                      <div className="mt-3">
                        <div className="text-muted small mb-1">Primeras filas detectadas</div>
                        <Table striped bordered hover responsive size="sm">
                          <thead>
                            <tr>
                              {PRODUCT_HEADERS.slice(0, 6).map((h) => <th key={h}>{h}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {previewRows.map((row, idx) => (
                              <tr key={idx}>
                                {PRODUCT_HEADERS.slice(0, 6).map((h) => <td key={h}>{String(row[h] ?? '')}</td>)}
                              </tr>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                    )}
                    {importErr && <Alert variant="danger" className="mt-2">{importErr}</Alert>}
                    {importMsg && <Alert variant="success" className="mt-2">{importMsg}</Alert>}
                    <div className="mt-3 d-flex align-items-center gap-2">
                      <Button type="submit" disabled={importing}>{importing ? 'Subiendo...' : 'Subir XLSX'}</Button>
                      <span className="text-muted small">Se enviara al endpoint de admin para crear/actualizar productos.</span>
                    </div>
                  </Form>
                </div>
              </Tab>
            </Tabs>
          )}
        </Card.Body>
      </Card>
    </div>
  );
}
