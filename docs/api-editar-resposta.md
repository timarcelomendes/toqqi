# O cliente pode mudar a resposta, e a nota do e-mail abre na pergunta 1

Pedido do Marcelo (06/10/2026, 23h58): "1. permitir ou não que o usuário que irá responder edite a resposta. 2. hoje se
clico no e-mail no 10, ele já abre a segunda tela do formulário […] deve abrir na pergunta 1 com o valor selecionado no
e-mail". Respostas dele: **7 dias**; no link público, **só logo depois de enviar**; o plano de ação **fica aberto, com
aviso**. Depois: "pode tomar as decisões e concluir sem perguntar".

## 1. Nota clicada no e-mail (ou no WhatsApp)

`/r/{token}?nota=N` (e `/f/{codigo}?nota=N`): a pesquisa abre no **primeiro passo** do caminho, com a nota principal já
marcada e a dica "Marcamos a nota N, a que você escolheu. Se quiser, mude antes de continuar." (some quando a pessoa
muda a nota). A abertura (título e texto) aparece como em qualquer visita. Antes, a pesquisa começava no item depois da
nota (ou na primeira obrigatória antes dela).

## 2. Opção do formulário: "O cliente pode mudar a resposta"

- `formularios.permite_editar` (padrão: desligada), na aba **Compartilhar** (seção "Depois de responder"). Vale na
  hora, sem publicar. `PATCH /formularios/{id}` aceita `permite_editar`; o formulário traz o campo; duplicar copia.
- **Prazo:** 7 dias depois de responder (`respostas.criada_em` + 7 dias; mudar não estende o prazo).
- **Vale para:** respostas de pesquisa (não as registradas à mão nem as importadas), não arquivadas.
- **Convite (e-mail ou WhatsApp):** `GET /publico/convites/{token}` de um convite já respondido traz
  `edicao: {ate, respondida_em, respostas}` quando dá para mudar (senão `null`, e a página mostra "Você já respondeu
  esta pesquisa", como antes). A página abre preenchida, com a faixa "Você respondeu em 06/10. Pode mudar suas respostas
  até 13/10." (a nota clicada de novo no e-mail vale por cima da de antes). `POST .../responder` de novo troca a resposta
  (a mesma linha); fora do prazo, arquivada ou com a opção desligada: 409 `ja_respondido`.
- **Link público:** o envio devolve `edicao: {chave, ate}`; a chave (`{id da resposta}.{segredo}`; o banco guarda só o
  sha256 do segredo em `respostas.edicao_hash`) fica só na página aberta. "Editar minha resposta" na tela final volta
  às perguntas com o que foi enviado e o próximo envio vai para `POST /publico/formularios/{codigo}/editar
  {chave, respostas}`. Reabrir o link começa outra resposta (seguro num tablet de balcão). Chave errada, de outro
  formulário ou prazo vencido: 409 `edicao_indisponivel`. O envio repetido (a mesma resposta do mesmo IP em 10
  minutos, que não é gravada de novo) volta com `edicao: null`: a resposta gravada pode ser de outra pessoa.
- **Tela final:** `edicao: {ate}` (e a chave, no link público) enquanto der para mudar; o botão "Editar minha resposta"
  mostra "Dá para mudar até 13/10." e, ao voltar, a faixa "Mude o que quiser e envie de novo."

## 3. O que acontece quando o cliente muda (`registro.editar_resposta` → `eventos.ao_editar_resposta`)

- A resposta é validada como uma nova (a lógica do formulário publicado hoje) e troca na mesma linha: respostas, nota,
  grupo, comentário, temas (menos os escolhidos à mão) e a versão do formulário. Data, convite, contato, empresa, canal,
  contexto e referência ficam. `editada_em` e `edicoes` sobem; a última nota do contato acompanha.
- **Plano de ação:** com plano, ele fica como está e guarda a nota nova (`acoes.nota_editada`/`nota_editada_em`); o
  painel do plano mostra "O cliente mudou a nota — De 3 para 9, em …"; voltando à nota do plano, a marca sai. Sem plano,
  a nota nova pode pedir um, como numa resposta nova (com o alerta ao responsável).
- **IA:** texto, nota ou opções diferentes → a análise anterior sai e a resposta passa pela IA de novo (ou fica sem
  análise, sem texto que qualifique).
- **Webhook `resposta.atualizada`:** o mesmo formato de `resposta.criada`, com `editada_em`, `edicoes` e
  `nota_anterior` (os dois campos novos também vão no `resposta.criada`).
- **Depoimento** autorizado: comentário ou categoria mudou → volta a `pendente` para a equipe conferir.
- Nada de agradecimento de novo.
- Em Respostas: selo "Editada" na lista e, no detalhe, "Editada pelo cliente" com "O cliente mudou a resposta N vezes,
  a última em …".

## 4. Banco (migração `0028_editar_resposta`)

`formularios.permite_editar`, `respostas.editada_em`/`edicoes`/`edicao_hash`, `acoes.nota_editada`/`nota_editada_em`
(juntos) e `webhooks.eventos` aceita `resposta.atualizada`.

## 5. Fora

- Histórico de cada versão da resposta (fica só a última, com quantas vezes mudou).
- Nota ao CRM (RD Station) de uma resposta mudada depois da anotação.
- Mudar a resposta pelo link público em outra visita (de propósito: o aparelho pode ser de várias pessoas).
