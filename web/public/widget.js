/*! Toqqi widget: <script src="https://SEU-APP/widget.js" data-toqqi="CODIGO" async></script> */
(function (w, d) {
  if (w.Toqqi && w.Toqqi.abrir) return;
  var s = d.currentScript || d.querySelector('script[data-toqqi]');
  var codigo = s && s.getAttribute('data-toqqi');
  if (!codigo) return;
  var origem;
  try { origem = new URL(s.src, w.location.href).origin; } catch (e) { origem = w.location.origin; }
  var cor = /^#[0-9a-f]{3,8}$/i.test(s.getAttribute('data-cor') || '') ? s.getAttribute('data-cor') : '#d63a18';
  var texto = s.getAttribute('data-texto') || 'Avalie-nos';
  var lado = /^(esquerda|left)$/i.test(s.getAttribute('data-posicao') || '') ? 'left' : 'right';
  var url = origem + '/f/' + encodeURIComponent(codigo) + '?canal=widget&embed=1';
  var P = 'toqqi-w';
  var css = d.createElement('style');
  css.textContent =
    '.' + P + '-b{position:fixed;bottom:20px;' + lado + ':20px;z-index:2147483000;border:0;border-radius:999px;padding:12px 20px;' +
    'font:600 15px/1.2 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#fff;background:' + cor + ';box-shadow:0 6px 20px rgba(0,0,0,.2);cursor:pointer}' +
    '.' + P + '-b:focus-visible{outline:3px solid #111;outline-offset:3px}' +
    '.' + P + '-o{position:fixed;inset:0;z-index:2147483001;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;padding:16px}' +
    '.' + P + '-m{position:relative;width:100%;max-width:560px;height:min(640px,90vh);background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.3)}' +
    '.' + P + '-m iframe{width:100%;height:100%;border:0;display:block}' +
    '.' + P + '-x{position:absolute;top:8px;right:8px;width:36px;height:36px;border:0;border-radius:10px;background:rgba(255,255,255,.9);font:20px/1 system-ui;color:#334155;cursor:pointer}' +
    '@media (max-width:640px){.' + P + '-o{padding:0}.' + P + '-m{max-width:none;height:100%;border-radius:0}}';
  var botao = d.createElement('button');
  botao.type = 'button';
  botao.className = P + '-b';
  botao.textContent = texto;
  botao.setAttribute('aria-haspopup', 'dialog');
  var fundo = null, anterior = null, estilo = '';

  function tecla(e) { if (e.key === 'Escape' || e.key === 'Esc') fechar(); }

  function abrir() {
    if (fundo) return;
    anterior = d.activeElement;
    fundo = d.createElement('div');
    fundo.className = P + '-o';
    var m = d.createElement('div');
    m.className = P + '-m';
    m.setAttribute('role', 'dialog');
    m.setAttribute('aria-modal', 'true');
    m.setAttribute('aria-label', texto);
    var f = d.createElement('iframe');
    f.src = url;
    f.title = texto;
    f.setAttribute('allow', 'clipboard-write');
    var x = d.createElement('button');
    x.type = 'button';
    x.className = P + '-x';
    x.setAttribute('aria-label', 'Fechar');
    x.innerHTML = '&times;';
    x.onclick = fechar;
    m.appendChild(f);
    m.appendChild(x);
    fundo.appendChild(m);
    fundo.addEventListener('click', function (e) { if (e.target === fundo) fechar(); });
    d.addEventListener('keydown', tecla);
    estilo = d.body.style.overflow;
    d.body.style.overflow = 'hidden';
    d.body.appendChild(fundo);
    botao.setAttribute('aria-expanded', 'true');
    x.focus();
  }

  function fechar() {
    if (!fundo) return;
    d.removeEventListener('keydown', tecla);
    fundo.parentNode && fundo.parentNode.removeChild(fundo);
    fundo = null;
    d.body.style.overflow = estilo;
    botao.setAttribute('aria-expanded', 'false');
    if (anterior && anterior.focus) anterior.focus();
  }

  botao.onclick = abrir;
  function montar() { d.head.appendChild(css); d.body.appendChild(botao); }
  if (d.body) montar(); else d.addEventListener('DOMContentLoaded', montar);
  w.Toqqi = { abrir: abrir, fechar: fechar };
})(window, document);
