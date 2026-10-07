# WhatsApp: situação do número na Meta e registro pelo Toqqi

Pedido do Marcelo (07/10/2026, 18h43), depois de ver o número "Pendente" no WhatsApp Manager ("Registre este número
de telefone usando a API de registro…"): "seria legal esse registro de verificação ser feito pela Toqqi, ajuda o
usuário".

## O problema

Número adicionado e confirmado com o código no WhatsApp Manager fica **Pendente** até o registro na Cloud API:
`POST /{phone_number_id}/register {"messaging_product": "whatsapp", "pin": "<6 dígitos>"}`. O WhatsApp Manager não
tem botão para isso. O PIN vira a verificação em duas etapas do número (se o número já tinha, vale o PIN dela). A Meta
aceita 10 pedidos de registro por número em 72 horas; depois bloqueia o registro por 72 horas (erro 133016). Sem o
registro, os envios voltam com 133010 ("sem número registrado").

## API

- `GET /integracoes/whatsapp/numero` (administrador): lê na hora, com o token salvo, `status`, `platform_type` e
  `code_verification_status` do número e devolve `{situacao, status, codigo_confirmado}`:
  - `registrado`: `platform_type` = `CLOUD_API` (ou, sem ele, `status` = `CONNECTED`);
  - `falta_registrar`: outra plataforma (`NOT_APPLICABLE`, `ON_PREMISE`) ou, sem ela, `PENDING`/`UNVERIFIED`;
  - `atencao`: registrado, mas `FLAGGED`, `RESTRICTED`, `RATE_LIMITED` ou `DISCONNECTED`;
  - `problema`: `BANNED`, `DELETED` ou `MIGRATED`;
  - `desconhecida`: a Meta não informou.
  Falha na Meta: 409 `falha_meta` com o texto de sempre (token recusado, fora do ar…).
- `POST /integracoes/whatsapp/registrar {pin}` (administrador; 2 por minuto por usuário): PIN de exatamente 6
  números (422 "O PIN tem 6 números."). Chama o `/register` com o token salvo. Aceito: 200 `{mensagem, numero}`,
  auditoria `whatsapp_numero_registrado` e o "sem número registrado" do último envio sai. Recusado: 409
  `registro_recusado` com o motivo em texto simples (133005 PIN errado, 133006 confirmar o número de novo, 133008 e
  133009 tentativas, 133015 excluído há pouco, 133016 bloqueio de 72 horas, 190/401 token, 10/200 permissão, 5xx ou
  133004 fora do ar; outro código: "A Meta recusou o registro do número (código N)…") e auditoria
  `whatsapp_registro_recusado` com o código.
- Limite: com 8 pedidos (aceitos ou recusados) da conta nas últimas 72 horas, 409 `muitas_tentativas_registro` sem
  chamar a Meta (folga para os 10 dela, que contam também o que for feito fora do Toqqi).
- O PIN não é guardado nem vai para o log ou para a auditoria.

## Site

- Integrações › WhatsApp automático: linha "Situação na Meta" (Registrado e pronto para enviar, Pendente: falta
  registrar o número, Registrado mas a Meta marcou como "…", A Meta marcou como "…", A Meta não informou), lida ao
  abrir, com "Tentar de novo" se a Meta não responder.
- Pendente: cartão "Falta registrar o número na Meta" com o campo "PIN de 6 números" (só números), digitado ou
  gerado em "Gerar PIN" (pedido do Marcelo, 19h02: sorteio seguro do navegador, sem repetição nem sequência, com
  "Copiar PIN"; PIN digitado fácil de adivinhar, como 123456 ou 111111, ganha um aviso, sem bloquear), "Registrar o
  número", a explicação (vira a verificação em duas etapas, o Toqqi não guarda; se já tinha, use o PIN dela; 10
  tentativas a cada 3 dias) e, sem o código confirmado, a dica de confirmar no WhatsApp Manager.
- Sinalizado, restrito, banido…: aviso com o link do WhatsApp Manager.
- Guia de conexão (passo 2) e Ajuda ("Conectar o WhatsApp automático"): o número fica Pendente até o registro, e o
  Toqqi registra depois de conectar.

## Fora

- Registrar antes de conectar (o registro usa o token já salvo).
- Trocar ou desligar a verificação em duas etapas pelo Toqqi (fica no WhatsApp Manager).
