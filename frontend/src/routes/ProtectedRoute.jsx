import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * Compatible con ambos estilos:
 *  - Wrapper con children:
 *      <ProtectedRoute><Account/></ProtectedRoute>
 *      <ProtectedRoute admin><Admin/></ProtectedRoute>
 *  - Rutas anidadas con <Outlet/>:
 *      <Route element={<ProtectedRoute requireAdmin />}>...</Route>
 *
 * Props aceptadas:
 *  - admin (boolean)           -> alias de requireAdmin
 *  - requireAdmin (boolean)    -> requiere rol admin
 */
export default function ProtectedRoute({ children, admin = false, requireAdmin }) {
  const { user, loading } = useAuth();
  const loc = useLocation();

  const mustBeAdmin = typeof requireAdmin === 'boolean' ? requireAdmin : admin;

  if (loading) return null; // o un spinner global
  if (!user) {
    const redirect = encodeURIComponent(loc.pathname || '/');
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  if (mustBeAdmin && user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return children ?? <Outlet />;
}
