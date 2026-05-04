async function loadBookings() {
  try {
    const status = document.getElementById('statusFilter').value;
    const date = document.getElementById('dateFilter').value;
    let qs = '?limit=100';
    if (status) qs += '&status=' + encodeURIComponent(status);
    if (date) {
      qs += '&date_from=' + encodeURIComponent(date + 'T00:00:00');
      qs += '&date_to=' + encodeURIComponent(date + 'T23:59:59');
    }
    const rows = await API.get('/reservations' + qs);
    const tbody = document.getElementById('bookingsTable');
    tbody.innerHTML = '';
    rows.forEach(b => {
      const tr = document.createElement('tr');

      const tdTable = document.createElement('td');
      tdTable.textContent = b.table_number || b.table_id;
      tr.appendChild(tdTable);

      const tdName = document.createElement('td');
      tdName.textContent = b.guest_name;
      tr.appendChild(tdName);

      const tdPhone = document.createElement('td');
      tdPhone.textContent = b.guest_phone;
      tr.appendChild(tdPhone);

      const tdTime = document.createElement('td');
      tdTime.textContent = b.start_time ? b.start_time.replace('T', ' ').substring(0, 16) : '';
      tr.appendChild(tdTime);

      const tdGuests = document.createElement('td');
      tdGuests.textContent = b.guests_count;
      tr.appendChild(tdGuests);

      const tdStatus = document.createElement('td');
      tdStatus.textContent = b.status;
      tr.appendChild(tdStatus);

      const tdActions = document.createElement('td');
      const btnEdit = document.createElement('button');
      btnEdit.className = 'btn btn-sm btn-primary';
      btnEdit.textContent = 'Ред.';
      btnEdit.onclick = () => openBookingModal(b.id);
      tdActions.appendChild(btnEdit);

      const btnCancel = document.createElement('button');
      btnCancel.className = 'btn btn-sm btn-danger';
      btnCancel.textContent = 'Отмена';
      btnCancel.onclick = () => cancelBooking(b.id);
      tdActions.appendChild(btnCancel);

      tr.appendChild(tdActions);
      tbody.appendChild(tr);
    });
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function openBookingModal(id) {
  try {
    const b = await API.get('/reservations/' + id);
    UI.openModal('Бронирование #' + id, `
      <div class="form-group"><label>Имя</label><input id="bName" value="${UI.escapeHtml(b.guest_name)}"></div>
      <div class="form-group"><label>Телефон</label><input id="bPhone" value="${UI.escapeHtml(b.guest_phone)}"></div>
      <div class="form-group"><label>Гостей</label><input id="bGuests" type="number" value="${UI.escapeHtml(b.guests_count)}"></div>
      <div class="form-group"><label>Статус</label>
        <select id="bStatus">
          <option value="pending" ${b.status==='pending'?'selected':''}>Ожидает</option>
          <option value="confirmed" ${b.status==='confirmed'?'selected':''}>Подтверждено</option>
          <option value="cancelled" ${b.status==='cancelled'?'selected':''}>Отменено</option>
        </select>
      </div>
      <button class="btn btn-primary" onclick="saveBooking(${id})">Сохранить</button>
    `);
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function saveBooking(id) {
  const payload = {
    guest_name: document.getElementById('bName').value,
    guest_phone: document.getElementById('bPhone').value,
    guests_count: parseInt(document.getElementById('bGuests').value),
    status: document.getElementById('bStatus').value,
  };
  try {
    await API.put('/reservations/' + id, payload);
    UI.showToast('Бронирование обновлено');
    UI.closeModal();
    loadBookings();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

async function cancelBooking(id) {
  if (!confirm('Отменить бронирование?')) return;
  try {
    await API.del('/reservations/' + id);
    UI.showToast('Бронирование отменено');
    loadBookings();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}
