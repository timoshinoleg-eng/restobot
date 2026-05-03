async function loadOrders() {
  try {
    const status = document.getElementById('statusFilter').value;
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;
    let qs = '?limit=100';
    if (status) qs += '&status=' + encodeURIComponent(status);
    if (dateFrom) qs += '&date_from=' + encodeURIComponent(dateFrom + 'T00:00:00');
    if (dateTo) qs += '&date_to=' + encodeURIComponent(dateTo + 'T23:59:59');
    const rows = await API.get('/orders' + qs);
    const tbody = document.getElementById('ordersTable');
    tbody.innerHTML = '';
    rows.forEach(o => {
      const tr = document.createElement('tr');
      const badgeClass = 'badge-' + (o.status || 'new');
      tr.innerHTML = `
        <td>${o.order_number}</td>
        <td>${o.amount} ₽</td>
        <td><span class="badge ${badgeClass}">${o.status}</span></td>
        <td>${o.payment_status}</td>
        <td>${o.created_at ? o.created_at.split('T')[0] : ''}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="openOrderModal(${o.id})">Детали</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function openOrderModal(id) {
  try {
    const o = await API.get('/orders/' + id);
    const items = (o.items_json && typeof o.items_json === 'string') ? JSON.parse(o.items_json) : (o.items_json || []);
    const itemsHtml = items.map(it => `<li>${it.quantity} × ${it.menu_item_id} — ${it.price} ₽</li>`).join('');
    const statusOptions = ['new','confirmed','preparing','ready','delivering','completed','cancelled'].map(s =>
      `<option value="${s}" ${o.status===s?'selected':''}>${s}</option>`
    ).join('');
    UI.openModal('Заказ ' + o.order_number, `
      <p><strong>Сумма:</strong> ${o.amount} ₽</p>
      <p><strong>Тип:</strong> ${o.type}</p>
      <p><strong>Адрес:</strong> ${o.address || '—'}</p>
      <p><strong>Комментарий:</strong> ${o.comment || '—'}</p>
      <ul>${itemsHtml}</ul>
      <div class="form-group">
        <label>Статус</label>
        <select id="newStatus">${statusOptions}</select>
      </div>
      <button class="btn btn-primary" onclick="updateOrderStatus(${o.id})">Сохранить статус</button>
    `);
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function updateOrderStatus(id) {
  const status = document.getElementById('newStatus').value;
  try {
    await API.put('/orders/' + id + '/status', { status });
    UI.showToast('Статус обновлён');
    UI.closeModal();
    loadOrders();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}
