// Trava a rolagem da página enquanto houver janela aberta (modal, painel lateral).
// Conta quantas estão abertas: fechar uma confirmação por cima de um painel não destrava a página.
let travas = 0

export function travarRolagem(): void {
  travas++
  document.body.style.overflow = 'hidden'
}

export function liberarRolagem(): void {
  travas = Math.max(0, travas - 1)
  if (!travas) document.body.style.overflow = ''
}
