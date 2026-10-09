import json
from portal_theme import apply_theme


def _script_value(value: str) -> str:
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render_login_page(next_path: str, prefix: str) -> str:
    return apply_theme(LOGIN_PAGE).replace("__NEXT_PATH__", _script_value(next_path)).replace(
        "__PREFIX__", _script_value(prefix)
    )


LOGIN_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>登录 · Amazon 工具中心</title>
__THEME_CSS__
__THEME_INIT__
<style>
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; min-width: 0; }
body {
  min-height: 100vh;
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 72px 32px 32px;
  background: var(--page-bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.login-toolbar { position: absolute; top: 24px; right: 24px; }
.login-shell {
  width: min(920px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 390px);
  gap: clamp(48px, 8vw, 96px);
  align-items: center;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  color: var(--heading);
  font-size: 16px;
  font-weight: 700;
}
.brand-mark {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--blue);
  background: var(--surface);
}
.brand-mark svg { width: 20px; height: 20px; }
.intro h1 {
  max-width: 520px;
  margin: 54px 0 18px;
  color: var(--heading);
  font-size: 42px;
  line-height: 1.25;
  letter-spacing: 0;
}
.intro p {
  max-width: 460px;
  margin: 0;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.8;
}
.form-section {
  padding: 36px 0 36px 48px;
  border-left: 1px solid var(--soft-border);
}
.form-section h2 {
  margin: 0 0 10px;
  color: var(--heading);
  font-size: 26px;
  line-height: 1.3;
  letter-spacing: 0;
}
.form-section > p {
  margin: 0 0 30px;
  color: var(--muted);
  font-size: 13px;
  line-height: 1.7;
}
form { display: flex; flex-direction: column; }
label {
  margin-bottom: 9px;
  color: var(--text);
  font-size: 13px;
  font-weight: 600;
}
input {
  width: 100%;
  min-height: 48px;
  margin: 0 0 22px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 7px;
  outline: none;
  background: var(--surface);
  color: var(--heading);
  font: inherit;
}
input::placeholder { color: var(--subtle); }
input:hover { border-color: var(--blue); }
input:focus-visible { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.18); }
.password-field { position: relative; }
.password-field input { padding-right: 52px; }
.reveal-button {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.reveal-button:hover { background: var(--hover-bg); color: var(--heading); }
.reveal-button:focus-visible, .submit-button:focus-visible {
  outline: 2px solid var(--blue);
  outline-offset: 2px;
}
.reveal-button svg { width: 19px; height: 19px; }
[hidden] { display: none !important; }
.error {
  min-height: 21px;
  margin: -7px 0 12px;
  color: var(--red);
  font-size: 13px;
  line-height: 1.6;
}
.submit-button {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 16px;
  border: 1px solid var(--success-border);
  border-radius: 7px;
  background: var(--success-bg);
  color: var(--on-success);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}
.submit-button:hover:not(:disabled) { background: var(--success-bg); }
.submit-button:disabled { cursor: wait; opacity: 0.7; }
.submit-button svg { width: 18px; height: 18px; }
@media (max-width: 720px) {
  body { place-items: start center; padding: 80px 24px 30px; }
  .login-shell { grid-template-columns: 1fr; gap: 30px; }
  .intro h1 { margin-top: 32px; font-size: 32px; }
  .intro p { font-size: 14px; }
  .form-section { padding: 30px 0 0; border-left: 0; border-top: 1px solid var(--soft-border); }
}
@media (max-width: 360px) {
  body { padding: 80px 18px 24px; }
  .intro h1 { font-size: 29px; }
  .form-section h2 { font-size: 23px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
</style>
</head>
<body>
<div class="login-toolbar">__THEME_BUTTON__</div>
<main class="login-shell">
  <section class="intro" aria-labelledby="portal-title">
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-1.7-1-4.3-1-6 0Z"/><path d="m2 16 3-8 3 8c-1.7-1-4.3-1-6 0Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h18"/></svg>
      </span>
      <span>Amazon Tools Portal</span>
    </div>
    <h1 id="portal-title">回到你的<br>运营工作空间。</h1>
    <p>集中查看项目状态，进入 Amazon 运营工具，并管理服务运行状态。</p>
  </section>
  <section class="form-section" aria-labelledby="login-title">
    <h2 id="login-title">登录 Amazon 工具中心</h2>
    <p>使用已配置的门户账号继续。</p>
    <form id="login-form">
      <label for="username">账号</label>
      <input id="username" name="username" autocomplete="username" required autofocus>
      <label for="password">密码</label>
      <div class="password-field">
        <input id="password" name="password" type="password" autocomplete="current-password" required>
        <button class="reveal-button" id="reveal-password" type="button" aria-label="显示密码" aria-controls="password" aria-pressed="false" title="显示密码">
          <svg class="eye-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.1 12a10.8 10.8 0 0 1 19.8 0 10.8 10.8 0 0 1-19.8 0Z"/><circle cx="12" cy="12" r="3"/></svg>
          <svg class="eye-closed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" hidden><path d="m2 2 20 20"/><path d="M6.7 6.7A11 11 0 0 0 2.1 12a10.8 10.8 0 0 0 15.2 5.3"/><path d="M10.7 4.1A10.8 10.8 0 0 1 21.9 12a10.9 10.9 0 0 1-2.2 3.2"/></svg>
        </button>
      </div>
      <p class="error" id="login-error" role="alert" aria-live="polite"></p>
      <button class="submit-button" id="login-submit" type="submit">
        <span id="submit-label">登录</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>
      </button>
    </form>
  </section>
</main>
<script>
const nextPath = __NEXT_PATH__;
const prefix = __PREFIX__;
const form = document.getElementById('login-form');
const password = document.getElementById('password');
const reveal = document.getElementById('reveal-password');
const error = document.getElementById('login-error');
const submit = document.getElementById('login-submit');
const submitLabel = document.getElementById('submit-label');

reveal.addEventListener('click', () => {
  const showing = password.type === 'password';
  password.type = showing ? 'text' : 'password';
  reveal.setAttribute('aria-label', showing ? '隐藏密码' : '显示密码');
  reveal.setAttribute('title', showing ? '隐藏密码' : '显示密码');
  reveal.setAttribute('aria-pressed', String(showing));
  reveal.querySelector('.eye-open').hidden = showing;
  reveal.querySelector('.eye-closed').hidden = !showing;
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  error.textContent = '';
  submit.disabled = true;
  submitLabel.textContent = '登录中';
  form.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(prefix + '/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        username: form.username.value,
        password: password.value,
        next: nextPath,
      }),
    });
    if (!response.ok) throw new Error(response.status === 401 ? '账号或密码不正确' : '登录失败，请稍后重试');
    const result = await response.json();
    location.assign(result.redirect);
  } catch (failure) {
    error.textContent = failure.message || '登录失败，请稍后重试';
    password.value = '';
    password.focus();
  } finally {
    submit.disabled = false;
    submitLabel.textContent = '登录';
    form.removeAttribute('aria-busy');
  }
});
</script>
</body>
</html>"""
