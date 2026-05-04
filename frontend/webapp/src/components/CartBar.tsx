import { useNavigate, useParams } from 'react-router-dom';
import { useCart } from '@/context/CartContext';

export function CartBar() {
  const { tenant } = useParams<{ tenant: string }>();
  const navigate = useNavigate();
  const { total, count } = useCart();

  if (count === 0) return null;

  return (
    <div className="cart-bar">
      <div className="info">
        <div className="total">{total.toLocaleString('ru-RU')} ₽</div>
        <div className="count">{count} {new Intl.PluralRules('ru').select(count) === 'one' ? 'товар' : new Intl.PluralRules('ru').select(count) === 'few' ? 'товара' : 'товаров'}</div>
      </div>
      <button className="btn btn-primary" onClick={() => navigate(`/${tenant}/order`)}>
        Оформить
      </button>
    </div>
  );
}
