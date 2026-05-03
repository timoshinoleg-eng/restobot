async function initDashboard() {
  try {
    const [revenueData, topDishes, turnover] = await Promise.all([
      API.get('/dashboard/revenue?period=day'),
      API.get('/dashboard/top_dishes?limit=5'),
      API.get('/dashboard/table_turnover'),
    ]);

    // Revenue chart (last 7 days)
    const chart = document.getElementById('revenueChart');
    const rev = (revenueData.data || []).slice(0, 7).reverse();
    const max = Math.max(...rev.map(r => r.total_revenue || 0), 1);
    rev.forEach(r => {
      const bar = document.createElement('div');
      bar.style.flex = '1';
      bar.style.background = 'var(--primary)';
      bar.style.borderRadius = '4px 4px 0 0';
      bar.style.height = Math.round(((r.total_revenue || 0) / max) * 100) + '%';
      bar.style.minHeight = '4px';
      bar.title = `${r.period?.split('T')[0] || ''}: ${Math.round(r.total_revenue || 0)} ₽`;
      chart.appendChild(bar);
    });

    // Top dishes
    const tbody = document.getElementById('topDishes');
    (topDishes.dishes || []).forEach(d => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${d.menu_item_id}</td><td>${d.total_quantity}</td><td>${Math.round(d.total_revenue || 0)} ₽</td>`;
      tbody.appendChild(tr);
    });

    // Metrics
    const today = new Date().toISOString().split('T')[0];
    const todayRev = rev.find(r => (r.period || '').startsWith(today));
    const totalRev = rev.reduce((s, r) => s + (r.total_revenue || 0), 0);
    const totalOrders = rev.reduce((s, r) => s + (r.orders_count || 0), 0);
    document.getElementById('todayRevenue').textContent = (todayRev ? Math.round(todayRev.total_revenue) : 0) + ' ₽';
    document.getElementById('todayOrders').textContent = (todayRev ? todayRev.orders_count : 0);
    document.getElementById('avgCheck').textContent = totalOrders ? Math.round(totalRev / totalOrders) + ' ₽' : '0 ₽';
    document.getElementById('activeBookings').textContent = turnover?.today_reservations || 0;
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}
