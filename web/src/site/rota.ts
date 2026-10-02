/** Fica sozinho para a entrada do app (entrada.ts) não carregar o resto da lógica do site. */

/** O endereço é a página do site? Só a raiz: o resto é o app (e /r, /f, /sair vão para responder.html). */
export function ehSite(caminho: string): boolean {
  return caminho === '/' || caminho === '' || caminho === '/index.html'
}
