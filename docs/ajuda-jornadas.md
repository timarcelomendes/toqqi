# Toqqi · Ajuda em jornadas (onde, como e resultado)

Pedido do Marcelo (03/10, 14:46): "a ajuda deveria ter ajuda no formato de jornada para as principais funcionalidades,
onde, como e resultado". Proposta enviada no chat e aprovada (14:5x): **Jornadas vira a abertura da Ajuda** e cada tópico
ganha no topo um atalho para a sua jornada; **13 jornadas**, 9 no ciclo e 4 "para ir além". Complementa a 5b
(`docs/api-etapa-5b.md` §3 e §6.1); o resto da Ajuda (tópicos, seções, busca, atalhos) não muda.

## 0. Decisões
- Um conteúdo só, como na 5b: as jornadas ficam no mesmo `api/toqqi/modulos/ajuda/conteudo.json`, numa lista nova
  `jornadas` ao lado de `topicos`, servidas pelo mesmo `GET /ajuda` e consultadas pelo ToqqiAI pela mesma busca.
- Cada jornada tem **Onde** (o caminho no menu, em pedaços, e um atalho para a tela), **Como** (2 a 6 passos curtos),
  **Resultado** (o que a pessoa vê no fim), **Saiba mais** (1 a 3 seções dos tópicos; a primeira diz o tópico "dono" da jornada)
  e palavras de busca. Texto puro, mesmas regras de escrita da 5b (sem HTML, markdown, links ou endereços; nomes de telas e
  botões como aparecem no sistema, entre aspas curvas “…”; caminhos com "›").
- Grupos: `ciclo` ("Do cadastro ao resultado", numeradas 1 a 9, com "Próxima jornada") e `alem` ("Para ir além", sem número).
- Na busca (tela e ToqqiAI), uma jornada concorre com as seções pelas mesmas regras de pontos; **no empate, a jornada vem
  primeiro**. O ToqqiAI, quando a busca devolve uma jornada, responde em três partes: Onde, Como e Resultado.
- Conteúdo antigo sem `jornadas` continua válido (a lista é opcional no formato; o arquivo real tem as 13). Site antigo que não
  conhece `jornadas` ignora a chave.

## 1. Formato (`conteudo.json`)
```json
{"versao": 1,
 "jornadas": [
   {"id": "cadastrar-seus-clientes", "grupo": "ciclo", "titulo": "Cadastrar seus clientes",
    "objetivo": "Trazer sua lista de clientes para o Toqqi, com a empresa e o responsável de cada um.",
    "somente_admin": false,
    "onde": ["Contatos", "Importar planilha"],
    "atalho": "importar_contatos",
    "como": ["…", "…", "…"],
    "resultado": "…",
    "veja": ["contatos#importar-planilha-de-contatos", "contatos#importacao-conferencia-e-problemas"],
    "palavras": ["importar", "planilha", "cadastrar clientes"]}],
 "topicos": [ … como na 5b … ]}
```
Regras (validadas em `servico.validar`, usadas nos testes):
- `jornadas` opcional; se existir, lista não vazia. Campos exatamente estes 11 (faltando ou sobrando → erro).
- `id` kebab-case, único entre as jornadas. O id de tópico `jornadas` fica reservado (é o endereço da página).
- `grupo` `ciclo` ou `alem`; todas as `ciclo` antes de todas as `alem`.
- `titulo` (até 60 caracteres), `objetivo` (até 160) e `resultado` (até 320): texto não vazio.
- `onde`: 1 a 4 pedaços de até 40 caracteres, sem "›" (a tela põe o separador).
- `como`: 2 a 6 passos de até 220 caracteres.
- `atalho`: uma chave da lista de atalhos (5b §5.4) ou `null`. `somente_admin`: booleano.
- `veja`: 1 a 3 referências `topico#secao` que existem no conteúdo, sem repetir.
- `palavras`: lista (pode ser vazia) de textos não vazios.
- Todos os textos: as regras da 5b (nada de `<`, `http`, `www.`, `**`).
- No arquivo real: as jornadas na ordem de `JORNADAS` (`servico.py`), como os tópicos em `TOPICOS`.

As 13, nesta ordem (id · grupo · atalho · primeira referência de `veja`):
1. `cadastrar-seus-clientes` · ciclo · `importar_contatos` · `contatos#importar-planilha-de-contatos`
2. `preparar-a-pesquisa` · ciclo · `formularios` · `formularios#criar-um-formulario`
3. `ligar-os-envios` · ciclo · `config_envios` · `configuracoes#configuracoes-de-envio-ligar-canal-e-horario` (só administrador)
4. `enviar-a-pesquisa` · ciclo · `envios` · `envios#enviar-por-email-agora`
5. `ler-as-respostas` · ciclo · `respostas` · `respostas#ver-e-filtrar-as-respostas`
6. `tratar-um-cliente-insatisfeito` · ciclo · `planos_de_acao` · `planos-de-acao#tratar-e-concluir-uma-acao`
7. `acompanhar-os-numeros` · ciclo · `inicio` · `painel#o-que-mostra-o-inicio`
8. `descobrir-onde-agir` · ciclo · `relatorios` · `relatorios#empresas-nps-cobertura-e-receita`
9. `crescer-com-quem-esta-feliz` · ciclo · `crescimento` · `crescimento#indicacoes-dos-promotores`
10. `perguntar-ao-toqqiai` · alem · `null` · `assistente#o-que-e-o-assistente`
11. `trazer-a-equipe` · alem · `equipe` · `equipe#adicionar-e-gerenciar-pessoas` (só administrador)
12. `ligar-o-seu-sistema` · alem · `integracoes` · `integracoes#ligar-seu-sistema-zapier-make-n8n` (só administrador;
    título "Ligar o seu sistema e o WhatsApp automático")
13. `assinar-um-plano` · alem · `assinatura` · `assinatura#assinar-um-plano` (só administrador)

## 2. API (`toqqi/modulos/ajuda/servico.py`)
- `validar` com as regras do §1; `JORNADAS` com os 13 ids.
- `texto_da_jornada(j)`: "Só administrador." (se for o caso), o objetivo, "Onde: Contatos › Importar planilha", "Como:" e os
  passos numerados, "Resultado: …", uma parte por linha, cortado em 1.500 caracteres como as seções.
- `buscar(termo)`: jornadas e seções juntas, mesmos pesos (título 3, palavras 3, texto 1, onde o texto da jornada é objetivo +
  onde + como + resultado); jornadas antes das seções na ordem de desempate. Item da jornada:
  `{topico: "Jornadas", titulo, texto: texto_da_jornada, atalho}`.
- Instruções do ToqqiAI (`assistente/instrucoes.py`, "Dúvidas de uso"): com uma jornada no resultado, responder em três partes,
  "Onde:", "Como:" (passos curtos, com "- ") e "Resultado:", e indicar a tela pelo atalho.

## 3. Site (`web/src/modulos/ajuda`)
- Tipos: `JornadaAjuda` e `ConteudoAjuda.jornadas` (`web/src/api/tipos.ts`). `lerConteudo` lê as jornadas com a mesma defesa
  dos tópicos: sem `id`, `titulo`, `onde`, `como` ou `resultado` válidos, a jornada fica de fora; `grupo` desconhecido vira
  `alem`; ids repetidos, vale a primeira; `veja` que não acha a seção é ignorado na hora de mostrar.
- Endereços: `/ajuda` e `/ajuda/jornadas` mostram a página Jornadas (com jornadas no conteúdo; sem elas, `/ajuda` abre o primeiro
  tópico como hoje e `/ajuda/jornadas` volta para `/ajuda`). Âncora de cada jornada: `/ajuda/jornadas#<id>` (mesmo `ajuda-<id>`
  e `t-ajuda-<id>` das seções, para o rolar e o foco de hoje servirem).
- Menu da Ajuda: "Jornadas" é o primeiro item, acima do rótulo "Tópicos" (no celular, a primeira pílula); marcado em `/ajuda` e
  `/ajuda/jornadas` sem busca.
- Página Jornadas: título "Jornadas" e o texto "Cada funcionalidade em três partes: onde fica, como fazer e o que você ganha. Na
  primeira vez, siga na ordem."; um **mapa** com os dois grupos ("Do cadastro ao resultado" e "Para ir além") em blocos
  clicáveis (número, título e o caminho do Onde), que levam ao cartão; depois os cartões, com o nome do grupo antes de cada
  grupo.
- Cartão da jornada: número (só `ciclo`) e título; etiqueta "Só administrador" quando for o caso; o objetivo; e uma lista de
  três paradas ligadas por uma linha vertical, cada uma com ícone e rótulo:
  - **Onde**: os pedaços do caminho como etiquetas separadas por "›"; o botão "Abrir <rótulo do atalho>" quando a pessoa pode
    abrir a tela; com atalho que ela não pode abrir, "Seu perfil não abre esta tela. Peça acesso a um administrador.";
  - **Como**: os passos numerados;
  - **Resultado**: o texto num quadro suave de sucesso.
  Rodapé: "Saiba mais:" com links para as seções do `veja` (título da seção; vai ao tópico com a âncora) e, nas `ciclo` que não
  são a última, "Próxima jornada: <título> →".
- Tópicos: logo abaixo do cabeçalho do tópico, uma chamada para cada jornada cujo **primeiro** `veja` é deste tópico
  ("Jornada · <título>", o objetivo e "Ver a jornada →", que leva a `/ajuda/jornadas#<id>`).
- Busca "Buscar na ajuda": acha jornadas e seções juntas, pelas regras de hoje e com as jornadas antes no empate; o resultado de
  uma jornada mostra "Jornadas" no lugar do tópico e leva a `/ajuda/jornadas#<id>`.
- Acessibilidade e aparência: só tokens e componentes do design-system, claro e escuro, 390 a 1440 px sem rolagem lateral; as
  três paradas numa lista de descrição (`dl`, `dt` Onde/Como/Resultado); ícones decorativos com `aria-hidden`; nada de `v-html`;
  sem animação (nada com movimento a respeitar).
- Testes (vitest): leitura defensiva, busca com jornadas (empate, link), página Jornadas (mapa, cartões, atalho permitido e
  negado, Saiba mais, Próxima), chamada no tópico, `/ajuda` sem jornadas igual a hoje.

## 4. Conteúdo
- As 13 do §1, escritas a partir das seções que já existem e **conferidas nas telas** (`web/src/modulos/**`): cada rótulo entre
  aspas existe como está, cada caminho existe para quem a jornada diz. Só o que existe hoje.
- "Primeiros passos › Roteiro da primeira pesquisa" e "Onde fica cada coisa" passam a citar as Jornadas (a Ajuda abre nelas).

## 5. Feito (03 e 04/10)
- As `palavras` de cada jornada começam pelo título dela: sem isso, "Como envio a pesquisa?" trazia antes a seção (que repete
  o título nas palavras) e a jornada ficava em segundo. Com isso, perguntas diretas trazem a jornada em primeiro; perguntas
  sobre um detalhe ("Como importo meus contatos?", "como crio um formulário") continuam trazendo a seção.
- Rodapé do cartão: "Saiba mais" em linhas inteiras e "Próxima jornada" numa linha própria (à direita nas telas largas).
- Ao conferir as telas para escrever as jornadas, apareceu que o tópico "Início e painel" ainda descrevia o Início de antes do
  v2; foi reescrito à parte (commit anterior a este), com os mesmos ids de seção.
- Teste integrado (pilha local, API e site de verdade, Playwright): administrador em 1280 claro e gestor em 390 escuro — mapa
  com 9 + 4, 13 cartões na ordem, âncoras (clique, clique repetido, recarregar) com foco no título, "Abrir …" de 4 jornadas na
  tela certa, "Saiba mais" na seção certa, "Próxima jornada" só nas 8 primeiras, chamadas só nos tópicos donos, busca
  levando ao cartão, ToqqiAI (`memoria`) respondendo com Onde/Como/Resultado e o atalho da tela, aviso "Seu perfil não abre
  esta tela" nas 4 de administrador para o gestor; sem rolagem lateral e sem erro no console.
