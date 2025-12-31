import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Card, Form, Button, Alert, Spinner, InputGroup } from 'react-bootstrap';
import { BsEyeFill, BsEyeSlashFill } from 'react-icons/bs';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';

const getSafeRedirect = (search, origin) => {
  const candidate = new URLSearchParams(search).get('redirect') || '/';
  try {
    const resolved = new URL(candidate, origin);
    if (resolved.origin !== origin) return '/';
    return resolved.pathname + resolved.search + resolved.hash;
  } catch {
    return '/';
  }
};

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');
  const redirect = useMemo(() => getSafeRedirect(location.search, window.location.origin), [location.search]);

  const { login, isLoggedIn } = useAuth();

  useEffect(() => {
    if (isLoggedIn) navigate(redirect, { replace: true });
  }, [isLoggedIn, navigate, redirect]);

  async function handleSubmit(e) {
    e.preventDefault();
    setErr('');
    try {
      setLoading(true);
      const data = await api.auth.login({ email, password });
      if (!data?.token || !data?.user) throw new Error('Respuesta inválida');
      login({ token: data.token, user: data.user });
      navigate(redirect, { replace: true });
    } catch (e) {
      setErr(e?.message || 'No se pudo iniciar sesión');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container my-5" style={{ maxWidth: 500 }}>
      <Card>
        <Card.Body>
          <h4 className="mb-3">Iniciar sesión</h4>
          {err && <Alert variant="danger">{err}</Alert>}
          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3" controlId="email">
              <Form.Label>Email</Form.Label>
              <Form.Control type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Form.Group>
            <Form.Group className="mb-3" controlId="password">
              <Form.Label>Contraseña</Form.Label>
              <InputGroup>
                <Form.Control
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <Button
                  variant="outline-secondary"
                  type="button"
                  onClick={() => setShowPass(v => !v)}
                  aria-label={showPass ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                >
                  {showPass ? <BsEyeSlashFill /> : <BsEyeFill />}
                </Button>
              </InputGroup>
            </Form.Group>
            <Button type="submit" disabled={loading} className="w-100">
              {loading ? <Spinner size="sm" animation="border" /> : 'Ingresar'}
            </Button>
          </Form>
          <div className="mt-3 text-center">
            ¿No tienes cuenta? <Link to="/register">Regístrate</Link>
          </div>
        </Card.Body>
      </Card>
    </div>
  );
}
