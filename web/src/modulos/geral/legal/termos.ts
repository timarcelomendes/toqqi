import type { DocumentoLegal } from './tipos'

export const TERMOS: DocumentoLegal = {
  titulo: 'Termos de uso',
  introducao: [
    {
      tipo: 'p',
      texto: [
        'Estes Termos de uso valem entre o Toqqi e a empresa que contrata o serviço (a "Empresa"), e também para cada pessoa que usa o Toqqi em nome dela (o "Usuário"). Ao criar a conta ou clicar em "Aceitar e continuar", você declara que leu e concorda com estes Termos e com a ',
        { texto: 'Política de privacidade', href: '/privacidade' },
        '.',
      ],
    },
    {
      tipo: 'p',
      texto:
        'Se você aceita em nome de uma empresa, declara ter poder para isso. Neste texto, "nós" e "Toqqi" são a plataforma de pesquisas de satisfação (NPS e CSAT) e quem a opera.',
    },
  ],
  secoes: [
    {
      id: 'quem-somos',
      titulo: 'Quem somos',
      blocos: [
        {
          tipo: 'p',
          texto:
            'O Toqqi é operado por [a confirmar: razão social], CNPJ [a confirmar: CNPJ], com sede em [a confirmar: endereço completo].',
        },
        {
          tipo: 'p',
          texto: [
            'Para dúvidas gerais, escreva para ',
            { texto: 'contato@toqqi.com', href: 'mailto:contato@toqqi.com' },
            '. Para assuntos de dados pessoais, escreva para ',
            { texto: 'privacidade@toqqi.com', href: 'mailto:privacidade@toqqi.com' },
            '.',
          ],
        },
      ],
    },
    {
      id: 'o-servico',
      titulo: 'O que é o Toqqi',
      blocos: [
        {
          tipo: 'p',
          texto:
            'O Toqqi é um sistema na internet para a Empresa medir a satisfação dos próprios clientes. Com ele você cadastra empresas e contatos, envia pesquisas por e-mail e WhatsApp, recebe as respostas, acompanha NPS e CSAT em painéis e relatórios e organiza planos de ação.',
        },
        {
          tipo: 'p',
          texto:
            'Também há recursos de inteligência artificial (IA). A análise de comentários já vem ligada, e a Empresa pode desligá-la em Configurações › IA. Ela classifica temas e sentimento automaticamente, e a Empresa pode corrigir o resultado. O assistente de perguntas fica disponível para os usuários da conta enquanto a IA estiver disponível e a assinatura estiver em dia, e só envia dados quando alguém faz uma pergunta.',
        },
        {
          tipo: 'p',
          texto:
            'As respostas da IA podem conter erros: confira antes de decidir algo importante com base nelas.',
        },
        {
          tipo: 'p',
          texto:
            'Novas funções podem ser criadas, mudadas ou retiradas ao longo do tempo. Se uma mudança tirar algo essencial do seu plano, avisamos com antecedência razoável. Nesse caso, você pode cancelar e receber o valor proporcional já pago.',
        },
      ],
    },
    {
      id: 'conta',
      titulo: 'Conta e acesso',
      blocos: [
        {
          tipo: 'lista',
          itens: [
            'Quem cria a conta precisa ser maior de 18 anos e ter poder para contratar pela Empresa.',
            'Os dados do cadastro devem ser verdadeiros e mantidos em dia.',
            'Cada pessoa usa o próprio acesso. Não compartilhe a senha. Você responde pelo que for feito com o seu acesso, salvo se o acesso indevido vier de falha nossa.',
            'O administrador da conta convida e remove usuários e define o perfil de cada um.',
            'Se suspeitar de uso indevido do seu acesso, troque a senha e avise-nos pelo contato acima.',
          ],
        },
      ],
    },
    {
      id: 'planos-e-pagamento',
      titulo: 'Planos, teste grátis e pagamento',
      blocos: [
        {
          tipo: 'p',
          texto:
            'O Toqqi tem os planos Essencial, Profissional e Empresa. Cada plano tem limites e recursos próprios, mostrados na tela de assinatura. Os preços e limites vigentes são os que aparecem lá no momento da contratação.',
        },
        {
          tipo: 'lista',
          itens: [
            'Teste grátis: quando houver, vale pelo período informado na tela. Ao final, a conta precisa de um plano pago para continuar enviando pesquisas.',
            'Cobrança: mensal, pelo Asaas, por boleto, Pix ou cartão, conforme as opções oferecidas.',
            'Atraso: se o pagamento atrasar, avisamos e damos 7 dias. Passado esse prazo, os envios de pesquisas e os recursos de IA são pausados até a regularização. Avisamos no topo das telas. Seus dados continuam guardados e você continua vendo o que já coletou.',
            'Cancelamento: você pode cancelar quando quiser. O plano vale até o fim do período já pago, sem nova cobrança depois disso.',
            'Reajuste: podemos reajustar os preços, avisando com pelo menos [a confirmar: prazo de aviso de reajuste, sugerido 30 dias] de antecedência. O novo valor vale a partir da renovação seguinte. Se não concordar com o reajuste, você pode cancelar sem multa antes do novo valor valer.',
            'Arrependimento (Código de Defesa do Consumidor, art. 49, quando aplicável): [a confirmar: cancelando em até 7 dias da primeira cobrança, devolvemos o valor pago].',
            'Reembolso: fora o caso de arrependimento, não devolvemos o período já pago, salvo cobrança feita por engano e o valor proporcional quando uma função essencial for retirada do seu plano.',
          ],
        },
      ],
    },
    {
      id: 'uso-aceitavel',
      titulo: 'Uso aceitável',
      blocos: [
        {
          tipo: 'p',
          texto: 'Você se compromete a usar o Toqqi de forma legal e respeitosa. Em especial:',
        },
        {
          tipo: 'lista',
          itens: [
            'Envie pesquisas só a pessoas com quem a Empresa tem relação de cliente ou de atendimento. Não é permitido enviar mensagens em massa a quem não tem relação com a Empresa (spam).',
            'Respeite o descadastro: quem pedir para não receber mais pesquisas não pode ser contatado de novo, e o Toqqi bloqueia esses envios. Nas mensagens de WhatsApp, inclua como a pessoa pode parar de receber (por exemplo, "responda SAIR").',
            'Não use o serviço para conteúdo ilegal, ofensivo, discriminatório, enganoso ou que viole direitos de terceiros.',
            'Não tente burlar limites do plano, acessar dados de outras contas, derrubar ou sobrecarregar o serviço, nem fazer engenharia reversa.',
            'Não use o Toqqi para pedir dados sensíveis (como saúde, religião ou biometria), nem dados de crianças sem o consentimento específico de um dos pais ou responsável (LGPD, art. 14).',
            'Respeite as regras das plataformas que você conectar, como as da Meta para o WhatsApp.',
          ],
        },
      ],
    },
    {
      id: 'responsabilidades-da-empresa',
      titulo: 'Responsabilidades da Empresa',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Os contatos e as respostas dos clientes da Empresa são dados da Empresa. Por isso, ela é a controladora desses dados e deve:',
        },
        {
          tipo: 'lista',
          itens: [
            'ter base legal (LGPD, art. 7º) para contatar cada pessoa, e informá-la de forma clara sobre o uso dos dados dela;',
            'importar apenas dados que realmente precise para a pesquisa;',
            'atender os pedidos dos titulares (acesso, correção, exclusão, descadastro). O Toqqi oferece ferramentas para isso e ajuda no que for preciso;',
            'manter atualizados os usuários da conta e remover quem saiu da empresa;',
            'responder pelo conteúdo que escreve nas pesquisas e nas mensagens enviadas.',
          ],
        },
      ],
    },
    {
      id: 'tratamento-de-dados',
      titulo: 'Tratamento de dados pessoais (acordo entre controladora e operador)',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Esta seção vale como acordo de tratamento de dados entre a Empresa (controladora) e o Toqqi (operador) para os dados dos clientes da Empresa. Para os dados de quem usa o Toqqi, o controlador é o próprio Toqqi, como explicado na Política de privacidade.',
        },
        {
          tipo: 'lista',
          itens: [
            'Objeto: tratar os dados que a Empresa importa ou coleta pelo Toqqi (nome, e-mail, telefone, empresa, CPF/CNPJ da empresa cliente, cargo, valor mensal, "cliente desde", dados do pedido ou atendimento, respostas, notas, comentários, situação dos envios e anotações dos planos de ação) para prestar o serviço contratado.',
            'Instruções: o Toqqi trata esses dados só conforme as instruções da Empresa, que são o uso normal das funções do sistema e estes Termos. Se uma instrução violar a lei, avisamos.',
            [
              'Suboperadores: a Empresa autoriza o uso dos fornecedores listados na ',
              { texto: 'Política de privacidade', href: '/privacidade#compartilhamento' },
              '. Avisamos sobre mudanças relevantes na lista, e a Empresa pode se opor por motivo justificado. Se a troca de suboperador não tiver acordo, a Empresa pode cancelar sem multa.',
            ],
            'Sigilo: quem trabalha no Toqqi e acessa esses dados tem dever de confidencialidade.',
            [
              'Segurança: mantemos as medidas descritas na ',
              { texto: 'Política de privacidade', href: '/privacidade' },
              '.',
            ],
            'Registro e comprovação: mantemos o registro das operações de tratamento (LGPD, art. 37) e damos à Empresa as informações de que ela precisa para comprovar o cumprimento da lei, inclusive para um relatório de impacto.',
            'Dados anonimizados: a Empresa autoriza o uso de dados anonimizados e agregados (que não identificam ninguém) para melhorar o serviço.',
            'Incidentes: se houver incidente de segurança com dados dos clientes da Empresa, avisamos a Empresa em [a confirmar: prazo para avisar a Empresa, sugerido 48 horas], com as informações que tivermos, para ela comunicar a ANPD e os titulares.',
            'Ajuda com os titulares: encaminhamos à Empresa os pedidos que recebermos e ajudamos a atendê-los (por exemplo, exclusão de contato e descadastro).',
            'Fim do contrato: depois do cancelamento, a Empresa pode exportar os dados dela durante [a confirmar: prazo, sugerido 90 dias], contados do fim do período pago. Pelo sistema, a Empresa exporta as respostas e os relatórios. Os demais dados, ela pede por contato@toqqi.com. Depois do prazo, eliminamos os dados [a confirmar: como os dados são eliminados], salvo o que a lei nos obrigar a guardar. Se a Empresa pedir, confirmamos a exclusão.',
            'Transferência internacional: alguns suboperadores ficam nos Estados Unidos. A transferência segue o art. 33 da LGPD: [a confirmar: mecanismo — cláusulas-padrão contratuais da ANPD (Resolução CD/ANPD nº 19/2024) nos contratos com os fornecedores].',
          ],
        },
      ],
    },
    {
      id: 'disponibilidade',
      titulo: 'Disponibilidade e suporte',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Trabalhamos para manter o Toqqi no ar o tempo todo, mas não prometemos disponibilidade de 100%. Pode haver paradas para manutenção, falhas de internet ou de fornecedores (hospedagem, e-mail, WhatsApp, pagamento) que não controlamos. Quando possível, avisamos antes das paradas programadas.',
        },
        {
          tipo: 'p',
          texto: [
            'O suporte é feito por e-mail, em ',
            { texto: 'contato@toqqi.com', href: 'mailto:contato@toqqi.com' },
            ', em dias úteis. Prazo de resposta: [a confirmar: prazo de resposta do suporte].',
          ],
        },
      ],
    },
    {
      id: 'propriedade-intelectual',
      titulo: 'Propriedade intelectual',
      blocos: [
        {
          tipo: 'lista',
          itens: [
            'O Toqqi (software, marca, telas, textos e design) pertence a nós. Você recebe o direito de uso do serviço enquanto o contrato valer, sem exclusividade e sem poder transferir a outros.',
            'Os dados e conteúdos que a Empresa coloca no Toqqi continuam sendo dela. Ela nos autoriza a tratá-los só para prestar o serviço.',
            'Podemos usar dados agregados e anonimizados (que não identificam a Empresa nem as pessoas) para melhorar o serviço e fazer estatísticas.',
            'Se você enviar sugestões, podemos usá-las sem qualquer pagamento.',
          ],
        },
      ],
    },
    {
      id: 'limitacao-de-responsabilidade',
      titulo: 'Limitação de responsabilidade',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Prestamos o serviço com cuidado, mas Não garantimos um resultado específico com o uso do Toqqi (por exemplo, uma nota ou taxa de resposta). A Empresa decide como usar os resultados.',
        },
        {
          tipo: 'p',
          texto:
            'Na medida permitida pela lei, não respondemos por lucros cessantes, perda de negócios nem danos indiretos. Nossa responsabilidade total por danos ligados ao serviço fica limitada a [a confirmar: limite de responsabilidade, sugerido o valor pago pela Empresa nos 12 meses anteriores ao fato].',
        },
        {
          tipo: 'p',
          texto:
            'Essa limitação não vale nos casos em que a lei não permite limitar (como dolo ou culpa grave) e não afasta direitos do consumidor, quando a lei de consumo se aplicar.',
        },
      ],
    },
    {
      id: 'suspensao-e-encerramento',
      titulo: 'Suspensão e encerramento',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Podemos suspender ou encerrar uma conta, com aviso, se houver violação destes Termos, uso que ponha em risco o serviço ou outras contas, ordem de autoridade ou falta de pagamento (como descrito acima). Em caso grave ou urgente, podemos suspender na hora e explicar depois.',
        },
        {
          tipo: 'p',
          texto:
            'Quando possível, damos à Empresa a chance de corrigir o problema. Depois do encerramento, valem as regras de exportação e eliminação de dados da seção sobre tratamento de dados.',
        },
      ],
    },
    {
      id: 'mudancas-nos-termos',
      titulo: 'Mudanças nestes Termos',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Podemos atualizar estes Termos e a Política de privacidade. Avisamos com pelo menos [a confirmar: prazo de aviso antes de mudar os termos, sugerido 15 dias] de antecedência. Quando a mudança for relevante, mostramos uma tela pedindo um novo aceite na próxima vez que você abrir o Toqqi. Guardamos o histórico dos aceites (quem, quando, qual versão, IP e navegador) como prova, mesmo depois que um usuário é removido da equipe. Nesse caso, guardamos o e-mail e o nome de quem aceitou.',
        },
        {
          tipo: 'p',
          texto:
            'Se você não concordar com a versão nova, não precisa aceitar: o administrador da conta pode cancelar a assinatura na tela Assinatura, que continua disponível sem o aceite, ou pedir por contato@toqqi.com. Não cobraremos o período seguinte. Os demais usuários não conseguem usar o site até aceitar.',
        },
        {
          tipo: 'p',
          texto: [
            'Você também pode retirar o seu aceite destes Termos e da Política de privacidade quando quiser, em ',
            { texto: 'Minha conta › Privacidade › Retirar meu aceite', href: '/minha-conta' },
            '. Ao retirar, você sai do Toqqi em todos os aparelhos e só volta a usá-lo aceitando de novo; guardamos o registro do aceite anterior e da retirada como prova. Retirar o aceite não cancela a assinatura: para encerrar o uso pela Empresa, o administrador cancela a assinatura.',
          ],
        },
      ],
    },
    {
      id: 'lei-e-foro',
      titulo: 'Lei aplicável e foro',
      blocos: [
        {
          tipo: 'p',
          texto:
            'Estes Termos seguem as leis do Brasil. Para resolver qualquer disputa, fica eleito o foro da comarca de [a confirmar: comarca], com renúncia a qualquer outro, ressalvado o direito do consumidor de ajuizar ação no foro do seu domicílio, quando a lei de consumo se aplicar.',
        },
        {
          tipo: 'p',
          texto: [
            'Antes de recorrer à Justiça, procure-nos em ',
            { texto: 'contato@toqqi.com', href: 'mailto:contato@toqqi.com' },
            ': a maioria dos problemas se resolve conversando. Veja também a ',
            { texto: 'Política de privacidade', href: '/privacidade' },
            '.',
          ],
        },
      ],
    },
  ],
}
