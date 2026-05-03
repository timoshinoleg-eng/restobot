import { useNavigate } from 'react-router-dom';
import { useTelegram } from '@/hooks/useTelegram';

export function OrderSuccess({
  tenant,
  orderNumber,
  amount,
  paymentMethod,
  paymentUrl,
  paymentError,
}: {
  tenant: string;
  orderNumber: string;
  amount: number;
  orderId: number;
  paymentMethod?: 'cash' | 'card' | 'online';
  paymentUrl?: string | null;
  paymentError?: string | null;
}) {
  const navigate = useNavigate();
  const { webApp } = useTelegram();

  const handlePaymentClick = () => {
    if (!paymentUrl) return;
    if (webApp?.openLink) {
      webApp.openLink(paymentUrl);
      return;
    }
    window.location.assign(paymentUrl);
  };

  return (
    <div className="success-card">
      <div className="card-kicker">Заказ принят</div>
      <h2>Готово, кухня получила заказ</h2>
      <p style={{ color: 'var(--muted)', margin: '4px 0' }}>
        {paymentMethod === 'online'
          ? 'Следующий шаг — перейти к оплате и завершить заказ.'
          : 'Спасибо за заказ. Ресторан подтвердит его в ближайшее время.'}
      </p>
      <div className="order-number">№ {orderNumber}</div>
      <div className="success-amount">Сумма: {amount.toLocaleString('ru-RU')} ₽</div>
      {paymentMethod === 'online' && paymentUrl && (
        <button className="btn btn-primary" onClick={handlePaymentClick}>
          Перейти к оплате YooKassa
        </button>
      )}
      {paymentMethod === 'online' && paymentError && (
        <div className="error" style={{ marginTop: 12 }}>
          {paymentError}
        </div>
      )}
      <button className="btn btn-secondary" onClick={() => navigate(`/${tenant}/menu`)}>
        Вернуться в меню
      </button>
    </div>
  );
}
