async function loadInventory() {
  try {
    const rows = await API.get('/ingredients');
    renderInventory(rows);
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function loadLowStock() {
  try {
    const rows = await API.get('/ingredients/low-stock');
    renderInventory(rows);
    UI.showToast('Показаны позиции с низким запасом');
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

function renderInventory(rows) {
  const tbody = document.getElementById('inventoryTable');
  tbody.innerHTML = '';
  rows.forEach(r => {
    const low = parseFloat(r.current_stock) < parseFloat(r.min_stock);
    const tr = document.createElement('tr');

    const tdName = document.createElement('td');
    tdName.textContent = r.name;
    tr.appendChild(tdName);

    const tdUnit = document.createElement('td');
    tdUnit.textContent = r.unit;
    tr.appendChild(tdUnit);

    const tdStock = document.createElement('td');
    tdStock.textContent = r.current_stock;
    tdStock.style.color = low ? 'var(--danger)' : 'inherit';
    tdStock.style.fontWeight = low ? '700' : '400';
    tr.appendChild(tdStock);

    const tdReserved = document.createElement('td');
    tdReserved.textContent = r.reserved_stock;
    tr.appendChild(tdReserved);

    const tdMin = document.createElement('td');
    tdMin.textContent = r.min_stock;
    tr.appendChild(tdMin);

    const tdActions = document.createElement('td');
    const btnAdd = document.createElement('button');
    btnAdd.className = 'btn btn-sm btn-success';
    btnAdd.textContent = '+ Приход';
    btnAdd.onclick = () => openStockModal(r.id);
    tdActions.appendChild(btnAdd);

    const btnDel = document.createElement('button');
    btnDel.className = 'btn btn-sm btn-danger';
    btnDel.textContent = 'Удал.';
    btnDel.onclick = () => deleteIngredient(r.id);
    tdActions.appendChild(btnDel);

    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  });
}

function openIngredientModal() {
  UI.openModal('Новый ингредиент', `
    <form id="ingForm">
      <div class="form-group"><label>Название</label><input name="name" required></div>
      <div class="form-group"><label>Единица</label><input name="unit" value="г"></div>
      <div class="form-group"><label>На складе</label><input name="current_stock" type="number" step="0.01" value="0"></div>
      <div class="form-group"><label>Мин. запас</label><input name="min_stock" type="number" step="0.01" value="0"></div>
      <button type="submit" class="btn btn-primary">Сохранить</button>
    </form>
  `);
  document.getElementById('ingForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      name: fd.get('name'),
      unit: fd.get('unit'),
      current_stock: parseFloat(fd.get('current_stock')),
      min_stock: parseFloat(fd.get('min_stock')),
    };
    try {
      await API.post('/ingredients', payload);
      UI.showToast('Ингредиент добавлен');
      UI.closeModal();
      loadInventory();
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });
}

function openStockModal(id) {
  UI.openModal('Пополнить запасы', `
    <form id="stockForm">
      <div class="form-group"><label>Количество</label><input name="qty" type="number" step="0.01" required></div>
      <div class="form-group"><label>Комментарий</label><input name="comment"></div>
      <button type="submit" class="btn btn-primary">Добавить</button>
    </form>
  `);
  document.getElementById('stockForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await API.post('/ingredients/' + id + '/stock', {
        quantity: parseFloat(fd.get('qty')),
        comment: fd.get('comment') || null,
      });
      UI.showToast('Запасы пополнены');
      UI.closeModal();
      loadInventory();
    } catch (err) {
      UI.showToast(err.message, 'error');
    }
  });
}

async function deleteIngredient(id) {
  if (!confirm('Удалить ингредиент?')) return;
  try {
    await API.del('/ingredients/' + id);
    UI.showToast('Ингредиент удалён');
    loadInventory();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}
