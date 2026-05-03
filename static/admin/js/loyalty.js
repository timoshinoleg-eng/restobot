async function initLoyalty() {
  try {
    const settings = await API.get('/loyalty');
    document.getElementById('bonusPercent').value = settings.bonus_percent;
    document.getElementById('maxDiscount').value = settings.max_discount_percent;
    document.getElementById('isActive').checked = settings.is_active;

    const txs = await API.get('/loyalty/transactions?limit=50');
    const tbody = document.getElementById('txTable');
    tbody.innerHTML = '';
    txs.forEach(t => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${t.user_id}</td>
        <td>${t.type}</td>
        <td>${t.points}</td>
        <td>${t.description || '—'}</td>
        <td>${t.created_at ? t.created_at.split('T')[0] : ''}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }

  document.getElementById('loyaltyForm').addEventListener('submit', async e => {
    e.preventDefault();
    try {
      await API.put('/loyalty', {
        bonus_percent: parseFloat(document.getElementById('bonusPercent').value),
        max_discount_percent: parseFloat(document.getElementById('maxDiscount').value),
        is_active: document.getElementById('isActive').checked,
      });
      UI.showToast('Настройки сохранены');
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });
}
