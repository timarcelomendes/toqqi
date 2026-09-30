"""Chamadas HTTP de saída para endereços informados pelo cliente (ex.: webhook do Teams).

Proteção contra SSRF: só https, o nome precisa resolver apenas para IPs públicos e a conexão é feita
direto no IP conferido (o nome vai no Host e no SNI), sem seguir redirecionamentos.
"""
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx

_NOMES_PROIBIDOS = ("localhost", ".localhost", ".local", ".internal", ".lan", ".home", ".corp")


class EnderecoProibido(ValueError):
    pass


def ip_publico(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_global and not (a.is_private or a.is_loopback or a.is_link_local or a.is_reserved
                                or a.is_multicast or a.is_unspecified)


def conferir_url_https(url: str) -> str:
    """Checagem sem DNS (usada ao salvar): https, com nome, sem credenciais, sem IP/nome interno."""
    try:
        partes = urlsplit(url.strip())
        porta = partes.port
    except ValueError:
        raise EnderecoProibido("Endereço inválido.")
    if partes.scheme != "https" or not partes.hostname:
        raise EnderecoProibido("Use um endereço https://.")
    if partes.username or partes.password:
        raise EnderecoProibido("O endereço não pode ter usuário e senha.")
    if porta not in (None, 443):
        raise EnderecoProibido("Use a porta padrão do https.")
    host = partes.hostname.lower().rstrip(".")
    if host == "localhost" or host.endswith(_NOMES_PROIBIDOS) or "." not in host and ":" not in host:
        raise EnderecoProibido("O endereço precisa ser público.")
    try:
        ipaddress.ip_address(host)
        eh_ip = True
    except ValueError:
        eh_ip = False
    if eh_ip and not ip_publico(host):
        raise EnderecoProibido("O endereço precisa ser público.")
    return url.strip()


def resolver(host: str) -> list[str]:
    """Todos os IPs do nome (trocável nos testes)."""
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return sorted({i[4][0] for i in infos})


def enviar_post(url: str, ip: str, host: str, corpo: dict) -> httpx.Response:
    """POST direto no IP conferido (trocável nos testes)."""
    partes = urlsplit(url)
    ip_url = f"[{ip}]" if ":" in ip else ip
    alvo = urlunsplit((partes.scheme, ip_url, partes.path or "/", partes.query, ""))
    with httpx.Client(timeout=10, follow_redirects=False) as c:
        return c.post(alvo, json=corpo, headers={"Host": host}, extensions={"sni_hostname": host})


def post_json_seguro(url: str, corpo: dict) -> httpx.Response:
    """Levanta EnderecoProibido se o destino não for público; httpx.HTTPError em falha de rede."""
    conferir_url_https(url)
    host = urlsplit(url).hostname.lower().rstrip(".")
    try:
        ips = resolver(host)
    except OSError:
        raise EnderecoProibido("Não foi possível encontrar este endereço.")
    if not ips or not all(ip_publico(ip) for ip in ips):
        raise EnderecoProibido("O endereço precisa ser público.")
    return enviar_post(url, ips[0], host, corpo)
