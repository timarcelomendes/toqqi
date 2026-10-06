# Toqqi · Etapa 5k: preços, descontos, plano Personalizado e IA mais barata

Pedido do Marcelo em 05/10/2026 (21h27–21h36), depois da análise de saúde financeira dos planos: reduzir e limitar o
que pesa, WhatsApp no número do cliente, modelos de IA "os mais recentes e baratos", Pix com desconto, plano anual e um
plano Personalizado com preço calculado pelos limites. Decisões dele: **Pix 3% no mensal, anual 10%** (sem somar com o
Pix). Mesmas convenções das etapas anteriores; os parâmetros seguem a 5g (`docs/api-etapa-5g.md`).

## 0. Decisões
- Preços dos três planos **não mudam** (149 / 349 / 799). O que muda são limites, descontos e o Personalizado.
- WhatsApp automático **sem franquia** por padrão: o número é do cliente (Tech Provider, etapa 3b) e a Meta cobra a
  conta dele; cobrar franquia ou excedente seria cobrar duas vezes. As franquias continuam como parâmetro (agora com
  "Sem limite", o padrão) para a equipe poder limitar se precisar; o excedente só aparece quando há franquia.
- IA: GPT-6 Luna (US$ 0,10 / 0,50 por milhão de tokens) no Rápido, no Equilibrado e na análise de cada resposta; GPT-6
  Sol (US$ 2 / 10) no Mais detalhado, que passa a gastar **3** análises da cota. `minimal` não existe nos GPT-6: o
  Rápido e a análise de cada resposta vão com `none`. Troca de modelo continua manual (Plataforma › Parâmetros testa
  antes de salvar); nada troca sozinho.
- Teste com cota própria do ToqqiAI (50, em vez da cota do plano do teste) e teto menor; cortesia com cota e teto
  menores; Empresa com limite de contatos (5.000) em vez de "sem limite" — acima disso, o Personalizado.
- Assinatura anual: troca de plano só pela equipe (a tela explica); mudar de mensal para anual (ou de forma de
  pagamento) = cancelar e assinar de novo (a nova começa no fim do período pago, regra da 5a).

## 1. Padrões novos (código; `render.yaml` acompanha as variáveis)
| Chave | Antes | Agora |
|---|---|---|
| `planos.empresa.contatos` | sem limite | 5.000 (também na função `limite_contatos` do banco) |
| `ia.cota.cortesia` (`IA_COTA_CORTESIA`) | 500 | 200 |
| `ia.cota.teste` (nova) | — (cota do plano do teste) | 50 |
| `ia.teto.empresa` / `.cortesia` / `.teste` | 20.000 / 5.000 / 1.000 | 15.000 / 2.000 / 500 |
| `ia.modelo.rapido` / `ia.esforco.rapido` | gpt-5-nano / minimal | gpt-6-luna / none |
| Equilibrado (`IA_ASSISTENTE_MODELO` / `_ESFORCO`) | gpt-5-mini / low | gpt-6-luna / low |
| `ia.modelo.detalhado` / `ia.analises.detalhado` | gpt-5 / 2 | gpt-6-sol / 3 |
| Análise de cada resposta (`IA_MODELO` / `IA_ESFORCO`) | gpt-5-mini / minimal | gpt-6-luna / none |
| `whatsapp.franquia.*` (tipo `limite`, aceita null) | 40 / 90 / 200 / 200 / 20 | sem limite (todas) |

Novas no grupo `planos`: `planos.desconto.pix` (inteiro 0–30, padrão 3), `planos.desconto.anual` (0–50, padrão 10) e o
Personalizado (§3): `planos.personalizado.base` (99,00), `.ate_1500` (18,00), `.ate_10000` (11,00), `.acima` (6,00),
`.ia_500` (30,00), `.ia_2000` (120,00), `.ia_5000` (250,00). Nova no grupo `whatsapp`: `whatsapp.franquia.personalizado`.

## 2. Ciclo e forma de pagamento
- `ciclo`: `mensal` | `anual`; `forma`: `pix` | `qualquer` (fatura com Pix, boleto ou cartão). Anual é sempre `qualquer`.
- Valor de cada fatura (`core.planos.valor_contrato`), arredondado a centavos (meio para cima):
  mensal = preço; mensal + Pix = preço × (1 − pix%); anual = preço × 12 × (1 − anual%).
- Asaas: mensal + Pix → `billingType: PIX`, `cycle: MONTHLY`; mensal → `UNDEFINED`/`MONTHLY`; anual → `UNDEFINED`/`YEARLY`.
- Descrição no Asaas (`core.planos.descricao`, também usada para adotar): "Toqqi – plano Profissional", "… · Pix",
  "… · anual"; Personalizado: "Toqqi – plano Personalizado (2.000 contatos, 500 perguntas)" + o mesmo sufixo. Adotar
  (assinar depois de tempo esgotado e conferência diária) exige descrição reconhecida **e** o valor de hoje para ela.
- `assinaturas` ganha `ciclo`, `forma`, `contatos` e `cota_ia` (os dois últimos só no Personalizado). `pago_ate` =
  maior vencimento pago + 1 mês (ou + 1 ano, se a assinatura da cobrança é anual) − 1 dia.
- `POST /assinatura` aceita `ciclo` (padrão mensal), `forma` (padrão qualquer) e, no Personalizado, `contatos` e
  `cota_ia`; `preco` = o valor da fatura que a tela mostrou (por mês, ou o total do ano). Diferente → 409 `preco_mudou`.
- `PUT /assinatura/plano` mantém ciclo e forma; anual → 409 `troca_no_anual` ("Na assinatura anual, a troca de plano é
  feita pela equipe Toqqi. Fale com a gente."). O mesmo plano com os mesmos números não muda nada.
- `GET /assinatura` e `GET /publico/planos` ganham `descontos: {pix, anual}` e `personalizado: {base, faixas:
  [{ate, preco}], ia: [{cota, preco}], contatos_min: 100, contatos_max: 100000, passo: 100}`; `assinatura` ganha
  `ciclo`, `forma`, `contatos`, `cota_ia`.

## 3. Plano Personalizado
- Contatos em múltiplos de 100, de 100 a 100.000; perguntas ao ToqqiAI por mês: 100 (incluídas), 500, 2.000 ou 5.000.
- Preço por mês = base + contatos em faixas (cada 100 até 1.500 pelo preço `ate_1500`, de 1.501 a 10.000 pelo
  `ate_10000`, acima pelo `acima`) + pacote do ToqqiAI. Exemplos com os padrões: 1.500/500 = R$ 399; 5.000/2.000 =
  R$ 874; 10.000/2.000 = R$ 1.424. Descontos de Pix e anual valem igual. Mesmo cálculo em `web/src/utils/precos.ts`.
- Conta: `plano = 'personalizado'` com `contatos_personalizado` e `cota_ia_personalizada` gravados ao assinar ou
  trocar. Limite de contatos = `contatos_personalizado` (gatilho e Python); cota do ToqqiAI = `cota_ia_personalizada`;
  teto da análise de comentários = 3 × contatos (mínimo 1.000); WhatsApp = `whatsapp.franquia.personalizado`.
- O plano do teste continua entre os três padrões. Perder a assinatura sem nunca pagar volta ao plano do teste (5a).

## 4. Telas
- Assinatura: alternador Mensal / Anual (−10%), forma Pix (−3%) ou cartão/boleto no mensal, quarto cartão
  Personalizado com a calculadora; trocar de plano inclui o Personalizado; no anual, a troca mostra a explicação.
- Plataforma › Parâmetros: descontos, tabela do Personalizado, cota do teste, franquias com "Sem limite".
- Integrações › WhatsApp: sem franquia → "Sem franquia: as mensagens saem pelo seu número e a Meta cobra direto da
  sua conta"; barra e excedente só com franquia.
- Site da raiz: WhatsApp "sem franquia", Empresa com 5.000 contatos, nota do Pix e do anual, cartão do Personalizado
  com a calculadora. Ajuda e Termos acompanham (Termos v7: anual, descontos, Personalizado, sem franquia).

## 5. Migração 0025_planos_5k
`assinaturas`: `ciclo` text NOT NULL DEFAULT 'mensal' CHECK (mensal|anual), `forma` text NOT NULL DEFAULT 'qualquer'
CHECK (pix|qualquer), `contatos` integer, `cota_ia` integer; CHECK do plano aceita `personalizado` (com contatos e
cota_ia preenchidos). `contas`: `contatos_personalizado` integer, `cota_ia_personalizada` integer. Função
`limite_contatos(p_plano, p_situacao)`: padrão do Empresa 5.000. Gatilho `contatos_checar_limite`: Personalizado
(fora da cortesia) usa `contas.contatos_personalizado`. O downgrade volta tudo (assinaturas Personalizado impedem).

## 6. Decisões tomadas na construção
- Na tela, **Pix vem marcado** (é a sugestão pedida); o cartão mostra o preço cheio riscado e o valor com desconto. No
  anual, a escolha da forma some (a fatura aceita as três) e o cartão mostra "equivale a R$ X por mês".
- O Personalizado é a 4ª opção do mesmo grupo de rádios, em largura total abaixo dos três planos; a calculadora abre
  quando ele é escolhido, com os contatos sugeridos = ativos de hoje + 20% (mínimo 500), arredondados para 100.
- `GET /assinatura/preco` devolve o valor de um contrato (prova da conta da tela; a tela não depende dela).
- Plataforma › Visão geral soma o anual como 1/12 na receita mensal.
- Assinou durante o teste: a cota do ToqqiAI já é a do plano escolhido (o teto da análise de comentários segue o do
  teste até pagar, como antes).
- Site da raiz: as franquias aparecem como "Sem franquia" (`data-p` com null); o cartão do Personalizado tem a mesma
  calculadora (`utils/precos.ts`), com a tabela de `GET /publico/planos`.
- **Atenção ao subir**: o `render.yaml` troca `IA_ASSISTENTE_MODELO` para gpt-6-luna e `IA_COTA_CORTESIA` para 200 na
  próxima sincronização do Blueprint. Os outros padrões são do código (nada salvo em Plataforma › Parâmetros hoje).
