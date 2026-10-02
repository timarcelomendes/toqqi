/**
 * Entrada de index.html. A raiz ("/") é a página do site, que já está pronta no HTML e só precisa de site.ts; qualquer
 * outro endereço é o app (o servidor manda index.html para todas as rotas). Assim o site abre leve, sem carregar o
 * app, e nada muda no servidor (README: "Duas entradas").
 */
import { ehSite } from './site/rota'

if (ehSite(window.location.pathname)) {
  void import('./site/site')
} else {
  document.getElementById('site')?.remove()
  void import('./main')
}
