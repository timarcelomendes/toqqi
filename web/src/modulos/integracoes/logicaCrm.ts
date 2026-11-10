// Textos dos conectores do Pipedrive e do HubSpot (SecaoCrm.vue). Os caminhos foram conferidos nas centrais de ajuda em
// 10/11/2026: Pipedrive (Configurações › Preferências pessoais › API) e HubSpot (Development › Keys › Service keys; desde
// 26/10/2026 o HubSpot não cria aplicativos privados novos).
import type { ChaveCrm } from '@/api'

/** Um pedaço de um passo: texto, texto em negrito ou link. */
export type ParteDoPasso = string | { forte: string } | { link: string; texto: string }

export interface TextosCrm {
  nome: string
  iniciais: string
  rotuloToken: string
  erroVazio: string
  /** "o token", "a chave": no aviso de desconectar. */
  oToken: string
  passos: ParteDoPasso[][]
  descricaoPesquisa: string
  oQueFaz: { titulo: string; texto: string }[]
}

const EMPRESAS = (nome: string) => ({
  titulo: 'Empresas e contatos',
  texto: `“Sincronizar agora” traz as empresas e as pessoas do ${nome} que ainda não estão no Toqqi, com e-mail ou telefone, cada uma ligada à sua empresa. Nunca apaga nem muda o que já existe aqui, e respeita o limite de contatos do plano.`,
})
const AINDA_NAO = (nome: string) => ({
  titulo: 'Ainda não faz',
  texto: `Não atualiza no Toqqi os dados já cadastrados (nome, e-mail, telefone) quando mudam no ${nome}; para isso, use o Toqqi ou a importação.`,
})

export const TEXTOS_CRM: Record<ChaveCrm, TextosCrm> = {
  pipedrive: {
    nome: 'Pipedrive',
    iniciais: 'PD',
    rotuloToken: 'Token de API',
    erroVazio: 'Cole o token de API do Pipedrive.',
    oToken: 'o token',
    passos: [
      ['No Pipedrive, abra ', { forte: 'Configurações › Preferências pessoais › API' }, ' e copie o seu token de API pessoal.'],
      ['Cole aqui e conecte. O token fica guardado cifrado e só é usado para falar com o Pipedrive.'],
    ],
    descricaoPesquisa: 'Quando um negócio vira ganho, os participantes dele recebem a pesquisa NPS, pelas regras de envio da conta (descadastro, descanso e canal).',
    oQueFaz: [
      EMPRESAS('Pipedrive'),
      { titulo: 'Pesquisa no negócio ganho', texto: 'Ligada, o Toqqi cadastra um aviso no Pipedrive. Quando um negócio vira ganho, as pessoas dele recebem a pesquisa NPS na hora, uma vez por negócio, pelas regras de envio da conta.' },
      { titulo: 'A nota de volta no Pipedrive', texto: 'Quando o cliente responde, o Toqqi anota no negócio a nota e o comentário (em até 30 minutos), para o vendedor ver sem sair do CRM.' },
      { titulo: 'Segurança', texto: 'O token fica cifrado e só é usado para falar com o Pipedrive. Ele tem as permissões do seu usuário: conecte com um usuário que vê os negócios da equipe. Desconectar apaga o token e remove o aviso no Pipedrive.' },
      AINDA_NAO('Pipedrive'),
    ],
  },
  hubspot: {
    nome: 'HubSpot',
    iniciais: 'HS',
    rotuloToken: 'Chave de serviço',
    erroVazio: 'Cole a chave de serviço do HubSpot.',
    oToken: 'a chave',
    passos: [
      ['No HubSpot, com um usuário superadministrador, abra ', { forte: 'Development › Keys › Service keys' }, ' e clique em ', { forte: 'Create service key' }, '.'],
      ['Dê o nome “Toqqi” e adicione os escopos ', { forte: 'crm.objects.contacts.read' }, ', ', { forte: 'crm.objects.companies.read' }, ' e ', { forte: 'crm.objects.deals.read' }, '. Crie e copie a chave (', { forte: 'Show › Copy' }, ').'],
      ['Cole aqui e conecte. Se você já tem um aplicativo privado com esses escopos, o token dele também serve.'],
    ],
    descricaoPesquisa: 'A cada 30 minutos, o Toqqi confere os negócios ganhos e os contatos deles recebem a pesquisa NPS, pelas regras de envio da conta (descadastro, descanso e canal).',
    oQueFaz: [
      EMPRESAS('HubSpot'),
      { titulo: 'Pesquisa no negócio ganho', texto: 'Ligada, o Toqqi confere a cada 30 minutos os negócios que viraram ganhos desde a última vez. Os contatos de cada um recebem a pesquisa NPS, uma vez por negócio, pelas regras de envio da conta. Negócios ganhos antes de ligar não recebem.' },
      { titulo: 'Segurança', texto: 'A chave fica cifrada e só lê contatos, empresas e negócios: o Toqqi não altera nada no HubSpot. Desconectar apaga a chave aqui; para cortar de vez, apague a chave também no HubSpot.' },
      { titulo: 'Ainda não faz', texto: 'Não devolve a nota ao HubSpot e não atualiza no Toqqi os dados já cadastrados (nome, e-mail, telefone) quando mudam no HubSpot.' },
    ],
  },
}
