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

      const tdNum = document.createElement('td');
      tdNum.textContent = o.order_number;
      tr.appendChild(tdNum);

      const tdAmount = document.createElement('td');
      tdAmount.textContent = o.amount + ' ₽';
      tr.appendChild(tdAmount);

      const tdStatus = document.createElement('td');
      const badge = document.createElement('span');
      badge.className = 'badge ' + badgeClass;
      badge.textContent = o.status;
      tdStatus.appendChild(badge);
      tr.appendChild(tdStatus);

      const tdPay = document.createElement('td');
      tdPay.textContent = o.payment_status;
      tr.appendChild(tdPay);

      const tdDate = document.createElement('td');
      tdDate.textContent = o.created_at ? o.created_at.split('T')[0] : '';
      tr.appendChild(tdDate);

      const tdActions = document.createElement('td');
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-primary';
      btn.textContent = 'Детали';
      btn.onclick = () => openOrderModal(o.id);
      tdActions.appendChild(btn);
      tr.appendChild(tdActions);

      tbody.appendChild(tr);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function openOrderModal(id) {
  try {
    const o = await API.get('/orders/' + id);
    let items = [];
    try {
      items = (o.items_json && typeof o.items_json === 'string') ? JSON.parse(o.items_json) : (o.items_json || []);
    } catch (e) {
      console.error('Failed to parse order items_json:', e);
    }
    const itemsHtml = Array.isArray(items) && items.length
      ? items.map(it => `<li>${UI.escapeHtml(it.quantity)} × ${UI.escapeHtml(it.menu_item_id)} — ${UI.escapeHtml(it.price)} ₽</li>`).join('')
      : '<li>Невозможно отобразить состав заказа</li>';
    const statusOptions = ['new','confirmed','preparing','ready','delivering','completed','cancelled'].map(s =>
      `<option value="${s}" ${o.status===s?'selected':''}>${s}</option>`
    ).join('');
    UI.openModal('Заказ ' + UI.escapeHtml(o.order_number), `
      <p><strong>Сумма:</strong> ${UI.escapeHtml(o.amount)} ₽</p>
      <p><strong>Тип:</strong> ${UI.escapeHtml(o.type)}</p>
      <p><strong>Адрес:</strong> ${UI.escapeHtml(o.address || '—')}</p>
      <p><strong>Комментарий:</strong> ${UI.escapeHtml(o.comment || '—')}</p>
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
