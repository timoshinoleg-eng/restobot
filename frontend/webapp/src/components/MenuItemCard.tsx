import type { MenuItem } from '@/types';
import { useCart } from '@/context/CartContext';

export function MenuItemCard({ item }: { item: MenuItem }) {
  const { items, addItem, updateQuantity } = useCart();
  const cartEntry = items.find((c) => c.item.id === item.id);
  const quantity = cartEntry?.quantity || 0;

  return (
    <div className="menu-card">
      <div
        className={`menu-card-media ${item.image_url ? 'has-image' : ''}`}
        style={item.image_url ? { backgroundImage: `linear-gradient(180deg, transparent, rgba(8, 15, 28, 0.55)), url(${item.image_url})` } : undefined}
      >
        {!item.image_url && <span>{item.name.slice(0, 1)}</span>}
        <div className="menu-card-badge">{item.is_available ? 'Готовим сейчас' : 'Скоро вернётся'}</div>
      </div>
      <div className="menu-card-body">
        <h3>{item.name}</h3>
        {item.description && <p>{item.description}</p>}
      </div>
      <div className="price-row">
        <div className="price">{item.price.toLocaleString('ru-RU')} ₽</div>
        <div className="price-caption">за порцию</div>
      </div>
      <div className="actions">
        {quantity === 0 ? (
          <button className="btn btn-primary btn-small" onClick={() => addItem(item)} disabled={!item.is_available}>
            Добавить
          </button>
        ) : (
          <>
            <button className="btn btn-secondary btn-small" onClick={() => updateQuantity(item.id, quantity - 1)}>
              −
            </button>
            <span style={{ fontWeight: 600, minWidth: 24, textAlign: 'center' }}>{quantity}</span>
            <button className="btn btn-primary btn-small" onClick={() => addItem(item)}>
              +
            </button>
          </>
        )}
      </div>
    </div>
  );
}
