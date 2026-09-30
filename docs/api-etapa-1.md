# Toqqi · API da etapa 1 (acesso, equipe, sessões, auditoria)

Base: `/api/v1`. JSON em UTF-8. Autenticação: cabeçalho `Authorization: Bearer <token>`.
Erros: `{"erro": {"codigo": "<slug>", "mensagem": "<texto para mostrar ao usuário>", "campos": {"<campo>": "<mensagem>"}}}`.

| Status | Significado | O que a tela faz |
|---|---|---|
| 401 `sessao_invalida` | sessão expirada, encerrada ou usuário bloqueado | apaga o token, vai para /entrar e mostra `mensagem` |
| 403 `sem_permissao` | perfil não pode | mostra aviso, continua logado |
| 409, 422 | regra ou validação | mostra `mensagem` e, se houver, `campos` ao lado de cada campo |
| 429 `muitas_tentativas` | limite de tentativas | "Muitas tentativas. Aguarde um minuto." |

## Perfis e permissões
Perfis: `admin`, `gestor`, `consulta`. Superadmin da plataforma é um sinal à parte (`superadmin: true`).

Permissões (strings): `painel.ver`, `painel.exportar`, `contatos.ver`, `contatos.editar`, `contatos.excluir`,
`importacao.usar`, `envios.ver`, `envios.disparar`, `formularios.ver`, `formularios.editar`, `respostas.ver`,
`respostas.editar`, `acoes.ver`, `acoes.tratar`, `acoes.excluir`, `relatorios.ver`, `equipe.gerenciar`,
`configuracoes.gerenciar`, `assinatura.gerenciar`, `auditoria.ver`, `zona_risco.usar`.

`admin` tem todas. `gestor` e `consulta` têm um padrão que o admin ajusta em Permissões
(nunca recebem `equipe.gerenciar`, `configuracoes.gerenciar`, `assinatura.gerenciar`, `auditoria.ver`, `zona_risco.usar`).

## Rotas públicas
- `POST /auth/cadastro` `{empresa, nome, email, senha, telefone?, aceite_termos: true}` → 201 `{mensagem}`. Cria conta em teste (14 dias) e o admin; envia e-mail de confirmação.
- `POST /auth/entrar` `{email, senha, lembrar: bool}` → 200 `Sessao` · 401 `credenciais_invalidas` ("E-mail ou senha incorretos.") · 403 `email_nao_confirmado` · 403 `acesso_pendente` · 403 `acesso_bloqueado`.
- `POST /auth/confirmar-email` `{token}` → 200 `{mensagem}` · 400 `link_invalido`.
- `POST /auth/reenviar-confirmacao` `{email}` → 200 `{mensagem}` (sempre igual).
- `POST /auth/esqueci-senha` `{email}` → 200 `{mensagem}` (sempre igual).
- `POST /auth/redefinir-senha` `{token, senha}` → 200 `{mensagem}` · 400 `link_invalido` · 422 senha fraca.
- `POST /auth/pedir-acesso` `{nome, email, senha}` → 200 `{mensagem}` (sempre igual; só cria se o domínio for liberado por uma conta).
- `GET /auth/regras-senha` → `{minimo: 8, maximo: 70, exige: ["maiuscula","numero","simbolo"]}`.

## Sessão e usuário logado
`Sessao` = `{token, expira_em (ISO), usuario: Usuario, conta: Conta, permissoes: [string]}`.
`Usuario` = `{id, nome, email, cargo, perfil, situacao: "ativo"|"pendente"|"bloqueado", email_confirmado, ultimo_acesso, superadmin}`.
`Conta` = `{id, nome, plano, situacao, teste_ate}`.

- `GET /eu` → `{usuario, conta, permissoes}`.
- `PATCH /eu` `{nome?, cargo?}` → `Usuario`.
- `POST /eu/senha` `{senha_atual, senha_nova}` → 200 (encerra as outras sessões).
- `POST /auth/sair` → 204 (encerra a sessão atual).
- `GET /eu/sessoes` → `[{id, aparelho, ip, criada_em, ultimo_uso, atual: bool}]`.
- `DELETE /eu/sessoes/{id}` → 204 · `POST /eu/sessoes/encerrar-outras` → 204.

## Equipe (`equipe.gerenciar`)
- `GET /equipe` → `[Usuario]`.
- `POST /equipe` `{nome, email, cargo?, perfil, senha}` → 201 `Usuario` (entra ativo e confirmado) · 409 `email_em_uso`.
- `PATCH /equipe/{id}` `{nome?, cargo?, perfil?, situacao?}` → `Usuario` · 409 `nao_pode_si_mesmo` (mudar o próprio perfil/situação) · 409 `ultimo_admin`.
- `DELETE /equipe/{id}` → 204 · 409 `nao_pode_si_mesmo` · 409 `ultimo_admin`.
- `POST /equipe/{id}/reenviar-confirmacao` → 200.
- `GET /equipe/permissoes` → `{catalogo: [{chave, rotulo, grupo, somente_admin}], gestor: [string], consulta: [string]}`.
- `PUT /equipe/permissoes` `{gestor: [string], consulta: [string]}` → mesmo formato.

## Segurança da conta (`configuracoes.gerenciar`)
- `GET /conta/seguranca` → `{sessao_minutos, dominios: [string]}`.
- `PUT /conta/seguranca` `{sessao_minutos (30–1440), dominios: [string]}` → mesmo formato · 422 com `campos.dominios` (e-mail gratuito, formato, domínio de outra conta).

## Auditoria (`auditoria.ver`)
- `GET /auditoria?de=YYYY-MM-DD&ate=YYYY-MM-DD&gravidade=&busca=&pagina=1` → `{itens: [{id, criado_em, evento, rotulo, gravidade: "info"|"sucesso"|"atencao"|"erro", usuario: {id, nome}|null, detalhe, ip}], total, pagina, por_pagina}`.

## Plataforma (superadmin)
- `GET /plataforma/contas` → `[{id, nome, plano, situacao, teste_ate, usuarios, criada_em}]`.
- `POST /plataforma/contas` `{empresa, admin_nome, admin_email, admin_senha, situacao: "teste"|"cortesia"}` → 201.
- `POST /plataforma/contas/{id}/estender-teste` `{dias: 14}` → conta (conta a partir do fim do teste atual).
- `POST /plataforma/contas/{id}/cortesia` → conta.
