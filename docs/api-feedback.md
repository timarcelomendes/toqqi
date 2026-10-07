# Feedback: erros, sugestões, melhorias e elogios para a equipe Toqqi

Pedido do Marcelo (06/10/2026, 21h55): "Preciso criar um report de erro, sugestão, elogios e melhorias para o usuário
logado". Respostas dele (todas as recomendadas): **situação e conversa** (a pessoa acompanha e conversa com a equipe),
**até 3 imagens** por mensagem, **e-mail na hora** para os superadmins e **elogio pode virar depoimento** com
autorização.

## 1. O que é

- Qualquer usuário logado (todos os perfis, também com o teste encerrado ou o pagamento atrasado) manda um feedback:
  **Algo deu errado** (`erro`), **Tenho uma ideia** (`sugestao`), **Dá para melhorar** (`melhoria`) ou **Gostei!**
  (`elogio`).
- O botão **Feedback** fica no rodapé do menu, embaixo de Ajuda, e abre a janela por cima da tela atual (leva o
  caminho e o título dela). Em **Seus feedbacks** (`/feedback`) a pessoa vê os dela, a situação e a conversa
  (`/feedback/:id`, o link dos e-mails).
- A equipe Toqqi (superadmins, `SUPERADMIN_EMAILS`) trabalha em **Plataforma › Feedback** (`/plataforma/feedback` e
  `/plataforma/feedback/:id`).
- Só a pessoa e a equipe Toqqi veem um feedback (nem o administrador da conta vê o feedback de outra pessoa).

## 2. Regras

### 2.1 Tipos, situações e impacto
- Situações: `recebido` (padrão), `em_analise`, `planejado`, `concluido`, `encerrado`. "Abertos" = as três primeiras.
- Impacto, só no erro e opcional: `bloqueia` (Impede o trabalho), `atrapalha`, `detalhe`. O e-mail da equipe de um erro
  `bloqueia` começa com "[Impede o trabalho]".
- `autoriza_depoimento`, só no elogio: a pessoa autoriza usar o texto no site do Toqqi com o nome e a empresa; pode
  retirar depois (PATCH). Nada é publicado sozinho: a Plataforma mostra "Copiar depoimento".

### 2.2 Texto e imagens
- Texto: até 5.000 caracteres, sem caracteres de controle (menos quebra de linha e tab), quebras normalizadas, sem
  espaços nas pontas, no máximo duas linhas em branco seguidas. O relato precisa de texto; uma mensagem depois precisa
  de texto ou imagem.
- Imagens: até 3 por mensagem e 12 por feedback; PNG ou JPG de até 1 MB (conferidos pelos bytes). O site converte o que
  o navegador abrir (WebP, GIF, HEIC, prints grandes) em PNG ou JPG de até 1 MB (até 1920 px; PNG primeiro quando a
  origem é PNG, depois JPG 0,85 → 0,75 → 0,7). Arquivos acima de 15 MB nem são abertos.
- As imagens são **privadas**: tabela própria (`feedback_imagens`), nunca por URL pública; o site busca como blob, com
  o token. A tarefa `limpeza` apaga as imagens dos feedbacks concluídos ou encerrados sem atividade há mais de 180 dias
  (até 2.000 por rodada; a conversa fica).
- Limites por usuário: 5 feedbacks por minuto, 30 por hora e 100 por dia; 10 mensagens por minuto e 120 por hora.
  Conversa com 200 mensagens: 409 `limite_mensagens`; 12 imagens: 409 `limite_imagens`.

### 2.3 Contexto e diagnóstico
- Sempre: `pagina` (o caminho, sem query nem hash, até 200) e `pagina_titulo` (o título da tela). Em Seus feedbacks,
  vale a tela anterior quando o navegador sabe qual foi.
- Só no erro e com **Enviar detalhes técnicos** marcado (padrão): `navegador` (User-Agent, pela API), `tela`
  ("1280x900"), `versao_site` e `diagnostico` = os últimos 10 erros do site e os últimos 10 pedidos à API que falharam
  neste carregamento da página (`web/src/utils/diagnostico.ts`; método, caminho, status, código do erro e o request id
  — o mesmo do log e de Plataforma › Erros). O 401 fica de fora. A janela mostra "Ver o que vai junto".
- A API limpa tudo de novo (`regras.limpar_diagnostico`, com a limpeza do aviso de erros: sem e-mails, números longos,
  tokens nem texto entre aspas) e guarda no máximo 8 KB; o que vier fora do formato sai calado.

### 2.4 Marcas de leitura
- "Precisa de atenção" (Plataforma) = feedback que a equipe nunca abriu ou com mensagem da pessoa depois da última vez
  que a equipe abriu (`ultima_do_usuario_em` > `visto_pela_equipe_em`). Aparece como número na aba e ao lado de
  Plataforma no menu.
- "Resposta nova" (pessoa) = resposta ou mudança de situação da equipe depois da última vez que ela abriu a conversa
  (`ultima_da_equipe_em` > `visto_pelo_usuario_em`). Aparece como número ao lado de Feedback no menu.
- Abrir o detalhe (GET) marca como visto, dos dois lados; escrever também.

## 3. Rotas de quem usa (`requer()`, só os próprios feedbacks)

| Rota | O que faz |
|---|---|
| `GET /feedback` | `{itens, novidades}`: até 200, atividade mais recente primeiro. Item: `{id, tipo, situacao, impacto, autoriza_depoimento, trecho (160), mensagens (com texto), imagens, pagina_titulo, criado_em, atualizado_em, novidade}` |
| `GET /feedback/novidades` | `{novidades}` (o número do menu) |
| `POST /feedback` | multipart: `tipo`, `texto`, `impacto`, `autoriza_depoimento`, `detalhes` (padrão true), `pagina`, `pagina_titulo`, `tela`, `versao_site`, `diagnostico` (JSON), `imagens` (até 3). 201 com o detalhe |
| `GET /feedback/{id}` | `{id, tipo, situacao, impacto, autoriza_depoimento, pagina, pagina_titulo, criado_em, atualizado_em, mensagens}`; marca como visto. Mensagem: `{id, autor: usuario|equipe, autor_nome, texto, situacao, criado_em, imagens: [{id, tipo, tamanho, largura, altura, nome}]}` |
| `PATCH /feedback/{id}` | `{autoriza_depoimento}` (só elogio; outro tipo: 409 `nao_e_elogio`) |
| `POST /feedback/{id}/mensagens` | multipart: `texto` e/ou `imagens`. 201 com o detalhe |
| `GET /feedback/{id}/imagens/{imagem_id}` | os bytes (`Cache-Control: private, max-age=3600`, `nosniff`, CSP `default-src 'none'`) |

De outra pessoa (mesmo da mesma conta) ou inexistente: 404. Erros de campo: 422 `dados_invalidos` em `tipo`, `texto`,
`impacto` ou `imagens`.

## 4. Rotas da equipe (`requer_superadmin`, modo sistema)

| Rota | O que faz |
|---|---|
| `GET /plataforma/feedback?tipo=&situacao=abertos\|concluidos\|encerrados\|todos&busca=` | `{itens, contagem: {atencao, abertos}}`: até 300; busca na conta, no nome e e-mail de quem mandou e no texto de qualquer mensagem (`%` e `_` valem como texto). Item = o da pessoa + `conta_id, conta_nome, autor_nome, autor_email, atencao` |
| `GET /plataforma/feedback/contagem` | `{atencao, abertos}` |
| `GET /plataforma/feedback/{id}` | detalhe + `conta {id, nome, plano, situacao}`, `autor {id, nome, email, perfil, cargo, situacao}` (null se saiu da conta), `contexto {pagina, pagina_titulo, navegador, tela, versao_site, diagnostico}`, `nota_interna`; marca como visto pela equipe |
| `POST /plataforma/feedback/{id}/mensagens` | `{texto, situacao?}`: texto e/ou situação nova numa mensagem (o nome de quem respondeu fica guardado). Sem texto e sem situação diferente: 422 no `texto`. Com texto, e-mail para a pessoa |
| `PATCH /plataforma/feedback/{id}` | `{situacao?, nota_interna?}`: situação vira linha na conversa (sem e-mail); nota interna (até 5.000) só a equipe vê |
| `GET /plataforma/feedback/{id}/imagens/{imagem_id}` | os bytes |

## 5. E-mails

- **Feedback novo** → cada superadmin com o e-mail confirmado e ativo: "Feedback novo: Erro de Ana Souza, Alfa Ltda"
  (com "[Impede o trabalho]" na frente quando for o caso), quem mandou, a conta (plano e situação), o texto, impacto,
  tela, quantas imagens, a autorização do depoimento e o botão para a Plataforma.
- **Mensagem nova da pessoa** → os superadmins, só quando a equipe já tinha visto tudo até ali (senão o aviso anterior
  ainda está pendente): "Nova mensagem no feedback #12 de Ana Souza, Alfa Ltda".
- Esses dois não entram no registro de e-mails da conta (saem para a equipe Toqqi). No log, o assunto vira "Feedback #N".
- **Resposta da equipe** (só com texto) → a pessoa, se ativa, com e-mail confirmado e sem ter retirado o aceite dos
  termos: "A equipe Toqqi respondeu seu feedback", com o texto, a situação nova e o botão "Ver a conversa". Entra no
  registro de e-mails da conta como `feedback` ("Resposta da equipe Toqqi").

## 6. Banco (migração `0027_feedback`)

`feedbacks`, `feedback_mensagens` e `feedback_imagens`, com RLS por conta (FORCE), saem em cascata com a conta; as
chaves entre elas levam a conta junto, e a do usuário segue o padrão (`ON DELETE SET NULL (usuario_id)`: quem sai da
conta vira "Pessoa que saiu da conta" e não recebe mais e-mail). `emails_enviados.tipo` aceita `feedback`.

## 7. Fora (por enquanto)

- Votação pública de ideias e quadro de novidades (roadmap) entre clientes.
- Feedback na exportação de dados da conta (é conversa da pessoa com a equipe Toqqi, não dado da conta para o
  administrador).
- Print automático da tela (a pessoa cola ou anexa o print).
- "Relatar este erro" direto no aviso de erro das telas.
