const steps = ['welcome', 'menu_upload', 'payment_setup', 'staff_invite'];
let currentStep = 0;

async function initOnboarding() {
  try {
    const data = await API.get('/onboarding/status');
    const idx = steps.indexOf(data.current_step);
    currentStep = idx >= 0 ? idx : 0;
    renderStep();
  } catch (e) {
    UI.showToast(e.message, 'error');
  }
}

function renderStep() {
  document.querySelectorAll('.wizard-step').forEach((el, i) => {
    el.classList.remove('active', 'done');
    if (i < currentStep) el.classList.add('done');
    if (i === currentStep) el.classList.add('active');
  });
  document.getElementById('prevBtn').style.display = currentStep === 0 ? 'none' : 'inline-flex';
  document.getElementById('nextBtn').textContent = currentStep === steps.length - 1 ? 'Завершить' : 'Далее';

  const content = document.getElementById('stepContent');
  const s = steps[currentStep];
  if (s === 'welcome') {
    content.innerHTML = `
      <h2>Добро пожаловать в RestoBot!</h2>
      <p>Этот визард поможет настроить ваш ресторан за несколько шагов.</p>
      <ul>
        <li>Загрузите меню</li>
        <li>Подключите оплату</li>
        <li>Пригласите персонал</li>
      </ul>
    `;
  } else if (s === 'menu_upload') {
    content.innerHTML = `
      <h2>Загрузка меню</h2>
      <p>Перейдите в раздел <a href="/admin/menu.html#${API.getTenant()}">Меню</a> и добавьте категории и блюда.</p>
      <p>После загрузки вернитесь сюда и нажмите «Далее».</p>
    `;
  } else if (s === 'payment_setup') {
    content.innerHTML = `
      <h2>Настройка оплаты</h2>
      <p>Убедитесь, что в настройках ЮKassa указан корректный webhook URL:</p>
      <code style="display:block;background:#f5f5f5;padding:10px;border-radius:6px;margin:10px 0">
        https://your-domain.com/api/v1/${API.getTenant()}/webhook/yookassa
      </code>
    `;
  } else if (s === 'staff_invite') {
    content.innerHTML = `
      <h2>Приглашение персонала</h2>
      <p>Добавьте сотрудников в разделе <a href="/admin/staff.html#${API.getTenant()}">Персонал</a>.</p>
    `;
  }
}

async function nextStep() {
  if (currentStep < steps.length - 1) {
    currentStep++;
    try {
      await API.put('/onboarding/status', { current_step: steps[currentStep] });
    } catch (e) {
      UI.showToast(e.message, 'error');
    }
    renderStep();
  } else {
    try {
      await API.post('/onboarding/complete');
      UI.showToast('Онбординг завершён!');
      setTimeout(() => location.href = '/admin/index.html#' + API.getTenant(), 1000);
    } catch (e) {
      UI.showToast(e.message, 'error');
    }
  }
}

async function prevStep() {
  if (currentStep > 0) {
    currentStep--;
    renderStep();
  }
}
