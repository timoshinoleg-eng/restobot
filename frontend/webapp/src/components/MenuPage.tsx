import { useEffect, useMemo, useState } from 'react';
import { fetchCategories, fetchMenu } from '@/api/client';
import { CartBar } from './CartBar';
import { MenuItemCard } from './MenuItemCard';
import type { MenuCategory, MenuItem } from '@/types';

export function MenuPage({ tenant }: { tenant: string }) {
  const [categories, setCategories] = useState<MenuCategory[]>([]);
  const [items, setItems] = useState<MenuItem[]>([]);
  const [activeCategory, setActiveCategory] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([fetchCategories(tenant), fetchMenu(tenant)])
      .then(([cats, menu]) => {
        if (cancelled) return;
        setCategories(cats);
        setItems(menu);
        if (cats.length > 0) setActiveCategory(cats[0].id);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Ошибка загрузки меню');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [tenant]);

  const filteredItems = useMemo(() => {
    if (!activeCategory) return items;
    return items.filter((i) => i.category_id === activeCategory);
  }, [items, activeCategory]);
  const featuredItem = filteredItems[0] || items[0] || null;
  const availableCount = items.filter((item) => item.is_available).length;

  return (
    <div>
      {error && <div className="error">{error}</div>}
      {loading && (
        <div className="empty">
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          Загрузка меню…
        </div>
      )}
      {!loading && categories.length === 0 && (
        <div className="empty">Меню пока пусто.</div>
      )}
      {!loading && categories.length > 0 && (
        <>
          <section className="hero-panel">
            <div className="hero-copy">
              <div className="card-kicker">Ресторан {tenant}</div>
              <h2>Соберите заказ в пару касаний</h2>
              <p>
                Актуальное меню, быстрый checkout и готовый сценарий для Telegram-пилота.
              </p>
              <div className="hero-stats">
                <div className="stat-chip">
                  <strong>{categories.length}</strong>
                  <span>категории</span>
                </div>
                <div className="stat-chip">
                  <strong>{availableCount}</strong>
                  <span>доступно сейчас</span>
                </div>
              </div>
            </div>
            {featuredItem && (
              <div
                className="hero-feature"
                style={featuredItem.image_url ? { backgroundImage: `linear-gradient(180deg, rgba(8, 15, 28, 0.12), rgba(8, 15, 28, 0.72)), url(${featuredItem.image_url})` } : undefined}
              >
                <div className="hero-feature-label">Сегодня рекомендуем</div>
                <strong>{featuredItem.name}</strong>
                <span>{featuredItem.price.toLocaleString('ru-RU')} ₽</span>
              </div>
            )}
          </section>
          <div className="section-heading">
            <div>
              <h3>Меню</h3>
              <p>Выберите категорию и добавьте позиции в корзину.</p>
            </div>
          </div>
          <div className="category-tabs">
            {categories.map((cat) => (
              <button
                key={cat.id}
                className={`category-tab ${activeCategory === cat.id ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat.id)}
              >
                {cat.emoji ? `${cat.emoji} ` : ''}{cat.name}
              </button>
            ))}
          </div>
          <div className="menu-grid">
            {filteredItems.map((item) => (
              <MenuItemCard key={item.id} item={item} />
            ))}
          </div>
          {filteredItems.length === 0 && (
            <div className="empty">В этой категории пока нет блюд.</div>
          )}
        </>
      )}
      <CartBar />
    </div>
  );
}
