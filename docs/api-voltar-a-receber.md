# Voltar a receber sem achar o e-mail antigo: página /sair e VOLTAR no WhatsApp

Pedido do Marcelo (07/10/2026, 09h32): "o cliente pode desejar não receber e-mails da Toqqi, mas para voltar ele terá
que ir no e-mail e localizar". Para os usuários da Toqqi isso já existia (resumo semanal e alertas em Minha conta ›
E-mails); o pedido é do cliente que responde as pesquisas. Respostas dele: a opção fica na **parte pública, sem
login**, "para que qualquer pessoa consiga cadastrar e descadastrar"; e **VOLTAR no WhatsApp**. "Cadastrar" aqui é
voltar a receber: entrar na lista de contatos continua sendo decisão de cada empresa.

## 1. Página `/sair` (sem token)

- No site: `toqqi.com/sair` (entrada leve `responder.html`, como `/sair/{token}`; `PaginaPedirLink.vue`). Link no rodapé
  do site e dos guias ("Sair ou voltar a receber pesquisas"), no link inválido da `/sair/{token}` ("peça um link
  novo"), na aba Envios › Descadastros e no "Registrar descadastro" (para a equipe indicar ao cliente).
- A pessoa digita o e-mail; `POST /publico/descadastro/pedir-link {email}` responde sempre `200 {mensagem}` ("Se este
  e-mail já recebeu pesquisas pelo Toqqi, o link chega em alguns minutos…"), ache ou não o e-mail. 422 com e-mail
  inválido.
- Depois da resposta (o tempo também não revela nada), a Toqqi manda ao e-mail "Escolha as pesquisas que você recebe"
  (e-mail do sistema, sem registro em nenhuma conta) com a página `/sair/{token}` de cada empresa que **já mandou
  pesquisa** a um contato com esse e-mail (`contatos.ultimo_envio`) ou **de cuja lista ele saiu** (pelo e-mail, ou um
  contato com ele pelo WhatsApp), em ordem de nome, até 20. Uma empresa: o texto e o botão "Não quero mais receber"
  ou "Voltar a receber as pesquisas". Várias: um link por empresa, com "(você saiu da lista)" nas que saiu. Nenhuma:
  não manda nada.
- Empresa que só tem o contato, sem nunca ter mandado pesquisa, não aparece: o e-mail não revela listas de contatos.
- Limites: por IP, 3 pedidos por minuto e 20 por hora (429 `muitas_tentativas`); por e-mail, 3 por hora e 6 por dia
  (depois disso responde igual e não manda). Os dois por processo, como os outros limites da API.

## 2. Voltar vale em todos os canais (`descadastro.desfazer`)

Quem sai por um canal já saía de todos (o e-mail ou o telefone de um contato na lista bloqueia o contato inteiro).
Agora quem volta por um canal também volta em todos: voltar tira da lista o e-mail (ou o telefone) e os dos contatos
com ele, na conta da página. A `/sair/{token}` mostra "você saiu da lista" também quando quem saiu foi o telefone de
um contato com esse e-mail. Auditoria `descadastro_desfeito` com `origem` (`link` ou `whatsapp`) e o dado mascarado.

## 3. WhatsApp: VOLTAR

- Frases (a mensagem inteira normalizada, como o SAIR): "voltar", "quero voltar", "voltar a receber", "quero voltar a
  receber", "quero receber", "quero receber de novo", "receber de novo", "quero receber novamente", "receber
  novamente".
- Só com o telefone (ou um contato com ele) fora da lista: volta a receber e confirma "Pronto! Você volta a receber
  as pesquisas da {empresa}. Para parar, responda SAIR." Sem estar fora: ignorada, sem resposta.
- A confirmação do SAIR passa a terminar com "Se mudar de ideia, responda VOLTAR."

## 4. O que não mudou

- A equipe continua sem desfazer um descadastro: só a própria pessoa volta.
- Termos e Política: sem mudança (subir a versão faria todo mundo aceitar de novo). A página não guarda nada no
  navegador, como a `/sair/{token}`.
- Webhooks: não há evento para "voltou a receber" (`contato.descadastrado` continua só na saída).

## 5. Produção

`render.yaml`: regra `/sair` → `/responder.html` antes da regra geral do app e o mesmo cabeçalho CSP da `/sair/*`
(o Blueprint está com Auto Sync, então o push aplica).
