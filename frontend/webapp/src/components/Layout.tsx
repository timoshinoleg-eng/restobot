import { useParams } from 'react-router-dom';

export function Layout({ children }: { children: React.ReactNode }) {
  const { tenant } = useParams<{ tenant: string }>();
  return (
    <div className="layout">
      <header className="header">
        <div className="eyebrow">Telegram WebApp ordering</div>
        <div className="header-row">
          <div>
            <h1>RestoBot Kitchen</h1>
            <p className="header-copy">Меню, оформление заказа и онлайн-оплата в одном сценарии.</p>
          </div>
          <div className="tenant-chip">{tenant || 'demo'}</div>
        </div>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}
