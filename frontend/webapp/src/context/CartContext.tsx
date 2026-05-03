import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { CartItem, MenuItem } from '@/types';

interface CartContextValue {
  items: CartItem[];
  addItem: (item: MenuItem) => void;
  removeItem: (menuItemId: number) => void;
  updateQuantity: (menuItemId: number, quantity: number) => void;
  clearCart: () => void;
  total: number;
  count: number;
}

const CartContext = createContext<CartContextValue>({
  items: [],
  addItem: () => {},
  removeItem: () => {},
  updateQuantity: () => {},
  clearCart: () => {},
  total: 0,
  count: 0,
});

function storageKey(tenant: string) {
  return `rb_cart_${tenant}`;
}

export function CartProvider({ tenant, children }: { tenant: string; children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      const raw = localStorage.getItem(storageKey(tenant));
      if (raw) return JSON.parse(raw) as CartItem[];
    } catch {
      // ignore
    }
    return [];
  });

  const addItem = useCallback(
    (item: MenuItem) => {
      setItems((prev) => {
        const existing = prev.find((c) => c.item.id === item.id);
        let next: CartItem[];
        if (existing) {
          next = prev.map((c) => (c.item.id === item.id ? { ...c, quantity: c.quantity + 1 } : c));
        } else {
          next = [...prev, { item, quantity: 1 }];
        }
        localStorage.setItem(storageKey(tenant), JSON.stringify(next));
        return next;
      });
    },
    [tenant]
  );

  const removeItem = useCallback(
    (menuItemId: number) => {
      setItems((prev) => {
        const next = prev.filter((c) => c.item.id !== menuItemId);
        localStorage.setItem(storageKey(tenant), JSON.stringify(next));
        return next;
      });
    },
    [tenant]
  );

  const updateQuantity = useCallback(
    (menuItemId: number, quantity: number) => {
      if (quantity <= 0) {
        removeItem(menuItemId);
        return;
      }
      setItems((prev) => {
        const next = prev.map((c) => (c.item.id === menuItemId ? { ...c, quantity } : c));
        localStorage.setItem(storageKey(tenant), JSON.stringify(next));
        return next;
      });
    },
    [tenant, removeItem]
  );

  const clearCart = useCallback(() => {
    setItems([]);
    localStorage.removeItem(storageKey(tenant));
  }, [tenant]);

  const total = useMemo(() => items.reduce((sum, c) => sum + c.item.price * c.quantity, 0), [items]);
  const count = useMemo(() => items.reduce((sum, c) => sum + c.quantity, 0), [items]);

  const value = useMemo(
    () => ({ items, addItem, removeItem, updateQuantity, clearCart, total, count }),
    [items, addItem, removeItem, updateQuantity, clearCart, total, count]
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  return useContext(CartContext);
}
