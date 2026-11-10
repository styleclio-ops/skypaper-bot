import urllib.request
import time
import logging
import asyncio
from typing import Dict, Any
from analytics import (
    record_site_health,
    get_pending_site_notifications,
    mark_site_notification_sent
)

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

async def notify_pending_users_for_site(site_key: str, site_url: str):
    """Notifica proativamente clientes que tentaram acessar durante a instabilidade e foram cadastrados na fila."""
    from meta_client import send_dm
    try:
        pending = get_pending_site_notifications(site_key)
        if not pending:
            return

        logger.info(f"Site {site_key} está online! Notificando {len(pending)} clientes em espera...")
        for item in pending:
            user_id = item["user_id"]
            notif_id = item["id"]
            recovery_msg = (
                "Olá! Passando para te avisar que o nosso site já foi totalmente restabelecido e está funcionando normalmente! 🚀✨\n\n"
                f"Você já pode acessar e conferir todas as novidades com tranquilidade: {site_url}\n\n"
                "Se precisar de mais alguma informação ou ajuda, estou à disposição por aqui! 📒💖"
            )
            success = await send_dm(user_id, recovery_msg)
            if success:
                mark_site_notification_sent(notif_id)
                logger.info(f"Cliente {user_id} notificado com sucesso sobre a volta do site {site_key}.")
            await asyncio.sleep(0.5) # Pausa leve entre envios
    except Exception as e:
        logger.error(f"Erro ao notificar clientes de contingência para {site_key}: {e}", exc_info=True)

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

    # Se o site estiver saudável (is_up == True), verifica se há clientes aguardando aviso
    if is_up:
        await notify_pending_users_for_site(site_key, url)

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
    """Gera resposta de contingência quando um cliente relata erro ou quando o site está instável (sem WhatsApp)."""
    return (
        "Pedimos desculpas pela instabilidade no momento! 🙏 Nossa equipe técnica já foi acionada "
        "para normalizar o acesso o quanto antes.\n\n"
        "Assim que o site for restabelecido, eu mesmo retorno e te aviso por aqui no direct! 🌸🕊️\n\n"
        "Se tiver qualquer dúvida urgente, nosso e-mail oficial é sac@skypaperinc.com.br."
    )

def is_b2b_portal_up() -> bool:
    """Retorna se o portal de lojistas está operacional."""
    return SITE_HEALTH.get("hidrahome_portal", {}).get("is_up", True)
