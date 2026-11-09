import logging
import httpx
from config import META_GRAPH_URL, META_PAGE_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID

logger = logging.getLogger("skypaper_bot")

async def send_dm(recipient_id: str, text: str) -> bool:
    """Envia uma mensagem direta (DM) para um usuário no Instagram."""
    if not META_PAGE_ACCESS_TOKEN:
        logger.error("META_PAGE_ACCESS_TOKEN não configurado!")
        return False

    url = f"{META_GRAPH_URL}/{INSTAGRAM_ACCOUNT_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info(f"DM enviada com sucesso para {recipient_id}")
                return True
            else:
                logger.error(f"Erro ao enviar DM: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Exceção ao enviar DM para {recipient_id}: {e}", exc_info=True)
        return False

async def send_private_reply_to_comment(comment_id: str, text: str) -> bool:
    """
    Envia uma DM privada para o autor de um comentário em QUALQUER post ou Reel.
    Usa o endpoint oficial da Meta Graph API com {"recipient": {"comment_id": comment_id}}.
    """
    if not META_PAGE_ACCESS_TOKEN:
        logger.error("META_PAGE_ACCESS_TOKEN não configurado!")
        return False

    url = f"{META_GRAPH_URL}/{INSTAGRAM_ACCOUNT_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": text}
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info(f"DM privada enviada com sucesso para o comentário {comment_id}")
                return True
            else:
                logger.error(f"Erro ao enviar DM privada para comentário: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Exceção ao enviar DM para comentário {comment_id}: {e}", exc_info=True)
        return False

async def send_public_comment_reply(comment_id: str, text: str) -> bool:
    """Responde publicamente ao comentário no post ou Reel."""
    if not META_PAGE_ACCESS_TOKEN:
        logger.error("META_PAGE_ACCESS_TOKEN não configurado!")
        return False

    url = f"{META_GRAPH_URL}/{comment_id}/replies"
    headers = {
        "Authorization": f"Bearer {META_PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"message": text}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info(f"Resposta pública enviada com sucesso para comentário {comment_id}")
                return True
            else:
                logger.error(f"Erro ao responder publicamente comentário: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Exceção ao responder comentário {comment_id}: {e}", exc_info=True)
        return False
