// Risco das contas em Plataforma › Contas (docs/api-plataforma-risco.md): o rótulo e o tom de cada nível, o texto de
// cada sinal e a lista das suspeitas (médio e alto), da maior nota para a menor. Sem Vue, para testar.
import type { ContaCitada, ContaPlataforma, RiscoConta, SinalRisco } from '@/api/tipos'
import { formatarData } from '@/utils/datas'
import { formatarNumero, plural } from '@/utils/formatos'
import type { Tom } from '@/utils/rotulos'

export const NIVEIS: Record<RiscoConta['nivel'], { rotulo: string; tom: Tom }> = {
  alto: { rotulo: 'Alto', tom: 'erro' },
  medio: { rotulo: 'Médio', tom: 'atencao' },
  baixo: { rotulo: 'Baixo', tom: 'neutro' },
}

const TERMOS: Record<Extract<SinalRisco, { tipo: 'formulario_sensivel' }>['termo'], string> = {
  senha: 'senha',
  cartao: 'dados de cartão',
  banco: 'dados bancários',
  codigo: 'código de verificação',
}

/** "Alfa", "Alfa e Beta", "Alfa, Beta e Gama", "Alfa, Beta, Gama e mais 2". */
function nomes(contas: ContaCitada[], total: number): string {
  const lista = contas.map((c) => c.nome)
  const resto = total - lista.length
  if (resto > 0) return `${lista.join(', ')} e mais ${formatarNumero(resto)}`
  return lista.length > 1 ? `${lista.slice(0, -1).join(', ')} e ${lista.at(-1)}` : (lista[0] ?? '')
}

/** "Alfa"; "2 contas: Alfa e Beta". */
function quem(s: { contas: ContaCitada[]; total: number }): string {
  return s.total === 1 ? nomes(s.contas, s.total) : `${formatarNumero(s.total)} contas: ${nomes(s.contas, s.total)}`
}

/** O motivo, curto, para quem passa o olho na lista. */
export function textoSinal(s: SinalRisco): string {
  switch (s.tipo) {
    case 'email_temporario':
      return `E-mail temporário (${s.dominio})`
    case 'email_pessoal':
      return `E-mail pessoal (${s.dominio})`
    case 'email_nao_confirmado':
      return `E-mail não confirmado há ${plural(s.dias, 'dia', 'dias')}`
    case 'nome_de_teste':
      return 'Nome de empresa de teste'
    case 'documento_repetido':
      return `${s.documento === 'cpf' ? 'CPF' : 'CNPJ'} igual ao de ${quem(s)}`
    case 'telefone_repetido':
      return `Telefone igual ao de ${quem(s)}`
    case 'dominio_repetido':
      return `Domínio ${s.dominio} também em ${quem(s)}`
    case 'nome_repetido':
      return `Nome igual ao de ${quem(s)}`
    case 'descadastros':
      return `${s.taxa}% saíram da lista (${formatarNumero(s.saidas)} de ${formatarNumero(s.destinatarios)} em 30 dias)`
    case 'invalidos':
      return `${s.taxa}% dos envios para endereço ou número que não existe (${formatarNumero(s.invalidos)} de ${formatarNumero(s.tentativas)} em 30 dias)`
    case 'sem_respostas':
      return `${s.respostas ? plural(s.respostas, 'resposta', 'respostas') : 'Nenhuma resposta'} em ${formatarNumero(s.convites)} pesquisas (30 dias)`
    case 'volume_inicio':
      return `${s.dias < 1 ? 'Conta criada hoje' : `Conta de ${plural(s.dias, 'dia', 'dias')}`} já fez ${formatarNumero(s.envios)} envios`
    case 'formulario_sensivel':
      return `Formulário “${s.formulario.nome}” pede ${TERMOS[s.termo]}`
    case 'estorno':
      return s.quantas === 1
        ? `Pagamento estornado em ${formatarData(s.ultima_em)}`
        : `${formatarNumero(s.quantas)} pagamentos estornados (último em ${formatarData(s.ultima_em)})`
  }
}

/** O trecho que explica o sinal, quando há (a pergunta do formulário), para mostrar entre aspas embaixo. */
export function detalheSinal(s: SinalRisco): string | null {
  return s.tipo === 'formulario_sensivel' ? `“${s.trecho}”` : null
}

/** Médio ou alto: entra em "Suspeitas". */
export function suspeita(c: ContaPlataforma): boolean {
  return !!c.risco && c.risco.nivel !== 'baixo'
}

/** As suspeitas, da maior nota para a menor (empate: a mais nova primeiro, a ordem da lista). */
export function suspeitas(contas: ContaPlataforma[]): ContaPlataforma[] {
  return contas
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => suspeita(c))
    .sort((a, b) => b.c.risco!.pontos - a.c.risco!.pontos || a.i - b.i)
    .map(({ c }) => c)
}
