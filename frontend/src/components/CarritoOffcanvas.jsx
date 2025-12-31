// src/components/CarritoOffcanvas.jsx
import {
  Offcanvas,
  Button,
  Card,
  Image,
  Row,
  Col,
  OverlayTrigger,
  Tooltip,
  Form
} from 'react-bootstrap';
import { FaTrash, FaPlus, FaMinus } from 'react-icons/fa';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';

const money = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' });

const CarritoOffcanvas = ({ show, handleClose }) => {
  const {
    cartItems,
    increaseQuantity,
    decreaseQuantity,
    removeFromCart,
    getTotalPrice,
    clearCart,
    setQuantity
  } = useCart();
  const navigate = useNavigate();

  const handleChange = (id, value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return;
    setQuantity(id, Math.max(1, Math.min(9999, Math.trunc(num))));
  };

  const goCheckout = () => {
    if (!cartItems.length) return;
    if (handleClose) handleClose();
    navigate('/checkout');
  };

  return (
    <Offcanvas
      show={show}
      onHide={handleClose}
      placement="end"
      className="cart-offcanvas"
      aria-labelledby="carrito-offcanvas-title"
      backdrop={true}
      scroll={false}
    >
      <Offcanvas.Header closeButton>
        <Offcanvas.Title id="carrito-offcanvas-title" className="fw-bold">
          🛒 Tu carrito
        </Offcanvas.Title>
      </Offcanvas.Header>

      <Offcanvas.Body>
        {cartItems.length === 0 ? (
          <p className="text-center mt-5 text-muted">Carrito vacío.</p>
        ) : (
          <>
            {cartItems.map(item => (
              <Card key={item.id} className="mb-3 shadow-sm border-0">
                <Card.Body>
                  <Row className="align-items-center">
                    <Col xs={3}>
                      <Image
                        src={item.imagen}
                        alt={item.nombre}
                        fluid
                        roundedCircle
                        style={{ width: 60, height: 60, objectFit: 'cover' }}
                      />
                    </Col>

                    <Col xs={6} className="d-flex flex-column align-items-center">
                      <OverlayTrigger placement="top" overlay={<Tooltip>{item.nombre}</Tooltip>}>
                        <span
                          className="fw-semibold text-center mb-2 text-truncate w-100"
                          style={{ overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis' }}
                        >
                          {item.nombre}
                        </span>
                      </OverlayTrigger>

                      <div className="d-flex align-items-center justify-content-center gap-2">
                        <Button
                          size="sm"
                          variant="outline-secondary"
                          onClick={() => decreaseQuantity(item.id)}
                          aria-label={`Disminuir cantidad de ${item.nombre}`}
                        >
                          <FaMinus />
                        </Button>

                        <Form.Control
                          size="sm"
                          type="number"
                          min={1}
                          max={9999}
                          value={item.cantidad}
                          onChange={(e) => handleChange(item.id, e.target.value)}
                          style={{ width: 72, textAlign: 'center' }}
                          aria-label={`Cantidad para ${item.nombre}`}
                        />

                        <Button
                          size="sm"
                          variant="outline-secondary"
                          onClick={() => increaseQuantity(item.id)}
                          aria-label={`Aumentar cantidad de ${item.nombre}`}
                        >
                          <FaPlus />
                        </Button>
                      </div>
                    </Col>

                    <Col xs={3} className="text-end">
                      <small className="text-muted fw-semibold">
                        {money.format((item.precio ?? 0) * item.cantidad)}
                      </small>
                      <br />
                      <Button
                        size="sm"
                        variant="outline-danger"
                        className="mt-2"
                        onClick={() => removeFromCart(item.id)}
                        aria-label={`Eliminar ${item.nombre}`}
                      >
                        <FaTrash />
                      </Button>
                    </Col>
                  </Row>
                </Card.Body>
              </Card>
            ))}

            <hr />

            <div className="mb-3 text-end">
              <h5 className="fw-bold">Total: {money.format(getTotalPrice())}</h5>
            </div>

            <Button variant="danger" className="w-100 mb-2" onClick={clearCart}>
              Vaciar carrito
            </Button>
            <Button
              variant="success"
              className="w-100"
              onClick={goCheckout}
            >
              Confirmar pedido
            </Button>
          </>
        )}
      </Offcanvas.Body>
    </Offcanvas>
  );
};

export default CarritoOffcanvas;

