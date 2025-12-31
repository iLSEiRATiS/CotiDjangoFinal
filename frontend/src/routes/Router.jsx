// frontend/src/routes/Router.js
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Suspense, lazy } from 'react';
import Layout from '../components/Layout';
import ProtectedRoute from './ProtectedRoute';

const Home = lazy(() => import('../pages/Home'));
const Productos = lazy(() => import('../pages/Productos'));
const Login = lazy(() => import('../pages/Login'));
const Register = lazy(() => import('../pages/Register'));
const Carrito = lazy(() => import('../pages/Carrito'));
const Account = lazy(() => import('../pages/Account'));
const Admin = lazy(() => import('../pages/Admin'));
const Panel = lazy(() => import('../pages/Panel'));
const Orders = lazy(() => import('../pages/Orders'));     // NUEVO
const Checkout = lazy(() => import('../pages/Checkout')); // NUEVO

const NotFound = () => (
  <div className="text-center my-5" role="alert">
    <h2>Página no encontrada</h2>
    <p>Verificá la URL o volvé al inicio.</p>
  </div>
);

const AppRouter = () => (
  <BrowserRouter>
    <Layout>
      <Suspense fallback={<div className="text-center py-5">Cargando…</div>}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/productos" element={<Productos />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/carrito" element={<Carrito />} />

          {/* Usuario logueado */}
          <Route
            path="/account"
            element={
              <ProtectedRoute>
                <Account />
              </ProtectedRoute>
            }
          />
          <Route
            path="/panel"
            element={
              <ProtectedRoute>
                <Panel />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders"
            element={
              <ProtectedRoute>
                <Orders />
              </ProtectedRoute>
            }
          />
          <Route
            path="/checkout"
            element={
              <ProtectedRoute>
                <Checkout />
              </ProtectedRoute>
            }
          />

          {/* Admin */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute admin>
                <Admin />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </Layout>
  </BrowserRouter>
);

export default AppRouter;



