/* ── Login Error Handling (Issue #7) ── */
async function handleLogin(event) {
  event.preventDefault();

  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  const errorDiv = document.getElementById('error');

  errorDiv.textContent = '';
  errorDiv.style.display = 'none';

  try {
    if (!navigator.onLine) {
      throw {
        message: 'لا يوجد اتصال بالإنترنت. تحقق من اتصالك وحاول مرة أخرى.',
        status: 0
      };
    }

    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();

    if (response.ok) {
      window.location.href = '/dashboard';
      return;
    }

    const errorMap = {
      400: 'بيانات الدخول غير صحيحة. تأكد من الرقم الوظيفي وكلمة المرور.',
      401: 'الرقم الوظيفي أو كلمة المرور غير صحيحة.',
      429: 'محاولات دخول كثيرة جداً. انتظر 5 دقائق قبل المحاولة مرة أخرى.',
      500: 'خطأ في الخادم. يرجى المحاولة بعد قليل.',
      503: 'الخدمة غير متاحة حالياً. يرجى المحاولة لاحقاً.'
    };

    throw {
      message: errorMap[response.status] || data.error || 'حدث خطأ غير متوقع.',
      status: response.status
    };

  } catch (error) {
    console.error('Login error:', error);

    errorDiv.textContent = error.message ||
      'حدث خطأ غير متوقع. إذا استمرت المشكلة، تواصل مع الدعم الفني.';
    errorDiv.setAttribute('role', 'alert');
    errorDiv.setAttribute('aria-live', 'polite');
    errorDiv.style.display = 'block';
  }
}
