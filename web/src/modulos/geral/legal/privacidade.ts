import type { DocumentoLegal } from './tipos'

export const PRIVACIDADE: DocumentoLegal = {
  titulo: 'Política de privacidade',
  introducao: [
    {
      tipo: 'p',
      texto:
        'Esta política explica quais dados pessoais o Toqqi trata, para quê, com quem compartilha, por quanto tempo guarda e como você exerce seus direitos. Ela segue a Lei Geral de Proteção de Dados (LGPD, Lei 13.709/2018) e o Marco Civil da Internet (Lei 12.965/2014).',
    },
    {
      tipo: 'p',
      texto: [
        'Ela vale junto com os ',
        { texto: 'Termos de uso', href: '/termos' },
        '. Não vendemos dados pessoais e não fazemos publicidade.',
      ],
    },
  ],
  secoes: [
    {
      id: 'quem-somos',
      titulo: 'Quem somos e como falar com a gente',
      blocos: [
        {
          tipo: 'p',
          texto:
            'O Toqqi é uma plataforma de pesquisas de satisfação (NPS e CSAT), operada por [a confirmar: razão social], CNPJ [a confirmar: CNPJ], com sede em [a confirmar: endereço completo].',
        },
        {
          tipo: 'p',
          texto: [
            'O encarregado pelo tratamento de dados pessoais (DPO) é [a confirmar: nome do encarregado]. Contato: ',
            { texto: 'privacidade@toqqi.com', href: 'mailto:privacidade@toqqi.com' },
            '. Para outros assuntos: ',
            { texto: 'contato@toqqi.com', href: 'mailto:contato@toqqi.com' },
            '.',
          ],
        },
      ],
    },
    {
      id: 'papeis',
      titulo: 'Quem decide sobre os dados: controlador e operador',
      blocos: [
        {
          tipo: 'p',
          texto: 'O papel do Toqqi muda conforme o dado:',
        },
        {
          tipo: 'lista',
          itens: [
            'Dados de quem usa o Toqqi (usuários e a empresa assinante): o Toqqi é o controlador. Nós decidimos como esses dados são tratados.',
            'Dados dos clientes da empresa assinante (contatos, respostas, notas e comentários): a empresa assinante é a controladora e o Toqqi é o operador. Tratamos esses dados só conforme as instruções dela, como descrito nos Termos de uso.',
          ],
        },
        {
          tipo: 'p',
          texto: [
            'Se você recebeu uma pesquisa de uma empresa e quer saber ou mudar algo sobre os seus dados, o caminho principal é falar com essa empresa. Veja ',
            { texto: 'Seus direitos', href: '/privacidade#seus-direitos' },
            '.',
          ],
        },
      ],
    },
    {
      id: 'dados-que-tratamos',
      titulo: 'Quais dados tratamos',
      blocos: [
        {
          tipo: 'tabela',
          colunas: ['De quem', 'Dados', 'De onde vêm'],
          linhas: [
            [
              'Usuários do Toqqi',
              'Nome, e-mail, cargo, telefone, senha (guardamos só um código irreversível, o hash argon2id, nunca a senha), perfil de acesso, preferências de e-mails do sistema.',
              'Informados por você ou pelo administrador da conta.',
            ],
            [
              'Usuários do Toqqi (uso)',
              'Endereço IP, navegador, data e hora de acessos, registros de auditoria (o que foi feito na conta e por quem), aceite dos termos.',
              'Gerados quando você usa o sistema.',
            ],
            [
              'Usuários do Toqqi (registro de acesso)',
              'Data, hora e IP de cada entrada no Toqqi e de cada tentativa de entrar, do cadastro, do pedido de acesso e da troca de senha pelo link enviado por e-mail (Marco Civil da Internet, art. 15).',
              'Gerado quando acontece cada um desses eventos.',
            ],
            [
              'Empresa assinante',
              'Razão social, documento de cobrança (CPF ou CNPJ), endereço, e-mail e telefone de cobrança e histórico de pagamentos (os dados de cartão ficam com o Asaas, não conosco).',
              'Informados no cadastro e na assinatura.',
            ],
            [
              'Clientes da empresa assinante',
              'Nome, e-mail, telefone, empresa, CPF/CNPJ da empresa cliente, cargo, valor mensal, "cliente desde", dados do pedido ou atendimento (referência e contexto), respostas, notas e comentários nas pesquisas, situação dos envios (entregue e, no WhatsApp, lido), pedido de descadastro e anotações internas dos planos de ação.',
              'Importados ou cadastrados pela empresa assinante, e informados pelo próprio cliente ao responder.',
            ],
            [
              'Quem responde a uma pesquisa',
              'Um código derivado do IP, com sal diário, só para evitar respostas repetidas no mesmo dia. E o registro de acesso: data, hora e IP do envio da resposta ou de uma indicação (Marco Civil da Internet, art. 15).',
              'Gerados quando a pessoa envia a resposta ou a indicação.',
            ],
            [
              'Quem recebe e-mails pelo Toqqi (clientes da empresa assinante e usuários)',
              'Registro de cada e-mail que sai em nome de uma conta, das pesquisas e do sistema: o endereço de quem recebeu, o assunto, a situação (enviado ou falhou), o erro, quando falha, e a data. Não guardamos o conteúdo da mensagem nesse registro.',
              'Gerado quando o e-mail é enviado.',
            ],
          ],
        },
        {
          tipo: 'p',
          texto:
            'Não pedimos dados sensíveis (art. 5º, II da LGPD). Se um cliente escrever algo assim num comentário, a empresa, como controladora, pode editar ou apagar a resposta. Oriente sua equipe a não pedir esse tipo de informação. Também não tratamos dados de crianças sem o consentimento específico de um dos pais ou responsável (LGPD, art. 14).',
        },
      ],
    },
    {
      id: 'finalidades-e-bases-legais',
      titulo: 'Para que usamos os dados e em que base legal',
      blocos: [
        {
          tipo: 'tabela',
          colunas: ['Para quê', 'Base legal (LGPD, art. 7º)'],
          linhas: [
            [
              'Prestar o serviço: criar a conta, enviar pesquisas por e-mail e WhatsApp, lembretes, receber respostas, painéis, relatórios e planos de ação.',
              'Execução de contrato (inciso V).',
            ],
            [
              'Enviar e-mails do sistema: confirmação de e-mail, redefinição de senha, resumo semanal e alertas. Resumo e alertas podem ser desligados em Minha conta.',
              'Execução de contrato (V) e legítimo interesse (IX).',
            ],
            ['Cobrança, emissão de documentos fiscais e contabilidade.', 'Execução de contrato (V) e obrigação legal (II).'],
            [
              'Segurança, prevenção a fraude e abuso, auditoria, limites de uso.',
              'Legítimo interesse (IX) e obrigação legal (II).',
            ],
            [
              'Mostrar à empresa assinante, em Auditoria › E-mails enviados, quais e-mails saíram em nome dela e quais falharam, para ela corrigir endereços e acompanhar os envios.',
              'Execução de contrato (V) e legítimo interesse (IX).',
            ],
            ['Suporte e atendimento aos seus pedidos.', 'Execução de contrato (V) e legítimo interesse (IX).'],
            ['Melhorar o serviço, com dados agregados ou anonimizados.', 'Legítimo interesse (IX).'],
            [
              'Guardar no navegador o que o site precisa para funcionar (veja "Cookies e armazenamento no navegador").',
              'Execução de contrato (V) e legítimo interesse (IX), sem precisar de consentimento.',
            ],
            [
              'Guardar registros de acesso, atender ordens de autoridades, defender-nos em processos.',
              'Obrigação legal (II) e exercício regular de direitos (VI).',
            ],
          ],
        },
        {
          tipo: 'p',
          texto:
            'Hoje não usamos o consentimento como base legal. Para os dados dos clientes da empresa assinante, quem define a base legal é a empresa controladora (por exemplo, execução de contrato ou legítimo interesse). Cabe a ela ter essa base para contatar os clientes e atender os pedidos deles. O Toqqi ajuda, por exemplo com o descadastro e a exclusão de contatos.',
        },
        {
          tipo: 'p',
          texto: [
            'O aceite destes documentos não é um consentimento: ele registra que você conhece e concorda com as regras de uso do Toqqi, contratado pela sua empresa. Mesmo assim, você pode retirá-lo quando quiser em ',
            { texto: 'Minha conta › Privacidade › Retirar meu aceite', href: '/minha-conta' },
            '. Ao retirar, você sai do Toqqi e só volta a usá-lo aceitando de novo; guardamos o registro do aceite anterior e da retirada como prova, pelo tempo descrito em Retenção, e você deixa de receber os e-mails do Toqqi. Retirar o aceite não apaga a sua conta nem os seus dados: para isso, veja Seus direitos. Para encerrar o uso pela empresa, o administrador cancela a assinatura.',
          ],
        },
      ],
    },
    {
      id: 'inteligencia-artificial',
      titulo: 'Inteligência artificial',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Usamos a OpenAI (Estados Unidos) em cinco recursos. A análise de comentários e os passos sugeridos nas ações já vêm ligados, e a empresa assinante pode desligá-los em Configurações › IA. O resumo do painel, o parecer dos relatórios e o ToqqiAI, o assistente de IA do Toqqi, só enviam dados quando alguém da conta pede (clica em gerar o resumo ou o parecer, ou faz uma pergunta). Todos funcionam enquanto a IA estiver disponível e a assinatura estiver em dia.',
        },
        {
          tipo: 'lista',
          itens: [
            'Análise de comentários: vão para a OpenAI o texto do comentário do cliente (cortado em 500 caracteres), as opções que ele marcou e a nota, para classificar temas e sentimento automaticamente. A empresa pode corrigir o resultado. Não enviamos o nome, o e-mail nem o telefone do cliente nesse recurso.',
            'Passos das ações: quando uma ação é criada a partir de uma resposta, vão para a OpenAI o tipo, a nota e o grupo dessa resposta, o comentário do cliente (cortado em 500 caracteres) e as opções que ele marcou, e as últimas 5 respostas da mesma empresa (data, tipo, nota e comentário, cortado em 300 caracteres), para sugerir até 3 passos. Nesse recurso não enviamos o nome da empresa nem do contato, o e-mail, o telefone ou os dados do pedido.',
            'Resumo do painel: quando alguém pede o resumo, vão para a OpenAI o nome da conta (nas instruções para a IA), o nome do grupo de empresas filtrado, se houver, os números do período e dos filtros escolhidos (NPS, CSAT, taxa de resposta, temas, evolução, ações abertas e vencidas e receita em risco), os nomes das empresas de menor e de maior NPS, os picos de reclamação e até 8 comentários de clientes do período (cortados em 300 caracteres, sem o nome, o e-mail ou o telefone de quem respondeu).',
            'Parecer dos relatórios: quando alguém pede o parecer, vão para a OpenAI o nome da conta (nas instruções para a IA), o nome do grupo de empresas filtrado, se houver, os números dos relatórios no período e nos filtros escolhidos (empresas, cobertura, receita, matriz NPS × valor, temas, responsáveis e operação) e os desta semana, com nomes de empresas e de responsáveis (por exemplo, as empresas a proteger e os responsáveis com mais receita em risco). Não enviamos nome, e-mail ou telefone de contatos nesse recurso.',
            'ToqqiAI: vão para a OpenAI a pergunta do usuário, as últimas mensagens da conversa e os dados que o ToqqiAI consulta para responder (indicadores, nomes de empresas e contatos, comentários). Esses dados podem incluir nomes e comentários de clientes.',
          ],
        },
        {
          tipo: 'p',
          texto:
            'Como desligar: a análise de comentários e os passos das ações se desligam em Configurações › IA. O resumo do painel e o parecer dos relatórios não rodam sozinhos: só quando alguém pede. O último resumo e o último parecer de cada combinação de filtros ficam guardados na conta, com a data e quem gerou, até alguém gerar de novo com os mesmos filtros, e são apagados junto com a conta.',
        },
        {
          tipo: 'p',
          texto:
            'Pelas regras da API da OpenAI, os dados enviados não são usados para treinar modelos. Também pedimos que ela não guarde as respostas (store: false). A OpenAI pode manter registros por até [a confirmar: prazo de retenção da OpenAI, em geral 30 dias] para prevenir abuso. As decisões com base na IA continuam sendo das pessoas da empresa: a IA só sugere.',
        },
      ],
    },
    {
      id: 'compartilhamento',
      titulo: 'Com quem compartilhamos (operadores e fornecedores)',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Usamos fornecedores para prestar o serviço. Eles só podem tratar os dados para esse fim, sob contrato. Não vendemos nem alugamos dados pessoais.',
        },
        {
          tipo: 'tabela',
          colunas: ['Fornecedor', 'Para quê', 'Onde fica', 'Que dados'],
          linhas: [
            ['Render', 'Hospedagem do sistema e banco de dados', 'Estados Unidos', 'Todos os dados do sistema'],
            ['OpenAI', 'Inteligência artificial (análise de comentários, passos das ações, resumo do painel, parecer dos relatórios e ToqqiAI)', 'Estados Unidos', 'Conforme a seção sobre IA: só com o recurso ligado ou quando alguém da conta pede'],
            ['Asaas', 'Cobrança e pagamentos', 'Brasil', 'Dados de cobrança da empresa assinante'],
            ['ZeptoMail (Zoho)', 'Envio de e-mails (pesquisas e e-mails do sistema)', 'Estados Unidos', 'Nome e e-mail do destinatário, conteúdo da mensagem'],
            ['Resend', 'Envio de e-mails, como provedor alternativo', 'Estados Unidos', 'Nome e e-mail do destinatário, conteúdo da mensagem'],
            ['Meta (WhatsApp Cloud API)', 'Envio de pesquisas por WhatsApp, só se a empresa conectar o WhatsApp', 'Estados Unidos e outros países', 'Telefone e nome do destinatário, conteúdo da mensagem'],
            ['Webhooks de saída e Microsoft Teams', 'Avisos para sistemas da própria empresa e para o Teams, só por instrução da empresa assinante', 'Onde fica o sistema de destino configurado pela empresa', 'O que a empresa escolher enviar (por exemplo, dados de uma resposta ou de um alerta)'],
            ['GitHub', 'Agendamento de tarefas automáticas', 'Estados Unidos', 'Nenhum dado pessoal'],
            ['ViaCEP', 'Preencher o endereço a partir do CEP, consulta feita pelo seu navegador', 'Brasil', 'O CEP digitado e o IP do seu navegador'],
          ],
        },
        {
          tipo: 'p',
          texto:
            'No envio manual por WhatsApp (link wa.me), a mensagem sai do WhatsApp do próprio usuário, sem passar pela Meta por meio do Toqqi.',
        },
        {
          tipo: 'p',
          texto:
            'Também podemos compartilhar dados com autoridades, quando a lei ou uma ordem judicial exigir, e em caso de fusão ou venda da empresa, com aviso a você e mantendo estas garantias.',
        },
      ],
    },
    {
      id: 'transferencia-internacional',
      titulo: 'Transferência para outros países',
      blocos: [
        {
          tipo: 'p',
          texto: [
            'Alguns fornecedores (como Render, OpenAI, ZeptoMail e Resend) ficam nos Estados Unidos. A transferência segue o art. 33 da LGPD: [a confirmar: mecanismo — cláusulas-padrão contratuais da ANPD (Resolução CD/ANPD nº 19/2024) nos contratos com os fornecedores]. Para os dados de quem usa o Toqqi, vale também a execução do contrato (art. 33, IX). Você pode pedir mais informações em ',
            { texto: 'privacidade@toqqi.com', href: 'mailto:privacidade@toqqi.com' },
            '.',
          ],
        },
      ],
    },
    {
      id: 'cookies',
      titulo: 'Cookies e armazenamento no navegador',
      blocos: [
        {
          tipo: 'p',
          texto:
            'O Toqqi não usa cookies. Também não usamos rastreadores de publicidade ou de análise, e nenhum terceiro coloca cookies ou rastreadores pelo Toqqi (a única exceção possível é o logo hospedado fora, explicado abaixo). O site guarda no seu navegador (localStorage e sessionStorage) apenas o necessário para funcionar. Pelo guia de cookies da ANPD, isso se apoia na execução do contrato e no legítimo interesse e não precisa de consentimento. Por isso, não há o que recusar.',
        },
        {
          tipo: 'tabela',
          colunas: ['Nome', 'Para que serve', 'Onde fica', 'Por quanto tempo'],
          linhas: [
            [
              'toqqi.sessao',
              'Manter você conectado: guarda o código da sessão e os dados básicos do usuário, da conta e das permissões.',
              'localStorage se você marcar "Lembrar de mim neste aparelho"; senão, sessionStorage',
              'No localStorage, até 30 dias ou até você sair. No sessionStorage, até fechar a aba ou o navegador.',
            ],
            [
              'toqqi.tema',
              'Lembrar se você prefere o tema claro ou escuro.',
              'localStorage',
              'Até você apagar os dados do navegador.',
            ],
            [
              'toqqi.menu-recolhido',
              'Lembrar se o menu lateral está recolhido.',
              'localStorage',
              'Até você apagar os dados do navegador.',
            ],
            [
              'toqqi.painel.passos-ocultos.{conta}',
              'Lembrar que você escondeu o quadro "Primeiros passos" do painel (uma chave por conta).',
              'localStorage',
              'Até você mostrar o quadro de novo ou apagar os dados do navegador.',
            ],
            [
              'toqqi.avisos-fechados',
              'Lembrar quais avisos de cobrança você fechou.',
              'sessionStorage',
              'Até fechar a aba ou o navegador.',
            ],
            [
              'toqqi.assistente.{conta}.{usuário}',
              'Guardar a conversa com o ToqqiAI (as últimas 20 mensagens), só neste navegador.',
              'sessionStorage',
              'Até fechar a aba, usar "Nova conversa" ou sair da conta.',
            ],
            [
              'toqqi.origem',
              'Lembrar de onde veio a visita ao site (só os parâmetros utm do link, como "pesquisa" e "rodape", nunca dados pessoais) para registrar a origem da conta no cadastro.',
              'sessionStorage',
              'Até concluir o cadastro ou fechar a aba.',
            ],
          ],
        },
        {
          tipo: 'p',
          texto:
            'A página onde os clientes das empresas respondem às pesquisas (incluindo o botão incorporado nos sites) e a página de descadastro não guardam nada no navegador: nem cookies, nem localStorage, nem sessionStorage. A resposta só é enviada ao Toqqi quando a pessoa a envia.',
        },
        {
          tipo: 'p',
          texto:
            'Se a empresa usar um logo hospedado fora do Toqqi, o navegador de quem abre a pesquisa ou o e-mail busca a imagem nesse endereço, que pode registrar o acesso.',
        },
        {
          tipo: 'p',
          texto:
            'A fonte das telas é servida pelo próprio Toqqi, sem chamar o Google Fonts. Você pode apagar esses dados quando quiser, nas configurações do navegador. O efeito é sair da conta e perder as preferências acima.',
        },
      ],
    },
    {
      id: 'retencao',
      titulo: 'Por quanto tempo guardamos',
      blocos: [
        {
          tipo: 'lista',
          itens: [
            'Dados da conta: enquanto ela estiver ativa.',
            'Depois do fim do período pago (quando a assinatura é cancelada) ou do teste grátis sem assinatura: guardamos os dados por 90 dias, para a empresa exportar. O administrador baixa uma cópia de todos os dados em Configurações › Dados da conta. Avisamos os administradores por e-mail 7 dias antes da exclusão. Passado o prazo, excluímos de forma definitiva e automática tudo o que é da conta, inclusive o registro de auditoria, o histórico de cobranças e os aceites dos termos. Assinar um plano antes disso cancela a exclusão.',
            'Registros de acesso (data, hora e IP das entradas e tentativas, do cadastro, do pedido de acesso, da troca de senha e do envio de respostas e indicações): por 6 meses (Marco Civil da Internet, art. 15), guardados à parte, mesmo depois de excluídos o usuário ou a conta. Depois disso, são apagados automaticamente.',
            'Registro de auditoria e histórico de cobranças: enquanto a conta existir. Os documentos fiscais seguem o prazo legal [a confirmar: prazo fiscal aplicável, em geral 5 anos].',
            'Respostas e contatos dos clientes: a empresa assinante controla e pode apagar quando quiser, um por um ou de uma vez (Configurações › Dados da conta › Zona de risco). Ao excluir um contato, o nome e o e-mail ficam no registro de auditoria enquanto a conta existir, e o e-mail ou telefone fica na lista de descadastro, para continuarmos respeitando o pedido da pessoa.',
            'Registro de e-mails enviados (endereço de quem recebeu, assunto, situação e erro): 90 dias. Depois disso, é apagado automaticamente.',
            'Cópias de segurança (backups): [a confirmar: se há backups e por quanto tempo].',
            'Histórico dos aceites dos termos (e das retiradas do aceite): guardado como prova, mesmo quando o texto muda, mesmo depois de o aceite ser retirado e mesmo depois que um usuário é removido da equipe (guardamos o e-mail e o nome de quem aceitou), com base no exercício regular de direitos (art. 7º, VI), enquanto a conta existir.',
          ],
        },
      ],
    },
    {
      id: 'seguranca',
      titulo: 'Como protegemos os dados',
      blocos: [
        {
          tipo: 'lista',
          itens: [
            'Senhas: guardamos só um código irreversível (hash argon2id), nunca a senha.',
            'Conexão cifrada (HTTPS).',
            'Isolamento dos dados de cada empresa no próprio banco.',
            'Segredos e chaves de integração cifrados.',
            'Registro de auditoria das ações na conta.',
            'Controle de acesso por perfil: cada usuário vê só o que o perfil permite.',
            'Registros de acesso em sigilo, fora das telas: nenhuma tela do Toqqi mostra esses registros. Só a equipe técnica consulta, e só para atender ordem judicial (Marco Civil da Internet, arts. 10 e 15).',
          ],
        },
        {
          tipo: 'p',
          texto:
            'Nenhum sistema é 100% seguro. Se houver incidente que possa causar risco ou dano relevante com dados de quem usa o Toqqi, comunicamos a ANPD e os afetados no prazo da regulamentação (hoje, 3 dias úteis, Resolução CD/ANPD nº 15/2024). Se for com dados dos clientes de uma empresa, avisamos a empresa em [a confirmar: prazo, sugerido 48 horas] para que ela comunique.',
        },
      ],
    },
    {
      id: 'seus-direitos',
      titulo: 'Seus direitos',
      blocos: [
        {
          tipo: 'p',
          texto: 'Pelo art. 18 da LGPD, você pode pedir:',
        },
        {
          tipo: 'lista',
          itens: [
            'confirmação de que tratamos seus dados;',
            'acesso aos dados;',
            'correção de dados incompletos, errados ou desatualizados;',
            'anonimização, bloqueio ou eliminação de dados desnecessários, excessivos ou tratados em desacordo com a lei;',
            'portabilidade dos dados (o administrador da empresa baixa uma cópia de todos os dados da conta, com uma planilha por assunto, em Configurações › Dados da conta);',
            'oposição a um tratamento feito sem consentimento, quando você achar que ele descumpre a lei (art. 18, § 2º);',
            'eliminação dos dados tratados com o seu consentimento;',
            'informação sobre com quem compartilhamos os dados;',
            'informação sobre a possibilidade de não consentir e suas consequências;',
            'revogação do consentimento, quando essa for a base legal (hoje não usamos o consentimento como base legal);',
            'revisão de decisões tomadas só por tratamento automatizado.',
          ],
        },
        {
          tipo: 'p',
          texto: [
            'Como pedir: escreva para ',
            { texto: 'privacidade@toqqi.com', href: 'mailto:privacidade@toqqi.com' },
            '. Parte dos seus dados você corrige direto em Minha conta. Podemos pedir informações para confirmar quem você é. Pelo art. 19 da LGPD, respondemos de forma simplificada na hora, ou de forma completa em até 15 dias.',
          ],
        },
        {
          tipo: 'p',
          texto:
            'Se você é cliente de uma empresa que usa o Toqqi, o seu pedido deve ir para essa empresa, que é a controladora dos seus dados. Se ele chegar até nós, encaminhamos a ela e avisamos você. Para não receber mais pesquisas, no e-mail use o link "Não quero mais receber pesquisas"; no WhatsApp, responda SAIR.',
        },
        {
          tipo: 'p',
          texto: [
            'Você também pode reclamar à Autoridade Nacional de Proteção de Dados (ANPD): ',
            { texto: 'www.gov.br/anpd', href: 'https://www.gov.br/anpd' },
            '.',
          ],
        },
      ],
    },
    {
      id: 'criancas',
      titulo: 'Crianças e adolescentes',
      blocos: [
        {
          tipo: 'p',
          texto: [
            'O Toqqi é feito para empresas e para usuários maiores de 18 anos. Não coletamos de propósito dados de crianças e adolescentes, nem dados de crianças sem o consentimento específico de um dos pais ou responsável (LGPD, art. 14). Se você achar que isso aconteceu, escreva para ',
            { texto: 'privacidade@toqqi.com', href: 'mailto:privacidade@toqqi.com' },
            ' para apagarmos.',
          ],
        },
      ],
    },
    {
      id: 'mudancas',
      titulo: 'Mudanças nesta política',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Podemos atualizar esta política. Quando a mudança for relevante, mostramos uma tela pedindo um novo aceite na próxima vez que você abrir o Toqqi. A versão e a data de vigência aparecem no topo desta página. O histórico dos aceites fica guardado como prova.',
        },
      ],
    },
  ],
}
