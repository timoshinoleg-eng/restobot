let categories = [];
let dishes = [];

async function initMenu() {
  try {
    const [cats, items] = await Promise.all([
      API.get('/menu/categories?include_hidden=true'),
      API.get('/menu?include_hidden=true'),
    ]);
    categories = cats;
    dishes = items;
    renderCategoryFilter();
    renderMenu();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }

  document.getElementById('catFilter').addEventListener('change', renderMenu);
  document.getElementById('searchFilter').addEventListener('input', renderMenu);
}

function renderCategoryFilter() {
  const sel = document.getElementById('catFilter');
  sel.innerHTML = '<option value="">Все категории</option>';
  categories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    sel.appendChild(opt);
  });
}

function renderMenu() {
  const catFilter = document.getElementById('catFilter').value;
  const search = document.getElementById('searchFilter').value.toLowerCase();
  const tbody = document.getElementById('menuTable');
  tbody.innerHTML = '';

  dishes
    .filter(d => !catFilter || String(d.category_id) === catFilter)
    .filter(d => !search || (d.name || '').toLowerCase().includes(search))
    .forEach(d => {
      const cat = categories.find(c => c.id === d.category_id);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${d.name}</td>
        <td>${cat ? cat.name : '—'}</td>
        <td>${d.price} ₽</td>
        <td>${d.is_available ? 'Активно' : 'Скрыто'}</td>
        <td>
          <button class="btn btn-sm btn-primary" onclick="openDishModal(${d.id})">Ред.</button>
          <button class="btn btn-sm btn-danger" onclick="deleteDish(${d.id})">Удал.</button>
        </td>
      `;
      tbody.appendChild(tr);
    });
}

function openDishModal(id) {
  const d = id ? dishes.find(x => x.id === id) : null;
  const catOpts = categories.map(c => `<option value="${c.id}" ${d && d.category_id === c.id ? 'selected' : ''}>${c.name}</option>`).join('');
  UI.openModal(d ? 'Редактировать блюдо' : 'Новое блюдо', `
    <form id="dishForm">
      <div class="form-group"><label>Название</label><input name="name" value="${d ? d.name : ''}" required></div>
      <div class="form-group"><label>Описание</label><textarea name="description">${d ? (d.description || '') : ''}</textarea></div>
      <div class="form-group"><label>Цена</label><input name="price" type="number" step="0.01" value="${d ? d.price : ''}" required></div>
      <div class="form-group"><label>Категория</label><select name="category_id">${catOpts}</select></div>
      <div class="form-group"><label>Фото URL</label><input name="image_url" value="${d ? (d.image_url || '') : ''}"></div>
      <div class="form-group">
        <label><input type="checkbox" name="is_available" ${!d || d.is_available ? 'checked' : ''}> Активно</label>
      </div>
      <button type="submit" class="btn btn-primary">Сохранить</button>
    </form>
  `);
  document.getElementById('dishForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      name: fd.get('name'),
      description: fd.get('description') || null,
      price: parseFloat(fd.get('price')),
      category_id: fd.get('category_id') ? parseInt(fd.get('category_id')) : null,
      image_url: fd.get('image_url') || null,
      is_available: !!fd.get('is_available'),
    };
    try {
      if (d) {
        await API.put('/menu/' + d.id, payload);
        UI.showToast('Блюдо обновлено');
      } else {
        await API.post('/menu', payload);
        UI.showToast('Блюдо создано');
      }
      UI.closeModal();
      initMenu();
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });
}

async function deleteDish(id) {
  if (!confirm('Скрыть это блюдо?')) return;
  try {
    await API.del('/menu/' + id);
    UI.showToast('Блюдо скрыто');
    initMenu();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}
