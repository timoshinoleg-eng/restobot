async function loadStaff() {
  try {
    const rows = await API.get('/users');
    const tbody = document.getElementById('staffTable');
    tbody.innerHTML = '';
    rows.forEach(u => {
      const tr = document.createElement('tr');

      const tdName = document.createElement('td');
      tdName.textContent = u.name;
      tr.appendChild(tdName);

      const tdRole = document.createElement('td');
      tdRole.textContent = u.role;
      tr.appendChild(tdRole);

      const tdPhone = document.createElement('td');
      tdPhone.textContent = u.phone || '—';
      tr.appendChild(tdPhone);

      const tdActive = document.createElement('td');
      tdActive.textContent = u.is_active ? 'Активен' : 'Неактивен';
      tr.appendChild(tdActive);

      const tdActions = document.createElement('td');
      const btnEdit = document.createElement('button');
      btnEdit.className = 'btn btn-sm btn-primary';
      btnEdit.textContent = 'Ред.';
      btnEdit.onclick = () => openStaffModal(u.id);
      tdActions.appendChild(btnEdit);

      const btnDel = document.createElement('button');
      btnDel.className = 'btn btn-sm btn-danger';
      btnDel.textContent = 'Удал.';
      btnDel.onclick = () => deleteStaff(u.id);
      tdActions.appendChild(btnDel);

      tr.appendChild(tdActions);
      tbody.appendChild(tr);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function openStaffModal(id) {
  let u = { name:'', role:'waiter', phone:'', telegram_id:'', email:'', is_active: true };
  if (id) {
    try {
      u = await API.get('/users/' + id);
    } catch (err) {
      UI.showToast(err.message, 'error');
      return;
    }
  }
  UI.openModal(id ? 'Редактировать сотрудника' : 'Новый сотрудник', `
    <form id="staffForm">
      <div class="form-group"><label>Имя</label><input name="name" value="${UI.escapeHtml(u.name)}" required></div>
      <div class="form-group"><label>Роль</label>
        <select name="role">
          <option value="waiter" ${u.role==='waiter'?'selected':''}>Официант</option>
          <option value="cook" ${u.role==='cook'?'selected':''}>Повар</option>
          <option value="manager" ${u.role==='manager'?'selected':''}>Менеджер</option>
          <option value="admin" ${u.role==='admin'?'selected':''}>Админ</option>
        </select>
      </div>
      <div class="form-group"><label>Телефон</label><input name="phone" value="${UI.escapeHtml(u.phone)}" placeholder="+7XXXXXXXXXX"></div>
      <div class="form-group"><label>Telegram ID</label><input name="telegram_id" value="${UI.escapeHtml(u.telegram_id)}"></div>
      <div class="form-group"><label>Email</label><input name="email" type="email" value="${UI.escapeHtml(u.email)}"></div>
      ${id ? `<div class="form-group"><label><input type="checkbox" name="is_active" ${u.is_active ? 'checked' : ''}> Активен</label></div>` : ''}
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
      is_active: id ? fd.get('is_active') === 'on' : undefined,
    };
    try {
      if (id) {
        await API.put('/users/' + id, payload);
        UI.showToast('Сотрудник обновлён');
      } else {
        await API.post('/users', payload);
        UI.showToast('Сотрудник добавлен');
      }
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
