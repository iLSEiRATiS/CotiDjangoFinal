import { useEffect, useState } from 'react';
import { Card, Table, Alert, Spinner, Button, Tabs, Tab, Form, Row, Col, Badge } from 'react-bootstrap';
import { API_BASE } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import api from '../lib/api';

const STATUSES = ['created', 'approved', 'paid', 'shipped', 'delivered', 'cancelled'];
const STATUS_LABELS = {
  created: 'Creado',
  approved: 'Aprobado',
  paid: 'Pagado',
  shipped: 'Enviado',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
};
const STATUS_VARIANTS = {
  created: 'secondary',
  approved: 'info',
  paid: 'success',
  shipped: 'primary',
  delivered: 'success',
  cancelled: 'danger',
};

export default function Admin() {
  const { token, user } = useAuth();
  const [tab, setTab] = useState('overview');

  // overview
  const [ovrLoading, setOvrLoading] = useState(true);
  const [ovrErr, setOvrErr] = useState('');
  const [overview, setOverview] = useState(null);

  // users
  const [uLoading, setULoading] = useState(true);
  const [uErr, setUErr] = useState('');
  const [users, setUsers] = useState([]);
  const [userQ, setUserQ] = useState('');
  const [newUser, setNewUser] = useState({ name: '', email: '', password: '' });

  // orders
  const [oLoading, setOLoading] = useState(true);
  const [oErr, setOErr] = useState('');
  const [orders, setOrders] = useState([]);
  const [orderStatus, setOrderStatus] = useState('');

  // products
  const [pLoading, setPLoading] = useState(true);
  const [pErr, setPErr] = useState('');
  const [products, setProducts] = useState([]);
  const [productQ, setProductQ] = useState('');

  useEffect(() => {
    let alive = true;
    async function loadAll() {
      try {
        const data = await api.admin.overview(token);
        if (alive) setOverview(data);
      } catch (e) {
        if (alive) setOvrErr(e?.message || 'Error al cargar el resumen');
      } finally {
        if (alive) setOvrLoading(false);
      }

      try {
        const data = await api.admin.listUsers(token, { q: userQ });
        const items = Array.isArray(data) ? data : (data?.items || []);
        if (alive) setUsers(items);
      } catch (e) {
        if (alive) setUErr(e?.message || 'Error al cargar usuarios');
      } finally {
        if (alive) setULoading(false);
      }

      try {
        const data = await api.admin.listOrders(token, { status: orderStatus || undefined });
        const items = Array.isArray(data) ? data : (data?.items || data?.orders || []);
        if (alive) setOrders(items);
      } catch (e) {
        if (alive) setOErr(e?.message || 'Error al cargar pedidos');
      } finally {
        if (alive) setOLoading(false);
      }

      try {
        const data = await api.admin.listProducts(token, { q: productQ });
        const items = Array.isArray(data) ? data : (data?.items || []);
        if (alive) setProducts(items);
      } catch (e) {
        if (alive) setPErr(e?.message || 'Error al cargar productos');
      } finally {
        if (alive) setPLoading(false);
      }
    }
    if (token) loadAll();
    return () => { alive = false; };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleDeleteUser(id) {
    if (!id) return;
    if (user && (user.id === id || user._id === id)) {
      window.alert('No podés borrarte a vos mismo.');
      return;
    }
    if (!window.confirm('¿Eliminar este usuario y sus pedidos?')) return;
    try {
      await api.admin.deleteUser(token, id);
      setUsers(prev => prev.filter(u => (u._id || u.id) !== id));
      setOrders(prev => prev.filter(o => String(o.user) !== String(id)));
    } catch (e) {
      window.alert(e?.message || 'No se pudo eliminar.');
    }
  }

  async function handleCreateUser(e) {
    e.preventDefault();
    try {
      const created = await api.admin.createUser(token, newUser);
      setUsers(prev => [created, ...prev]);
      setNewUser({ name: '', email: '', password: '' });
    } catch (e) {
      window.alert(e?.message || 'No se pudo crear el usuario.');
    }
  }

  async function handleOrderAction(order, nextStatus) {
    try {
      const updated = await api.admin.updateOrder(token, order._id, { status: nextStatus });
      setOrders(prev => prev.map(o => (o._id === order._id ? updated : o)));
    } catch (e) {
      window.alert(e?.message || 'No se pudo actualizar el estado.');
    }
  }

  if (user && user.role !== 'admin') {
    return <Alert variant="warning" className="m-3">Acceso restringido.</Alert>;
  }

  const renderOrders = () => (
    <>
      {oErr && <Alert variant="danger" className="mb-3">{oErr}</Alert>}
      <Form onSubmit={(e)=>e.preventDefault()} className="mb-2">
        <Row className="g-2 align-items-end">
          <Col md>
            <Form.Label>Estado</Form.Label>
            <Form.Select value={orderStatus} onChange={e=>setOrderStatus(e.target.value)}>
              <option value="">Todos</option>
              {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </Form.Select>
          </Col>
          <Col md="auto" className="pt-4">
            <Button variant="outline-primary" onClick={async () => {
              setOLoading(true);
              try {
                const data = await api.admin.listOrders(token, { status: orderStatus || undefined });
                const items = Array.isArray(data) ? data : (data?.items || data?.orders || []);
                setOrders(items);
              } catch (e) {
                setOErr(e?.message || 'Error al cargar pedidos');
              } finally {
                setOLoading(false);
              }
            }}>Filtrar</Button>
          </Col>
        </Row>
      </Form>
      {oLoading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : (
        <Table striped bordered hover responsive>
          <thead>
            <tr>
              <th>ID</th>
              <th>Usuario</th>
              <th>Monto</th>
              <th>Items</th>
              <th>Estado</th>
              <th>Fecha</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(o => (
              <tr key={o._id}>
                <td>{o._id}</td>
                <td>{o.user?.name || o.user?.email || String(o.user)}</td>
                <td>${o.totals?.amount}</td>
                <td>{o.items?.length || 0}</td>
                <td>
                  <Badge bg={STATUS_VARIANTS[o.status] || 'secondary'}>
                    {STATUS_LABELS[o.status] || o.status}
                  </Badge>
                </td>
                <td>{new Date(o.createdAt).toLocaleString()}</td>
                <td className="text-end d-flex flex-wrap gap-1 justify-content-end">
                  <Form.Select
                    size="sm"
                    style={{maxWidth:160}}
                    value={o.status}
                    onChange={e=>handleOrderAction(o, e.target.value)}
                  >
                    {STATUSES.map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
                  </Form.Select>
                  <Button size="sm" variant="outline-success" onClick={() => handleOrderAction(o, 'approved')}>Aprobar</Button>
                  <Button size="sm" variant="outline-primary" onClick={() => handleOrderAction(o, 'paid')}>Marcar pago</Button>
                  <Button size="sm" variant="outline-danger" onClick={() => handleOrderAction(o, 'cancelled')}>Cancelar</Button>
                </td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr><td colSpan={7} className="text-center py-3">Sin pedidos.</td></tr>
            )}
          </tbody>
        </Table>
      )}
    </>
  );

  const renderUsers = () => (
    <>
      {uErr && <Alert variant="danger" className="mb-3">{uErr}</Alert>}
      <Form onSubmit={(e)=>{e.preventDefault();}} className="mb-2">
        <Row className="g-2 align-items-end">
          <Col md>
            <Form.Label>Buscar</Form.Label>
            <Form.Control placeholder="Nombre o email" value={userQ} onChange={e=>setUserQ(e.target.value)} />
          </Col>
          <Col md="auto" className="pt-4">
            <Button variant="outline-primary" onClick={async () => {
              setULoading(true);
              try {
                const data = await api.admin.listUsers(token, { q: userQ });
                const items = Array.isArray(data) ? data : (data?.items || []);
                setUsers(items);
              } catch (e) {
                setUErr(e?.message || 'Error al cargar usuarios');
              } finally {
                setULoading(false);
              }
            }}>Buscar</Button>
          </Col>
        </Row>
      </Form>
      <Form onSubmit={handleCreateUser} className="mb-3">
        <Row className="g-2 align-items-end">
          <Col md>
            <Form.Label>Nombre</Form.Label>
            <Form.Control value={newUser.name} onChange={e=>setNewUser(v=>({...v, name:e.target.value}))} required />
          </Col>
          <Col md>
            <Form.Label>Email</Form.Label>
            <Form.Control type="email" value={newUser.email} onChange={e=>setNewUser(v=>({...v, email:e.target.value}))} required />
          </Col>
          <Col md>
            <Form.Label>Contraseña</Form.Label>
            <Form.Control type="password" value={newUser.password} onChange={e=>setNewUser(v=>({...v, password:e.target.value}))} required />
          </Col>
          <Col md="auto">
            <Button type="submit">Crear usuario</Button>
          </Col>
        </Row>
      </Form>
      {uLoading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : (
        <Table striped bordered hover responsive>
          <thead>
            <tr>
              <th>Avatar</th>
              <th>Nombre</th>
              <th>Email</th>
              <th>Rol</th>
              <th>Teléfono</th>
              <th>Dirección</th>
              <th>Creado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => {
              const id = u._id || u.id;
              let avatar = u.profile?.avatar || '';
              if (avatar && avatar.startsWith('/')) avatar = `${API_BASE}${avatar}`;
              const phone = u.profile?.phone || u.shipping?.phone || '';
              const addr = [u.shipping?.address, u.shipping?.city, u.shipping?.zip].filter(Boolean).join(', ');
              return (
                <tr key={id}>
                  <td>{avatar ? <img src={avatar} alt="avatar" style={{ width: 28, height: 28, borderRadius: '50%', objectFit: 'cover' }} /> : null}</td>
                  <td>{u.name || '-'}</td>
                  <td>{u.email}</td>
                  <td>{u.role}</td>
                  <td>{phone}</td>
                  <td>{addr || '-'}</td>
                  <td>{new Date(u.createdAt).toLocaleString()}</td>
                  <td className="text-end">
                    <Button size="sm" variant="outline-danger" onClick={() => handleDeleteUser(id)}>Borrar</Button>
                  </td>
                </tr>
              );
            })}
            {users.length === 0 && (
              <tr><td colSpan={8} className="text-center py-3">Sin usuarios.</td></tr>
            )}
          </tbody>
        </Table>
      )}
    </>
  );

  const renderOverview = () => (
    <>
      {ovrErr && <Alert variant="danger" className="mb-3">{ovrErr}</Alert>}
      {ovrLoading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : (
        overview && (
          <>
            <Row className="g-3 mb-3">
              <Col md>
                <Card className="h-100"><Card.Body>
                  <div className="text-muted">Usuarios</div>
                  <div className="fs-3 fw-bold">{overview.counts?.users ?? '-'}</div>
                </Card.Body></Card>
              </Col>
              <Col md>
                <Card className="h-100"><Card.Body>
                  <div className="text-muted">Productos</div>
                  <div className="fs-3 fw-bold">{overview.counts?.products ?? '-'}</div>
                </Card.Body></Card>
              </Col>
              <Col md>
                <Card className="h-100"><Card.Body>
                  <div className="text-muted">Pedidos (30d)</div>
                  <div className="fs-5">{overview.last30d?.orders ?? 0} pedidos</div>
                  <div className="text-success fw-bold">${overview.last30d?.revenue?.toFixed ? overview.last30d.revenue.toFixed(2) : overview.last30d?.revenue || 0}</div>
                </Card.Body></Card>
              </Col>
            </Row>
            <h6 className="mb-2">Últimos pedidos</h6>
            <Table size="sm" striped bordered hover responsive>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Usuario</th>
                  <th>Monto</th>
                  <th>Estado</th>
                  <th>Fecha</th>
                </tr>
              </thead>
              <tbody>
                {(overview.lastOrders || []).map(o => (
                  <tr key={o._id}>
                    <td>{o._id}</td>
                    <td>{o.user?.name || o.user?.email || String(o.user)}</td>
                    <td>${o.totals?.amount}</td>
                    <td>
                      <Badge bg={STATUS_VARIANTS[o.status] || 'secondary'}>
                        {STATUS_LABELS[o.status] || o.status}
                      </Badge>
                    </td>
                    <td>{new Date(o.createdAt).toLocaleString()}</td>
                  </tr>
                ))}
                {(!overview.lastOrders || overview.lastOrders.length===0) && (
                  <tr><td colSpan={5} className="text-center py-3">Sin datos.</td></tr>
                )}
              </tbody>
            </Table>
          </>
        )
      )}
    </>
  );

  const renderProducts = () => (
    <>
      {pErr && <Alert variant="danger" className="mb-3">{pErr}</Alert>}
      <Form onSubmit={(e)=>{e.preventDefault();}} className="mb-2">
        <Row className="g-2 align-items-end">
          <Col md>
            <Form.Label>Buscar</Form.Label>
            <Form.Control placeholder="Nombre" value={productQ} onChange={e=>setProductQ(e.target.value)} />
          </Col>
          <Col md="auto" className="pt-4">
            <Button variant="outline-primary" onClick={async () => {
              setPLoading(true);
              try {
                const data = await api.admin.listProducts(token, { q: productQ });
                const items = Array.isArray(data) ? data : (data?.items || []);
                setProducts(items);
              } catch (e) {
                setPErr(e?.message || 'Error al cargar productos');
              } finally {
                setPLoading(false);
              }
            }}>Buscar</Button>
          </Col>
        </Row>
      </Form>
      {pLoading ? (
        <div className="text-center py-5"><Spinner animation="border" /></div>
      ) : (
        <Table striped bordered hover responsive>
          <thead>
            <tr>
              <th>Imagen</th>
              <th>Nombre</th>
              <th>Precio</th>
              <th>Stock</th>
              <th>Activo</th>
            </tr>
          </thead>
          <tbody>
            {products.map(p => {
              let img = p.imagen || (Array.isArray(p.images) && p.images[0]) || '';
              if (typeof img === 'string' && img.startsWith('/')) img = `${API_BASE}${img}`;
              return (
                <tr key={p._id || p.id}>
                  <td>{img ? <img alt={p.name} src={img} style={{width:40,height:40,objectFit:'cover'}} /> : null}</td>
                  <td>{p.name}</td>
                  <td>${p.price ?? p.precio}</td>
                  <td>{p.stock}</td>
                  <td>{p.active ? 'Sí' : 'No'}</td>
                </tr>
              );
            })}
            {products.length === 0 && (
              <tr><td colSpan={5} className="text-center py-3">Sin productos.</td></tr>
            )}
          </tbody>
        </Table>
      )}
    </>
  );

  return (
    <div className="container my-4">
      <div className="d-flex justify-content-between align-items-center mb-2">
        <h5 className="m-0">Administración</h5>
        <a
          className="btn btn-outline-secondary btn-sm"
          href={`${API_BASE}/admin/`}
          target="_blank"
          rel="noreferrer"
        >
          Abrir Django admin
        </a>
      </div>
      <Card>
        <Card.Header><strong>Panel de control</strong></Card.Header>
        <Card.Body>
          <Tabs activeKey={tab} onSelect={(k) => setTab(k || 'overview')} className="mb-3">
            <Tab eventKey="overview" title="Resumen">
              {renderOverview()}
            </Tab>
            <Tab eventKey="orders" title="Pedidos">
              {renderOrders()}
            </Tab>
            <Tab eventKey="users" title="Usuarios">
              {renderUsers()}
            </Tab>
            <Tab eventKey="products" title="Productos">
              {renderProducts()}
            </Tab>
          </Tabs>
        </Card.Body>
      </Card>
    </div>
  );
}
