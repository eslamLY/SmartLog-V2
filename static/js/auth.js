/* ── Password Visibility Toggle ── */
document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('togglePassword');
  var pw  = document.getElementById('password');
  var icon = document.getElementById('togglePasswordIcon');
  if (btn && pw) {
    btn.style.display = 'flex';
    btn.addEventListener('click', function () {
      var isPassword = pw.type === 'password';
      pw.type = isPassword ? 'text' : 'password';
      if (icon) {
        icon.className = isPassword ? 'ti ti-eye-off' : 'ti ti-eye';
      } else {
        btn.querySelector('i').className = isPassword ? 'ti ti-eye-off' : 'ti ti-eye';
      }
    });
  }
});

/* ── Login Error Handling (Issue #7) ── */
function getCSRFToken() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

async function handleLogin(event) {
  event.preventDefault();

  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const errorDiv = document.getElementById('error');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';

  try {
    if (!navigator.onLine) {
      throw { message: 'لا يوجد اتصال بالإنترنت. تحقق من اتصالك وحاول مرة أخرى.', status: 0 };
    }

    var csrfToken = getCSRFToken();
    if (!csrfToken) {
      errorDiv.textContent = 'خطأ في أمان الصفحة. أعد تحميل الصفحة وحاول مرة أخرى.';
      errorDiv.style.display = 'block';
      return;
    }

    const response = await fetch('/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        username: username.trim().toUpperCase(),
        password: password
      })
    });

    const data = await response.json();

    if (data.ok) {
      window.location.href = data.redirect || '/admin';
      return;
    }

    /* Map specific status codes to user-friendly messages */
    var message = data.msg || 'بيانات الدخول غير صحيحة.';

    if (response.status === 429) {
      message = 'محاولات دخول كثيرة جداً. انتظر 5 دقائق قبل المحاولة مرة أخرى.';
    }

    if (data.blocked_until) {
      message = 'الحساب محظور حالياً. حاول لاحقاً.';
    }

    errorDiv.textContent = message;
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'assertive');
    errorDiv.style.display = 'block';

  } catch (error) {
    console.error('Login error:', error);
    errorDiv.textContent = 'حدث خطأ في الاتصال بالخادم. حاول مرة أخرى.';
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'polite');
    errorDiv.style.display = 'block';
  }
}
