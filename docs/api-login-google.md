# Entrar com o Google

Pedido do Marcelo (08/10/2026, 10h56): "implementar login com google". Nas telas de entrada e de cadastro, "Continuar
com o Google". Quem já tem usuário entra direto; quem não tem cria a conta só com o nome da empresa e o aceite (o e-mail
vem confirmado pelo Google). A entrada com e-mail e senha continua igual.

Revisão de 13/10/2026 ("melhore o botão entrar com google"): o botão passou a ser do Toqqi (abaixo, "Site"). Antes era
o botão oficial do Google, num iframe: mais baixo que os outros (40 px), de cantos retos, com a letra do Google, "Fazer
Login" com L maiúsculo e, com a pessoa logada no Google, trocava sozinho para "Fazer login como Fulano" com a foto.

## Como funciona

- O site carrega o script do Google (Google Identity Services, `https://accounts.google.com/gsi/client`) só nas telas
  de entrar e de cadastro. O clique no botão abre a janela do Google (o **modelo de token**,
  `google.accounts.oauth2.initTokenClient`, escopos `openid email profile`, sempre com a escolha da conta). Escolhida a
  conta, o Google devolve ao site um **token de acesso**, que vai para a API.
- O token de acesso não é assinado para o Toqqi: quem confirma é o próprio Google. A API manda o token no corpo de um
  POST para `GOOGLE_TOKENINFO_URL` (nunca na URL) e só aceita o token **emitido para o nosso ID do cliente** (`aud` e
  `azp` iguais a `GOOGLE_CLIENT_ID`), ainda válido (`expires_in` > 0), com `sub` e e-mail verificado pelo Google. Um
  token que outro app recebeu da mesma pessoa não entra. Para quem ainda não tem conta, o nome vem do
  `GOOGLE_USERINFO_URL` (se falhar, fica em branco e a pessoa digita).
- O caminho antigo continua valendo (abas abertas com o site de antes): o token de identidade (JWT assinado pelo
  Google) conferido com as chaves públicas do Google (`GOOGLE_CHAVES_URL`, em cache pelo tempo que o Google indica):
  assinatura RS256, emissor `accounts.google.com`, destinatário igual a `GOOGLE_CLIENT_ID`, validade (60 s de
  tolerância) e e-mail verificado.
- **Não há segredo do cliente** nem token do Google guardado. Do Google, o Toqqi guarda só o `sub` (o identificador da
  conta do Google) em `usuarios.google_sub`, na primeira entrada (migração `0029_login_google`).

## API

- `GET /auth/google/config` → `{client_id}` (null = sem o botão). Público, `Cache-Control: public, max-age=300`.
- `POST /auth/google` `{token_acesso, lembrar}` (o botão do Toqqi) ou `{credencial, lembrar}` (o token de identidade
  do botão oficial, de antes); um dos dois, senão 422 (limite da entrada: 5 por minuto):
  - **usuário encontrado** (primeiro pela conta do Google já ligada; senão pelo e-mail) → a sessão, igual à de
    `POST /auth/entrar`. Na primeira vez, liga a conta do Google ao usuário (auditoria `login_google_ligado`) e, se o
    e-mail ainda não estava confirmado, confirma. A auditoria `login_ok` leva `metodo: "google"`.
  - **sem usuário** → `{novo: true, cadastro, email, nome}`: `cadastro` é um token de 15 minutos (HS256 com uma chave
    derivada do JWT_SECRET, que não vale como sessão) para terminar o cadastro sem o Google de novo. Nada é criado.
  - Recusas: 409 `google_outra_conta` (o usuário já está ligado a outra conta do Google; auditoria
    `login_google_recusado`), 403 `acesso_pendente` e `acesso_bloqueado` (como na senha; o pedido de acesso pendente tem
    o e-mail confirmado pelo Google e os administradores são avisados, como na confirmação por e-mail), 401
    `google_invalido` (token inválido, vencido ou de outro app), 403 `google_email_nao_verificado`, 503
    `google_fora_do_ar` (o Google não respondeu), 404 `google_desligado` (sem `GOOGLE_CLIENT_ID`).
- `POST /auth/google/cadastro` `{cadastro, empresa, nome, telefone?, aceite_termos: true, origem?}` → 201 com a
  sessão: conta nova em teste (como o cadastro com senha), usuário administrador com o e-mail confirmado e a conta do
  Google ligada, aceite dos termos, auditoria `cadastro_conta` com `metodo: "google"` e registro de acesso `cadastro`.
  A senha é aleatória (ninguém sabe); para usar senha, "Esqueci a senha". 400 `cadastro_vencido` (token inválido ou
  passou dos 15 minutos); 409 `email_em_uso` (o e-mail ou a conta do Google já têm usuário).

## Site

- **O botão** (`web/src/modulos/acesso/BotaoGoogle.vue`): "Continuar com o Google", o botão secundário do Toqqi no
  tamanho do "Entrar" (48 px, cantos arredondados, a letra do site, largura toda), claro ou escuro como a tela. Segue as
  regras de marca do Google: o "G" original (`URL_LOGO_GOOGLE`, a imagem servida pelo próprio Google, sem enviar a
  página de origem) e o texto oficial em português, que vale para quem já tem conta e para quem vai criar.
- Ao clicar: a janela do Google. Enquanto a API confere, o botão fica apagado com "Entrando com o Google…". Janela
  fechada ou recusada ("access_denied"): nada muda. Janela bloqueada pelo navegador: "O navegador bloqueou a janela do
  Google. Permita janelas pop-up neste site e tente de novo." Outro erro: "Não deu para entrar com o Google agora…".
- O botão aparece assim que a API dá o ID do cliente (sem pular a tela quando o script do Google termina de carregar);
  clique antes do script pronto não faz nada.
- **Entrar**: o botão no alto, "ou entre com seu e-mail" e o formulário de sempre. O "Lembrar de mim neste aparelho"
  vale também para o Google. Quem não tem conta vai para o cadastro, no passo "Falta pouco".
- **Cadastro**: o botão no alto, "ou cadastre com seu e-mail". Quem já tem conta entra direto. Quem não tem vê **Falta
  pouco**: o e-mail do Google, o nome (já preenchido pelo Google), o nome da empresa, o WhatsApp (opcional) e o aceite;
  "Começar 14 dias grátis" cria a conta e já entra. "Usar outro e-mail" volta ao cadastro normal. O token pendente fica
  só na memória da página.
- Sem `GOOGLE_CLIENT_ID`, ou se o script do Google não carregar (bloqueador, sem internet), as telas ficam como antes,
  sem o botão nem o "ou".

## Política de privacidade (versão 8)

A Política passou a dizer o que o Google envia (nome, e-mail e o identificador da conta, só se a pessoa usar o botão;
nunca a senha nem acesso ao Gmail, Drive, agenda ou contatos), o Google na lista de fornecedores (Estados Unidos) e que
o botão é carregado do Google nas telas de entrar e de cadastro (com os cookies do Google). Os Termos não mudaram.
`VERSAO_DOCUMENTOS` subiu para 8 (vigente desde 08/10/2026): **todo mundo vê a tela de aceite de novo**, como nas
versões anteriores.

## Configurar no Google Cloud (uma vez)

1. Em https://console.cloud.google.com, crie (ou escolha) o projeto "Toqqi".
2. Em **APIs e serviços › Tela de consentimento OAuth** (ou **Google Auth Platform › Branding**): nome "Toqqi", e-mail
   de suporte, logo (opcional), domínio autorizado `toqqi.com`, página inicial `https://toqqi.com`, política de
   privacidade `https://toqqi.com/privacidade` e termos `https://toqqi.com/termos`. Público: **Externo**. Publique o
   app (**Em produção**). Os escopos são só os básicos (openid, e-mail e perfil): não precisam de verificação do Google.
3. Em **APIs e serviços › Credenciais › Criar credenciais › ID do cliente OAuth**: tipo **Aplicativo da Web**, nome
   "Toqqi site". Em **Origens JavaScript autorizadas**: `https://toqqi.com`, `https://toqqi-web.onrender.com` (o endereço
   antigo, que continua abrindo o site) e, para testar no computador, `http://localhost:5173` e `http://localhost`. Não
   precisa de URI de redirecionamento.
4. Copie o **ID do cliente** (termina em `.apps.googleusercontent.com`). **Não precisa da chave secreta do cliente.**
5. No Render, em **toqqi-api › Environment**, crie `GOOGLE_CLIENT_ID` com esse ID e salve (o Render publica de novo).
   O site lê o ID da API: não precisa mexer no toqqi-web.

## Testes

- `api/tests/test_login_google.py`: configuração, entrada de quem tem usuário (liga a conta do Google; a senha continua
  valendo; chaves em cache), outra conta do Google recusada e entrada pela conta ligada mesmo com outro e-mail, tokens
  inválidos (destinatário, emissor, vencido, chave desconhecida, outra assinatura, HS256, lixo), e-mail não
  verificado, Google fora do ar, cadastro completo (sessão, conta, usuário, origem, auditoria, aceite) e repetido,
  token de cadastro inválido, de sessão ou vencido, pedido de acesso pendente e usuário bloqueado. Token de acesso:
  quem tem conta entra (só o tokeninfo, com o token no corpo do POST), quem não tem recebe o nome do userinfo (e em
  branco se o userinfo falhar ou for de outra conta), recusas (outro app no `aud` ou no `azp`, vencido, sem `sub`, sem
  e-mail verificado, token que o Google não conhece), Google fora do ar, um token só e Google desligado.
- `web/tests/loginGoogle.test.ts`: ID e script carregados uma vez (e de novo depois de falhar), o botão (tamanho, "G",
  texto), a janela do Google (escopos, token, "Entrando com o Google…", fechada, recusada, bloqueada, erro), o botão
  antes do script pronto e sem o script, as duas telas, a sessão com o "lembrar", o "Falta pouco" (validação,
  cadastro, token vencido, "Usar outro e-mail") e a Política na versão 8.
