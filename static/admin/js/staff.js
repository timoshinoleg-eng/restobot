async function loadStaff() {
  try {
    const rows = await API.get('/users');
    const tbody = document.getElementById('staffTable');
    tbody.innerHTML = '';
    rows.forEach(u => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${u.name}</td>
        <td>${u.role}</td>
        <td>${u.phone || '—'}</td>
        <td>${u.is_active ? 'Активен' : 'Неактивен'}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="openStaffModal(${u.id})">Ред.</button>
          <button class="btn btn-sm btn-danger" onclick="deleteStaff(${u.id})">Удал.</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

function openStaffModal(id) {
  // staff data loaded on page, could fetch individually but simple enough
  const u = id ? { name:'', role:'waiter', phone:'', telegram_id:'', email:'' } : { name:'', role:'waiter', phone:'', telegram_id:'', email:'' };
  UI.openModal(id ? 'Редактировать сотрудника' : 'Новый сотрудник', `
    <form id="staffForm">
      <div class="form-group"><label>Имя</label><input name="name" required></div>
      <div class="form-group"><label>Роль</label>
        <select name="role">
          <option value="waiter">Официант</option>
          <option value="cook">Повар</option>
          <option value="manager">Менеджер</option>
          <option value="admin">Админ</option>
        </select>
      </div>
      <div class="form-group"><label>Телефон</label><input name="phone" placeholder="+7XXXXXXXXXX"></div>
      <div class="form-group"><label>Telegram ID</label><input name="telegram_id"></div>
      <div class="form-group"><label>Email</label><input name="email" type="email"></div>
      <button type="submit" class="btn btn-primary">Сохранить</button>
    </form>
  `);
  document.getElementById('staffForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      name: fd.get('name'),
      role: fd.get('role'),
      phone: fd.get('phone') || null,
      telegram_id: fd.get('telegram_id') || null,
      email: fd.get('email') || null,
    };
    try {
      await API.post('/users', payload);
      UI.showToast('Сотрудник добавлен');
      UI.closeModal();
      loadStaff();
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });
}

async function deleteStaff(id) {
  if (!confirm('Деактивировать сотрудника?')) return;
  try {
    await API.del('/users/' + id);
    UI.showToast('Сотрудник деактивирован');
    loadStaff();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}
