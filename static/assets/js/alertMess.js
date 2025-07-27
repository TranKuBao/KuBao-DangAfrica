function createToast(type, message) {
    const colors = {
      success: 'text-bg-success',
      warning: 'text-bg-warning',
      danger: 'text-bg-danger'
    };
  
    const toastId = 'toast-' + Date.now();
    const toastHTML = `
      <div id="${toastId}" class="toast align-items-center ${colors[type]} border-0 mb-2" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
          <div class="toast-body">${message}</div>
          <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
      </div>
    `;
  
    const toastArea = document.getElementById('toast-area');
    if (toastArea) {
      toastArea.insertAdjacentHTML('beforeend', toastHTML);
      const toastElement = document.getElementById(toastId);
      const toast = new bootstrap.Toast(toastElement);
      toast.show();
  
      toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
      });
    } else {
      console.warn('Không tìm thấy #toast-area trong DOM.');
    }
  }
  
  function showAlertSuccess(msg) {
    createToast('success', msg);
  }
  
  function showAlertWarning(msg) {
    createToast('warning', msg);
  }
  
  function showAlertError(msg) {
    createToast('danger', msg);
  }
  