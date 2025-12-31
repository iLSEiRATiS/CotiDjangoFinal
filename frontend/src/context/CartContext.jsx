// src/context/CartContext.jsx
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useAuth } from './AuthContext';

const CartCtx = createContext(null);

export function CartProvider({ children }) {
  const { token, user, loading } = useAuth();
  const [cartItems, setCartItems] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cart_items') || '[]'); } catch { return []; }
  });

  const userKey = user?.id || user?._id || user?.pk || null;

  const persist = (items) => {
    setCartItems(items);
    localStorage.setItem('cart_items', JSON.stringify(items));
    if (userKey) localStorage.setItem(`cart_items_${userKey}`, JSON.stringify(items));
  };

  // Cuando el usuario cambia, cargamos su carrito guardado; si no hay usuario, vaciamos el carrito visible.
  useEffect(() => {
    if (userKey) {
      try {
        const stored = localStorage.getItem(`cart_items_${userKey}`);
        if (stored) {
          setCartItems(JSON.parse(stored));
          return;
        }
      } catch { /* ignore */ }
      try {
        const fallback = localStorage.getItem('cart_items');
        setCartItems(fallback ? JSON.parse(fallback) : []);
      } catch {
        setCartItems([]);
      }
    } else if (!token && !loading) {
      setCartItems([]);
      localStorage.setItem('cart_items', '[]');
    }
  }, [userKey, token, loading]);

  const findIndex = (id) => cartItems.findIndex(i => String(i.id || i._id) === String(id));

  const isLoggedIn = !!(token || localStorage.getItem('auth_token'));
  const canBuy = isLoggedIn && !loading;

  const addToCart = (product, qty = 1) => {
    if (!canBuy) {
      window.alert('Iniciá sesión para ver precios y comprar.');
      return;
    }
    const cantidad = Math.max(1, Number(qty) || 1);
    const id = product.id || product._id || `${product.categoria}-${product.nombre}`;
    const idx = findIndex(id);
    if (idx >= 0) {
      const copy = [...cartItems];
      copy[idx] = { ...copy[idx], cantidad: (copy[idx].cantidad || 1) + cantidad };
      persist(copy);
    } else {
      persist([...cartItems, {
        id,
        nombre: product.nombre,
        precio: product.precio ?? 0,
        imagen: product.imagen || '',
        cantidad
      }]);
    }
  };

  const removeFromCart = (id) => {
    persist(cartItems.filter(it => String(it.id) !== String(id)));
  };

  const clearCart = () => persist([]);

  const updateQuantity = (id, cantidad) => {
    const idx = findIndex(id);
    if (idx < 0) return;
    const qty = Math.max(1, Number(cantidad) || 1);
    const copy = [...cartItems];
    copy[idx] = { ...copy[idx], cantidad: qty };
    persist(copy);
  };

  const increaseQuantity = (id) => updateQuantity(id, (cartItems[findIndex(id)]?.cantidad || 1) + 1);

  const decreaseQuantity = (id) => updateQuantity(id, Math.max(1, (cartItems[findIndex(id)]?.cantidad || 1) - 1));

  const setQuantity = (id, qty) => updateQuantity(id, qty);

  const getTotalItems = () =>
    cartItems.reduce((acc, it) => acc + (it.cantidad || 1), 0);

  const getTotalPrice = () =>
    cartItems.reduce((acc, it) => acc + (it.precio ?? 0) * (it.cantidad || 1), 0);

  const value = useMemo(() => ({
    cartItems,
    addToCart,
    removeFromCart,
    clearCart,
    updateQuantity,
    increaseQuantity,
    decreaseQuantity,
    setQuantity,
    getTotalItems,
    getTotalPrice,
    canBuy,
  }), [cartItems, canBuy]);

  return <CartCtx.Provider value={value}>{children}</CartCtx.Provider>;
}

export function useCart() {
  const ctx = useContext(CartCtx);
  if (!ctx) throw new Error('useCart debe usarse dentro de <CartProvider>');
  return ctx;
}
