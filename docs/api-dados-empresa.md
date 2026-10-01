# Toqqi · Dados da empresa e imagens (logo)

Mesmas convenções das etapas anteriores (base `/api/v1`, Bearer, erro `{"erro":{codigo,mensagem,campos}}`, RLS por conta).
Pedido do Marcelo em 01/10: a empresa que assina o Toqqi edita os próprios dados numa área logada (nome, razão social e CNPJ;
contato e endereço; logo). O logo aparece nas pesquisas e nos e-mails quando o formulário não tem logo próprio.
Também corrige o envio de logo por arquivo no editor de formulário, que hoje falha: a tela guardava a imagem como `data:` e a
API só aceita `https://` (422 "Use um endereço https://").

## 1. Banco (migração `0006_dados_empresa`)
`contas` ganha: `razao_social` (≤ 200), `documento` (só dígitos: CPF 11 ou CNPJ 14, CHECK de formato), `telefone` (10–13 dígitos,
com 55), `email_contato` citext, `site` (≤ 200), `cep` (8 dígitos), `logradouro` (≤ 150), `numero` (≤ 20), `complemento` (≤ 80),
`bairro` (≤ 80), `cidade` (≤ 80), `uf` (uma das 27 siglas), `dados_atualizados_em`. Tudo opcional; o `nome` continua obrigatório.

Tabela nova `imagens` (conta_id DEFAULT app_conta(), ENABLE + FORCE RLS, política padrão, grants condicionais):
`id, conta_id, uso ('logo_conta'|'logo_formulario'), formulario_id (FK composta, ON DELETE CASCADE; obrigatório só no uso
logo_formulario), chave (32+ caracteres aleatórios url-safe, UNIQUE), tipo ('image/png'|'image/jpeg'), dados bytea,
tamanho (≤ 307200), sha256, criada_em`. Uma imagem por uso: índice único parcial `(conta_id) WHERE uso = 'logo_conta'` e
`(formulario_id) WHERE uso = 'logo_formulario'`. Trocar = apagar a anterior e gravar outra com **chave nova** (a URL muda e os
caches se renovam sozinhos). A imagem não fica na tabela `contas` (que é lida a cada requisição).

## 2. Rotas
`DadosEmpresa` = `{nome, razao_social, documento, telefone, email_contato, site, cep, logradouro, numero, complemento, bairro,
cidade, uf, logo_url|null, atualizado_em|null}` (vazios como null; `documento`, `telefone` e `cep` só com dígitos).
- `GET /conta/dados` (`configuracoes.gerenciar`) → `DadosEmpresa`.
- `PUT /conta/dados` (`configuracoes.gerenciar`), corpo com todos os campos de texto (opcionais = null) → `DadosEmpresa`. Regras (422 com
  `campos`, mensagens simples): nome 2–120 ("Informe o nome da empresa."); documento CPF ou CNPJ com dígitos verificadores (aceita
  máscara; "CNPJ ou CPF inválido. Confira os números."); telefone com DDD (regra dos contatos); e-mail válido; site aceita sem
  `https://` (vira `https://...`), só http/https, nome com ponto, ≤ 200 ("Informe um site válido, como www.suaempresa.com.br.");
  CEP com 8 dígitos (aceita hífen); UF da lista; limites de tamanho. Auditoria `dados_empresa_alterados` com a lista dos campos
  que mudaram (sem os valores). O nome novo vale na hora em `{empresa}`, assuntos, rodapé dos e-mails, WhatsApp e remetente
  (quando `remetente_nome` está vazio).
- `PUT /conta/logo` (`configuracoes.gerenciar`), multipart `arquivo` → `DadosEmpresa`. PNG ou JPEG conferido pelos primeiros
  bytes (não pela extensão), até 300 KB; senão 422 `{arquivo: "Use uma imagem PNG ou JPG de até 300 KB."}`. Auditoria `logo_alterado`.
- `DELETE /conta/logo` (`configuracoes.gerenciar`) → 204. Auditoria `logo_removido`.
- `POST /formularios/{id}/logo` (`formularios.editar`), multipart `arquivo` → `{logo_url}`. Guarda o logo do formulário (troca o
  anterior) e devolve a URL pública; o editor põe a URL em `tema.logo_url`, que só muda de fato quando o formulário é salvo.
  Mesmas regras de tipo e tamanho. 404 se o formulário não é da conta.
- `tema.logo_url` (validação da etapa 2) aceita `https://...` como hoje **ou** uma URL de imagem da própria plataforma
  (`{API_PUBLIC_URL}/api/v1/publico/imagens/{chave}`, também com `http://` em desenvolvimento). `data:` continua recusado.
- `GET /publico/imagens/{chave}` (sem login) → a imagem, com `Content-Type` do tipo, `Cache-Control: public, max-age=31536000,
  immutable`, `ETag` = sha256, `X-Content-Type-Options: nosniff`; responde 304 a `If-None-Match` igual; 404 se a chave não existe.
  Busca a conta em modo sistema só pela chave. Limite alto por IP (600/min), porque os e-mails abrem pelo proxy de imagens do Gmail.
- `GET /eu` → `conta` ganha `logo_url`.

## 3. Onde o logo aparece
- Páginas públicas de pesquisa (`/publico/convites/{token}`, `/publico/formularios/{codigo}`): `formulario.tema.logo_url` = logo do
  formulário; se vazio, o logo da conta (se houver).
- E-mails de pesquisa (convite, lembrete, agradecimento e o e-mail de teste): cabeçalho com o logo do formulário do convite, senão o
  da conta; `alt` = nome da conta; altura até 48 px; sem logo, o e-mail fica como hoje. A URL é absoluta (`API_PUBLIC_URL`).

## 4. Telas
- **Configurações › Empresa** (`/configuracoes/empresa`, primeiro item da navegação de Configurações; perfil admin): cartões
  Identificação (Nome, com a explicação de que aparece nas pesquisas e e-mails; Razão social; CNPJ com máscara, aceita CPF),
  Contato (Telefone/WhatsApp com máscara, E-mail, Site), Endereço (CEP com máscara e preenchimento automático pelo ViaCEP — só
  campos vazios, com tempo limite; se falhar, segue manual —, Logradouro, Número, Complemento, Bairro, Cidade, UF) e Logo
  (prévia em fundo claro e escuro, Enviar/Trocar, Remover com confirmação, formato e tamanho aceitos). Barra "Salvar alterações /
  Descartar" e aviso ao sair com alterações não salvas. Salvou: o nome no topo do app atualiza.
- **Editor de formulário › Aparência**: enviar arquivo usa `POST /formularios/{id}/logo` (PNG/JPG até 300 KB) e põe a URL devolvida
  no tema; sem logo no formulário, a prévia mostra o logo da conta com o aviso "Usando o logo da empresa".
- Tudo funciona no celular, em tema claro e escuro, sem erros no console.

## 5. Ajustes feitos na construção
- `ETag` vai entre aspas (exigência do HTTP); `If-None-Match` aceita com ou sem aspas, `W/`, listas e `*`.
- Se o `tema.logo_url` salvo aponta para uma imagem da plataforma que não existe mais (logo trocado no editor e formulário
  descartado) ou de outra conta, a pesquisa e o e-mail usam o logo da conta em vez de uma imagem quebrada; o editor avisa
  quando a imagem não carrega.
- Duplicar um formulário copia o logo enviado com chave nova (trocar o logo de um não apaga o do outro).
- `PUT /conta/dados`: campo opcional ausente ou null é apagado; salvar sem mudança não grava nem audita. Trocar ou remover o
  logo também atualiza `atualizado_em`. `logo_alterado` guarda tipo e tamanho; o envio de logo de formulário não é auditado.
- Mensagens que o contrato não trazia: nome longo "Use no máximo 120 caracteres."; CEP "Informe o CEP com 8 números, como
  01310-100."; UF "Escolha um estado (UF) da lista.".
- O login (`POST /auth/entrar`) também devolve `conta.logo_url`, como o `GET /eu`.
- A prévia do e-mail em Configurações › Envios mostra o cabeçalho com o logo (do formulário dos convites, senão o da empresa).
