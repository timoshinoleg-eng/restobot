import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { SessionProvider } from '@/context/SessionContext';
import { CartProvider } from '@/context/CartContext';
import { Layout } from '@/components/Layout';
import { MenuPage } from '@/components/MenuPage';
import { OrderPage } from '@/components/OrderPage';

function TenantRoutes() {
  const { tenant } = useParams<{ tenant: string }>();
  if (!tenant) return <Navigate to="/" replace />;
  return (
    <SessionProvider tenant={tenant}>
      <CartProvider tenant={tenant}>
        <Layout>
          <Routes>
            <Route path="menu" element={<MenuPage tenant={tenant} />} />
            <Route path="order" element={<OrderPage tenant={tenant} />} />
            <Route path="*" element={<Navigate to="menu" replace />} />
          </Routes>
        </Layout>
      </CartProvider>
    </SessionProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/:tenant/*" element={<TenantRoutes />} />
        <Route path="*" element={<div className="empty">Перейдите по ссылке ресторана</div>} />
      </Routes>
    </BrowserRouter>
  );
}
