# Plataforma › Contas: o risco de cada conta

Pedido do Marcelo (08/10/2026, 10h45): "adicione uma coluna para informar contas suspeitas, score das contas". A lista
de contas mostrava a situação e a assinatura, mas nada dizia quais contas podiam estar abusando do Toqqi: cadastro
falso ou repetido para ganhar outro teste, lista comprada (o que mais estraga a entrega dos e-mails de todo mundo),
formulário de golpe ou pagamento estornado.

A nota é um alerta para alguém da equipe olhar, não uma decisão: nada é bloqueado por ela.

## API

`GET /plataforma/contas` (superadmin) traz em cada conta:

```json
"risco": {
  "pontos": 65,
  "nivel": "alto",
  "sinais": [
    {"tipo": "descadastros", "pontos": 35, "saidas": 9, "destinatarios": 150, "taxa": 6},
    {"tipo": "invalidos", "pontos": 15, "invalidos": 20, "tentativas": 170, "taxa": 12},
    {"tipo": "sem_respostas", "pontos": 15, "convites": 150, "respostas": 1}
  ]
}
```

- `pontos`: a soma dos pontos dos sinais, até 100. `nivel`: `alto` (60 ou mais), `medio` (30 a 59) ou `baixo`.
- `sinais`: do que vale mais para o que vale menos, cada um com os dados que o explicam.
- `risco: null` nas contas da equipe (algum administrador em `SUPERADMIN_EMAILS`); elas também ficam fora das
  comparações de repetidos.
- Só na listagem: criar, "+N dias" e cortesia devolvem a conta sem `risco` (a tela guarda o da listagem).
- Calculado na hora (`api/toqqi/modulos/plataforma/risco.py`), com um número fixo de consultas agregadas, como a Visão
  geral. Nada é gravado; sem migração.

### Sinais

| Sinal | Pontos | Quando |
|---|---|---|
| `formulario_sensivel` | 60 | Formulário não arquivado com pergunta aberta (texto curto ou comentário) pedindo senha, número ou código de segurança do cartão, dados bancários ou código de verificação; também um bloco de texto com isso num formulário que tem pergunta aberta. Traz o formulário, o `termo` (`senha`, `cartao`, `banco`, `codigo`) e o `trecho` (até 100 caracteres). |
| `email_temporario` | 40 | Algum administrador com e-mail de serviço descartável (mailinator, yopmail, 10minutemail e outros ~60, ou subdomínio deles). |
| `descadastros` | 35 / 20 | Nos últimos 30 dias, quem saiu da lista pelo link, pelo "cancelar inscrição" do programa de e-mail ou pelo SAIR do WhatsApp, sobre quem recebeu algo (destinatários diferentes): 5% ou mais / 2% ou mais. Só com 30 destinatários e 3 saídas ou mais. A saída registrada pela equipe da conta não conta. |
| `invalidos` | 30 / 15 | Nos últimos 30 dias, envios que voltaram com "endereço não existe" (e-mail) ou "número sem WhatsApp", sobre os envios tentados: 20% ou mais / 8% ou mais. Só com 30 tentativas e 5 inválidos ou mais. |
| `documento_repetido` | 30 | O CPF ou CNPJ da conta (dados da empresa ou de alguma assinatura) aparece em outra conta. Traz até 3 contas e o total. |
| `estorno` | 25 | Alguma cobrança estornada. Traz quantas e a data da última. |
| `telefone_repetido` | 20 | O telefone da conta, de um administrador ou de uma assinatura aparece em outra conta (comparado só pelos dígitos, com o 55 e o nono dígito acertados). |
| `sem_respostas` | 15 | Convites por e-mail ou WhatsApp que saíram nos últimos 30 dias (menos os dos últimos 3, que ainda podem ser respondidos): 100 ou mais, com menos de 2% respondidos. |
| `email_nao_confirmado` | 15 | Quem criou a conta (o administrador mais antigo) não confirmou o e-mail em 2 dias ou mais. |
| `nome_de_teste` | 15 | Nome da empresa de teste ou sem sentido: "teste", "asdf", "empresa", "xx", só números, uma letra repetida, menos de 3 caracteres. |
| `nome_repetido` | 15 | Outra conta com o mesmo nome (sem acento, caixa, pontuação e "Ltda", "ME", "S/A"…). Não vale para nome de teste. |
| `email_pessoal` | 10 | Quem criou a conta usa e-mail pessoal (gmail.com, hotmail.com, outlook.com, yahoo, bol, uol…). |
| `dominio_repetido` | 10 | O domínio do e-mail de quem criou a conta (fora os pessoais e temporários) é o de quem criou outra conta. |
| `volume_inicio` | 10 | Conta com menos de 14 dias que já fez 500 envios ou mais. |

### Decisões

- **Sem IP.** Os registros de acesso ficam em sigilo (Marco Civil da Internet; `core.acessos`) e nenhuma tela os lê;
  o "mesmo IP de outra conta" ficou de fora de propósito.
- **Volume mínimo** nos sinais de envio, para conta pequena não ser acusada por acaso (3 saídas em 20 envios não dizem
  nada).
- **E-mail pessoal vale pouco** (10): muita empresa pequena usa gmail. Sozinho, fica em "Baixo".
- **Formulário pedindo senha vale 60** (alto sozinho): golpe com o nome do Toqqi é o pior caso. O trecho aparece na
  tela para a equipe ver na hora se é engano (ex.: uma pesquisa sobre a troca de senha do app do cliente).
- Os pesos e limites ficam no começo de `risco.py`, para ajustar com o uso.

## Site (Plataforma › Contas)

- Coluna **Risco** (a partir de 1280 px), logo depois de Empresa: médio e alto com o selo colorido ("Alto 65",
  "Médio 40"), baixo em texto discreto ("Baixo 10") e "Nenhum sinal" quando não há nenhum; embaixo, cada motivo com os
  pontos ("+35 6% saíram da lista (9 de 150 em 30 dias)"). A conta da equipe mostra "—".
- Abaixo de 1280 px (e no celular), o risco médio ou alto aparece embaixo do nome, com os motivos.
- Botão **Suspeitas N** ao lado da busca: mostra só as contas de risco médio ou alto, da maior nota para a menor;
  combina com a busca; sem nenhuma, "Nenhuma conta suspeita".
- Para a coluna caber, a coluna **Datas** saiu: "Teste até" e "Pago até" ficam embaixo da situação (no celular,
  embaixo do nome, como antes).

## Testes

- `api/tests/test_plataforma_risco.py`: as regras puras (nome de teste, nome normalizado, domínio temporário, trecho
  sensível) e, pela API, conta limpa e da equipe, cadastro suspeito, repetidos (com a conta da equipe fora), lista
  comprada (faixas e janela de 30 dias), pouco volume, conta nova com muito envio, formulário pedindo senha (arquivado
  não conta), estorno e o teto de 100.
- `web/tests/plataformaRisco.test.ts`: o texto de cada sinal, a coluna, o risco embaixo do nome, o filtro "Suspeitas"
  com a busca e a ordem.
