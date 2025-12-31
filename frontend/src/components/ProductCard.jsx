// src/components/ProductCard.jsx
import { Card, Button } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { API_BASE } from '../lib/api';

const money = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' });

const ProductCard = ({ product, onAdd }) => {
  const { isLoggedIn } = useAuth();
  const navigate = useNavigate();

  const nombre = product.nombre || product.name || 'Producto';
  const precio = product.precio ?? product.price ?? 0;
  const categoria = product.categoria || product.category?.name || '-';
  let imagen = product.imagen || (Array.isArray(product.images) && product.images[0]) || `https://placehold.co/600x400?text=${encodeURIComponent(nombre)}`;
  if (typeof imagen === 'string' && imagen.startsWith('/')) {
    imagen = `${API_BASE}${imagen}`;
  }
  const id = product.id || product._id || product.slug || '';

  return (
    <Card className="h-100 product-card shadow-sm">
      <div className="product-img-wrap position-relative">
        <Card.Img
          variant="top"
          src={imagen}
          alt={nombre}
          className="object-fit-cover"
        />
        <span className="badge badge-category">{categoria}</span>
      </div>

      <Card.Body className="d-flex flex-column">
        <Card.Title className="mb-1 text-truncate" title={nombre}>
          {nombre}
        </Card.Title>
        <div className="text-muted small mb-2">ID: {id}</div>

        {/* --- Control de sesión --- */}
        {isLoggedIn ? (
          <>
            <div className="fw-bold mb-3">{money.format(precio)}</div>
            <Button className="mt-auto w-100" variant="primary" onClick={() => onAdd(product)}>
              Agregar al carrito
            </Button>
          </>
        ) : (
          <div className="mt-auto text-center text-muted small border rounded py-3 px-2">
            <p className="mb-2" style={{ fontStyle: 'italic' }}>
              Iniciá sesión para ver precios y comprar
            </p>
            <Button variant="outline-primary" size="sm" onClick={() => navigate('/login')}>
              Iniciar sesión
            </Button>
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default ProductCard;

