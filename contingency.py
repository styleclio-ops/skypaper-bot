import urllib.request
import time
import logging
import asyncio
from typing import Dict, Any
from analytics import record_site_health

logger = logging.getLogger("skypaper_bot.contingency")

MONITORED_SITES = {
    "skypaper_site": "https://skypaperinc.com.br/",
    "hidrahome_portal": "https://comprarskypaper.hidrahome.com.br/"
}

# Estado dos sites em memória
SITE_HEALTH: Dict[str, Dict[str, Any]] = {
    "skypaper_site": {"is_up": True, "status_code": 200, "latency_ms": 0, "last_check": None},
    "hidrahome_portal": {"is_up": True, "status_code": 200, "latency_ms": 0, "last_check": None}
}

def _sync_check_site(url: str) -> tuple[int, bool, int]:
    """Checa um site de forma síncrona com urllib."""
    start_time = time.time()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SkyPaper-HealthMonitor/3.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            latency_ms = int((time.time() - start_time) * 1000)
            status_code = resp.status
            is_up = 200 <= status_code < 400
            return status_code, is_up, latency_ms
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return e.code, e.code < 500, latency_ms
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Erro ao checar site {url}: {e}")
        return 500, False, latency_ms

async def check_single_site(site_key: str, url: str) -> Dict[str, Any]:
    """Testa a conectividade de um site de forma assíncrona sem travar o event loop."""
    status_code, is_up, latency_ms = await asyncio.to_thread(_sync_check_site, url)
    
    SITE_HEALTH[site_key] = {
        "is_up": is_up,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "last_check": time.time()
    }
    record_site_health(site_key, url, status_code, is_up, latency_ms)
    return SITE_HEALTH[site_key]

async def check_all_sites():
    """Executa checagem de todos os sites monitorados em paralelo."""
    tasks = [check_single_site(k, u) for k, u in MONITORED_SITES.items()]
    await asyncio.gather(*tasks, return_exceptions=True)

async def periodic_healthcheck_loop(interval_seconds: int = 600):
    """Loop em background que roda a cada 10 minutos para monitorar a saúde dos portais."""
    logger.info(f"Iniciando monitoramento de saúde de sites (intervalo: {interval_seconds}s)")
    while True:
        try:
            await check_all_sites()
        except Exception as e:
            logger.error(f"Erro no loop de healthcheck: {e}")
        await asyncio.sleep(interval_seconds)

def get_contingency_response(issue_type: str = "geral") -> str:
    """Gera resposta de contingência quando um cliente relata erro ou quando o site está instável."""
    return (
        "Poxa, muito obrigado por nos avisar! 🙏✨ Nossa equipe técnica já foi acionada para verificar o acesso ao site.\n\n"
        "Mas não se preocupe, você não fica na mão! Preparamos opções imediatas para te atender:\n\n"
        "💼 Atendimento Comercial Direto no WhatsApp: (11) 97825-7833 (condições de atacado e compras)\n"
        "📒 Catálogo Alternativo de Produtos: https://skypaperinc.com.br/produtos/\n"
        "📧 E-mail de Suporte / Pedidos: sac@skypaperinc.com.br\n\n"
        "Se preferir, me diga por aqui qual produto ou informação você procura que te passo todos os detalhes agora mesmo! 🌸🕊️"
    )

def is_b2b_portal_up() -> bool:
    """Retorna se o portal de lojistas está operacional."""
    return SITE_HEALTH.get("hidrahome_portal", {}).get("is_up", True)
