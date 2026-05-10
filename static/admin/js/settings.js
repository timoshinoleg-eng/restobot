const days = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];

async function initSettings() {
  try {
    const data = await API.get('/settings');
    const rs = data.restaurant || {};
    document.getElementById('restName').value = rs.restaurant_name || '';
    document.getElementById('minOrder').value = rs.min_order_amount || 0;
    document.getElementById('deliveryRadius').value = rs.delivery_radius || 0;
    document.getElementById('vatCode').value = rs.vat_code || 1;
    document.getElementById('currency').value = rs.currency || 'RUB';

    const wh = data.working_hours || [];
    const grid = document.getElementById('hoursGrid');
    grid.innerHTML = '';
    days.forEach((label, idx) => {
      const h = wh.find(x => x.day_of_week === idx) || { open_time: '10:00', close_time: '22:00', is_closed: false };
      const row = document.createElement('div');
      row.className = 'form-group';
      row.style.display = 'flex';
      row.style.gap = '10px';
      row.style.alignItems = 'center';
      row.innerHTML = `
        <label style="min-width:40px">${label}</label>
        <input type="time" name="open_${idx}" value="${h.open_time ? h.open_time.substring(0,5) : '10:00'}" style="width:auto">
        <input type="time" name="close_${idx}" value="${h.close_time ? h.close_time.substring(0,5) : '22:00'}" style="width:auto">
        <label><input type="checkbox" name="closed_${idx}" ${h.is_closed ? 'checked' : ''}> Выходной</label>
      `;
      grid.appendChild(row);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }

  document.getElementById('settingsForm').addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await API.put('/settings', {
        restaurant_name: document.getElementById('restName').value || null,
        min_order_amount: parseFloat(document.getElementById('minOrder').value) || 0,
        delivery_radius: parseFloat(document.getElementById('deliveryRadius').value) || null,
        vat_code: parseInt(document.getElementById('vatCode').value, 10) || 1,
        currency: document.getElementById('currency').value || 'RUB',
      });
      UI.showToast('Настройки сохранены');
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });

  document.getElementById('hoursForm').addEventListener('submit', async e => {
    e.preventDefault();
    const hours = [];
    for (let i = 0; i < 7; i++) {
      hours.push({
        day_of_week: i,
        open_time: document.querySelector(`[name="open_${i}"]`).value || null,
        close_time: document.querySelector(`[name="close_${i}"]`).value || null,
        is_closed: document.querySelector(`[name="closed_${i}"]`).checked,
      });
    }
    try {
      await API.put('/settings/working-hours', { hours });
      UI.showToast('Часы работы сохранены');
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });
}
