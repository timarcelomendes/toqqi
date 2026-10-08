# Entrar com o Google

Pedido do Marcelo (08/10/2026, 10h56): "implementar login com google". Na tela de entrada, "Fazer login com o Google";
na de cadastro, "Continuar com o Google". Quem já tem usuário entra direto; quem não tem cria a conta só com o nome da
empresa e o aceite (o e-mail vem confirmado pelo Google). A entrada com e-mail e senha continua igual.

## Como funciona

- O site usa o botão oficial do Google (Google Identity Services, `https://accounts.google.com/gsi/client`, carregado
  só nas telas de entrar e de cadastro). Ao escolher a conta, o Google devolve ao site um token de identidade (JWT
  assinado pelo Google), que vai para a API.
- A API confere o token com as chaves públicas do Google (`GOOGLE_CHAVES_URL`, em cache pelo tempo que o Google
  indica): assinatura RS256, emissor `accounts.google.com`, destinatário igual a `GOOGLE_CLIENT_ID`, validade (60 s de
  tolerância) e e-mail verificado pelo Google.
- **Não há segredo do cliente** nem token do Google guardado. Do Google, o Toqqi guarda só o `sub` (o identificador da
  conta do Google) em `usuarios.google_sub`, na primeira entrada (migração `0029_login_google`).

## API

- `GET /auth/google/config` → `{client_id}` (null = sem o botão). Público, `Cache-Control: public, max-age=300`.
- `POST /auth/google` `{credencial, lembrar}` (limite da entrada: 5 por minuto):
  - **usuário encontrado** (primeiro pela conta do Google já ligada; senão pelo e-mail) → a sessão, igual à de
    `POST /auth/entrar`. Na primeira vez, liga a conta do Google ao usuário (auditoria `login_google_ligado`) e, se o
    e-mail ainda não estava confirmado, confirma. A auditoria `login_ok` leva `metodo: "google"`.
  - **sem usuário** → `{novo: true, cadastro, email, nome}`: `cadastro` é um token de 15 minutos (HS256 com uma chave
    derivada do JWT_SECRET, que não vale como sessão) para terminar o cadastro sem o Google de novo. Nada é criado.
  - Recusas: 409 `google_outra_conta` (o usuário já está ligado a outra conta do Google; auditoria
    `login_google_recusado`), 403 `acesso_pendente` e `acesso_bloqueado` (como na senha; o pedido de acesso pendente tem
    o e-mail confirmado pelo Google e os administradores são avisados, como na confirmação por e-mail), 401
    `google_invalido`, 403 `google_email_nao_verificado`, 503 `google_fora_do_ar` (sem as chaves do Google), 404
    `google_desligado` (sem `GOOGLE_CLIENT_ID`).
- `POST /auth/google/cadastro` `{cadastro, empresa, nome, telefone?, aceite_termos: true, origem?}` → 201 com a
  sessão: conta nova em teste (como o cadastro com senha), usuário administrador com o e-mail confirmado e a conta do
  Google ligada, aceite dos termos, auditoria `cadastro_conta` com `metodo: "google"` e registro de acesso `cadastro`.
  A senha é aleatória (ninguém sabe); para usar senha, "Esqueci a senha". 400 `cadastro_vencido` (token inválido ou
  passou dos 15 minutos); 409 `email_em_uso` (o e-mail ou a conta do Google já têm usuário).

## Site

- **Entrar**: o botão do Google no alto, "ou entre com seu e-mail" e o formulário de sempre. O "Lembrar de mim neste
  aparelho" vale também para o Google. Quem não tem conta vai para o cadastro, no passo "Falta pouco".
- **Cadastro**: "Continuar com o Google" no alto. Quem já tem conta entra direto. Quem não tem vê **Falta pouco**: o
  e-mail do Google, o nome (já preenchido pelo Google), o nome da empresa, o WhatsApp (opcional) e o aceite; "Começar
  14 dias grátis" cria a conta e já entra. "Usar outro e-mail" volta ao cadastro normal. O token pendente fica só na
  memória da página.
- Sem `GOOGLE_CLIENT_ID`, ou se o script do Google não carregar (bloqueador, sem internet), as telas ficam como antes,
  sem o botão nem o "ou".
- O botão é desenhado pelo Google (num iframe dele), no tema claro ou escuro do Toqqi.

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
  token de cadastro inválido, de sessão ou vencido, pedido de acesso pendente e usuário bloqueado.
- `web/tests/loginGoogle.test.ts`: ID e script carregados uma vez (e de novo depois de falhar), as duas telas com e sem
  o ID, a sessão com o "lembrar", o "Falta pouco" (validação, cadastro, token vencido, "Usar outro e-mail") e a
  Política na versão 8.
