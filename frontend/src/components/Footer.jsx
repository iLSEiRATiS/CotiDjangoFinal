// src/components/Footer.jsx
import { useEffect, useState } from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { FaInstagram, FaEnvelope, FaPhoneAlt, FaArrowUp } from 'react-icons/fa';

const Footer = () => {
  const year = new Date().getFullYear();
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 200);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  return (
    <>
      <footer className="bg-dark text-white mt-4 pt-3" role="contentinfo" style={{ paddingBottom: 8 }}>
        <Container>
          <Row className="gy-3 align-items-start">
            <Col md={5}>
              <h6 className="mb-1">CotiStore</h6>
              <p className="mb-0 small text-white-50">
                Mayorista de cotillón y artículos para eventos. Calidad y buen precio.
              </p>
            </Col>

            <Col md={4}>
              <h6 className="mb-1">Contacto</h6>
              <ul className="list-unstyled mb-0 small">
                <li className="d-flex align-items-center">
                  <FaEnvelope className="me-2" aria-hidden />
                  <a
                    href="mailto:ventascotistore@gmail.com"
                    className="link-light text-decoration-none"
                  >
                    ventascotistore@gmail.com
                  </a>
                </li>
                <li className="d-flex align-items-center mt-2">
                  <FaPhoneAlt className="me-2" aria-hidden />
                  <a href="tel:+541139581816" className="link-light text-decoration-none">
                    11 3958-1816
                  </a>
                </li>
              </ul>
            </Col>

            <Col md={3}>
              <h6 className="mb-1">Redes</h6>
              <a
                href="https://www.instagram.com/cotistore_mayorista"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-outline-light btn-sm d-inline-flex align-items-center"
                aria-label="Instagram de CotiStore (se abre en una pestaña nueva)"
              >
                <FaInstagram className="me-2" aria-hidden />
                @cotistore_mayorista
              </a>
            </Col>
          </Row>

          <hr className="border-secondary my-2" />

          <div className="d-flex flex-column flex-md-row justify-content-between align-items-center pb-1">
            <small className="text-white-50">
              © {year} CotiStore — Todos los derechos reservados.
            </small>
          </div>
        </Container>
      </footer>

      {showTop && (
        <button
          type="button"
          onClick={scrollTop}
          aria-label="Subir al inicio"
          className="btn btn-primary shadow position-fixed"
          style={{ right: 16, bottom: 16, borderRadius: '9999px', width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1050 }}
        >
          <FaArrowUp />
        </button>
      )}
    </>
  );
};

export default Footer;
