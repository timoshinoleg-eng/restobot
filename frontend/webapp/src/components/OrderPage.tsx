import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createOrder, createOrderPayment } from '@/api/client';
import { useCart } from '@/context/CartContext';
import { useSession } from '@/context/SessionContext';
import { SessionForm } from './SessionForm';
import { OrderSuccess } from './OrderSuccess';
import { useTelegram } from '@/hooks/useTelegram';
import { formatPhone, isValidPhone } from '@/utils/phoneMask';
import type { OrderCreatePayload } from '@/types';

export function OrderPage({ tenant }: { tenant: string }) {
  const navigate = useNavigate();
  const { session } = useSession();
  const { items, total, clearCart } = useCart();
  const { setMainButton } = useTelegram();

  const [type, setType] = useState<'delivery' | 'pickup' | 'dine_in'>('pickup');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [comment, setComment] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<'cash' | 'card' | 'online'>('cash');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdOrder, setCreatedOrder] = useState<{
    orderNumber: string;
    amount: number;
    orderId: number;
    paymentMethod: 'cash' | 'card' | 'online';
    paymentUrl: string | null;
    paymentError: string | null;
  } | null>(null);

  useEffect(() => {
    if (!session || items.length === 0) return;
    const cleanup = setMainButton('Оформить заказ', () => {
      document.getElementById('submit-order')?.click();
    });
    return () => { if (cleanup) cleanup(); };
  }, [session, items.length, setMainButton]);

  if (!session) {
    return (
      <div>
        <h2 style={{ marginTop: 0 }}>Оформление заказа</h2>
        <p style={{ color: 'var(--muted)', fontSize: 14 }}>Войдите, чтобы продолжить</p>
        <SessionForm tenant={tenant} />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="empty">
        <p>Корзина пуста</p>
        <button className="btn btn-primary" onClick={() => navigate(`/${tenant}/menu`)}>
          В меню
        </button>
      </div>
    );
  }

  if (createdOrder) {
    return (
      <OrderSuccess
        tenant={tenant}
        orderNumber={createdOrder.orderNumber}
        amount={createdOrder.amount}
        orderId={createdOrder.orderId}
        paymentMethod={createdOrder.paymentMethod}
        paymentUrl={createdOrder.paymentUrl}
        paymentError={createdOrder.paymentError}
      />
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!session) return;
    if (type === 'delivery' && !address.trim()) {
      setError('Укажите адрес доставки');
      return;
    }
    if (phone.trim() && !isValidPhone(phone)) {
      setError('Введите корректный номер телефона');
      return;
    }
    if (paymentMethod === 'online' && !phone.trim()) {
      setError('Для онлайн-оплаты укажите телефон');
      return;
    }
    setLoading(true);
    try {
      const payload: OrderCreatePayload = {
        user_id: session.user_id,
        type,
        items: items.map((c) => ({
          menu_item_id: c.item.id,
          quantity: c.quantity,
          price: c.item.price,
          modifiers: null,
        })),
        address: type === 'delivery' ? address.trim() : null,
        phone: phone.trim() || null,
        comment: comment.trim() || null,
        payment_method: paymentMethod,
        loyalty_points_to_use: 0,
      };
      const order = await createOrder(tenant, payload);
      let paymentUrl: string | null = null;
      let paymentError: string | null = null;
      if (paymentMethod === 'online') {
        try {
          const payment = await createOrderPayment(tenant, order.id);
          paymentUrl = payment.confirmation_url;
        } catch (paymentErr) {
          paymentError = paymentErr instanceof Error
            ? `Заказ создан, но ссылка на оплату не получена: ${paymentErr.message}`
            : 'Заказ создан, но ссылка на оплату не получена';
        }
      }
      setCreatedOrder({
        orderNumber: order.order_number,
        amount: order.amount,
        orderId: order.id,
        paymentMethod,
        paymentUrl,
        paymentError,
      });
      clearCart();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка оформления заказа');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Оформление заказа</h2>
      {error && <div className="error">{error}</div>}

      <div className="section-card">
        <div className="card-kicker">Ваш заказ</div>
        {items.map((c) => (
          <div key={c.item.id} className="order-item">
            <div>
              <div style={{ fontWeight: 600 }}>{c.item.name}</div>
              <div style={{ fontSize: 13, color: 'var(--muted)' }}>{c.quantity} × {c.item.price.toLocaleString('ru-RU')} ₽</div>
            </div>
            <div style={{ fontWeight: 700 }}>{(c.quantity * c.item.price).toLocaleString('ru-RU')} ₽</div>
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontWeight: 700, fontSize: 16 }}>
          <span>Итого</span>
          <span>{total.toLocaleString('ru-RU')} ₽</span>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Тип заказа</label>
          <select value={type} onChange={(e) => setType(e.target.value as any)}>
            <option value="pickup">Самовывоз</option>
            <option value="delivery">Доставка</option>
            <option value="dine_in">В зале</option>
          </select>
        </div>

        {type === 'delivery' && (
          <div className="form-group">
            <label>Адрес</label>
            <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Улица, дом, квартира" required />
          </div>
        )}

        <div className="form-group">
          <label>Телефон</label>
          <input value={phone} onChange={(e) => setPhone(formatPhone(e.target.value))} placeholder="+7 (999) 000-00-00" type="tel" />
        </div>

        <div className="form-group">
          <label>Комментарий</label>
          <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} placeholder="Пожелания к заказу" />
        </div>

        <div className="form-group">
          <label>Способ оплаты</label>
          <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value as any)}>
            <option value="cash">Наличные</option>
            <option value="card">Картой при получении</option>
            <option value="online">Онлайн</option>
          </select>
        </div>
        {paymentMethod === 'online' && (
          <div className="info-banner">
            После создания заказа откроется защищённая страница YooKassa для тестовой оплаты.
          </div>
        )}

        <button id="submit-order" className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Оформляем…' : `Оформить заказ на ${total.toLocaleString('ru-RU')} ₽`}
        </button>
      </form>
    </div>
  );
}
