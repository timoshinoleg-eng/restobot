import { useState } from 'react';
import { createWidgetSession } from '@/api/client';
import { useSession } from '@/context/SessionContext';
import { useTelegram } from '@/hooks/useTelegram';
import { formatPhone, isValidPhone } from '@/utils/phoneMask';

export function SessionForm({ tenant }: { tenant: string }) {
  const { setSession } = useSession();
  const { user: tgUser } = useTelegram();
  const [name, setName] = useState(tgUser?.first_name || '');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError('Введите имя');
      return;
    }
    if (phone.trim() && !isValidPhone(phone)) {
      setError('Введите корректный номер телефона');
      return;
    }
    setLoading(true);
    try {
      const externalId = tgUser?.id ? `tg-${tgUser.id}` : `webapp-${crypto.randomUUID()}`;
      const session = await createWidgetSession(tenant, externalId, name.trim(), phone.trim() || null);
      setSession(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-card">
      <div className="card-kicker">Быстрый вход</div>
      <h3>Представьтесь перед заказом</h3>
      <p>Имя и телефон помогут ресторану подтвердить заказ и связаться по доставке.</p>
      <form onSubmit={handleSubmit}>
        {error && <div className="error">{error}</div>}
        <div className="form-group">
          <label>Имя</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ваше имя" required />
        </div>
        <div className="form-group">
          <label>Телефон</label>
          <input value={phone} onChange={(e) => setPhone(formatPhone(e.target.value))} placeholder="+7 (999) 000-00-00" type="tel" />
        </div>
        <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: '100%' }}>
          {loading ? 'Вход…' : 'Продолжить'}
        </button>
      </form>
    </div>
  );
}
