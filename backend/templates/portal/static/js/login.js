document.addEventListener('DOMContentLoaded', () => {
  const pwInput = document.getElementById('id_password');
  const toggleBtn = document.getElementById('toggle-pw');
  
  if (pwInput && toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const isPw = pwInput.type === 'password';
      pwInput.type = isPw ? 'text' : 'password';
      toggleBtn.textContent = isPw ? 'Hide' : 'Show';
    });
  }
});