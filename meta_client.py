import logging
import httpx
from config import META_GRAPH_URL, META_PAGE_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID

logger = logging.getLogger("skypaper_bot")

async def send_dm(recipient_id: str, text: str) -> bool:
    """Envia uma mensagem direta (DM) de texto para um usuário no Instagram."""
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

async def send_button_menu(recipient: dict, text: str = None) -> bool:
    """
    Envia o menu de botões clicáveis no Instagram Direct (Button Template / Generic Template).
    Compatível tanto com {"id": recipient_id} quanto com {"comment_id": comment_id}.
    
    Botões configurados:
    1. Lojista -> https://comprarskypaper.hidrahome.com.br/
    2. Representante -> https://comprarskypaper.hidrahome.com.br/
    3. Consumidor Final -> https://skypaperinc.com.br/produtos/
    """
    if not META_PAGE_ACCESS_TOKEN:
        logger.error("META_PAGE_ACCESS_TOKEN não configurado!")
        return False

    url = f"{META_GRAPH_URL}/{INSTAGRAM_ACCOUNT_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    menu_text = text or (
        "Olá! Vi que você comentou no nosso post da SkyPaper! 📒✨\n\n"
        "Para conseguir te atender melhor, me informe o que você é:"
    )

    # Tentativa 1: Button Template (menu nativo de botões verticais idêntico ao modelo solicitado)
    button_payload = {
        "recipient": recipient,
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": menu_text,
                    "buttons": [
                        {
                            "type": "web_url",
                            "url": "https://comprarskypaper.hidrahome.com.br/",
                            "title": "Lojista"
                        },
                        {
                            "type": "web_url",
                            "url": "https://comprarskypaper.hidrahome.com.br/",
                            "title": "Representante"
                        },
                        {
                            "type": "web_url",
                            "url": "https://skypaperinc.com.br/produtos/",
                            "title": "Consumidor Final"
                        }
                    ]
                }
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=button_payload, headers=headers)
            if resp.status_code == 200:
                logger.info(f"Menu de botões clicáveis enviado com sucesso (Button Template) para {recipient}")
                return True
            else:
                logger.warning(f"Button Template falhou ({resp.status_code}): {resp.text}. Tentando Generic Template...")

            # Tentativa 2: Generic Template (alternativa padrão suportada pela Meta)
            generic_payload = {
                "recipient": recipient,
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": [
                                {
                                    "title": "SkyPaper | Atendimento 📒✨",
                                    "subtitle": menu_text[:80],
                                    "buttons": [
                                        {
                                            "type": "web_url",
                                            "url": "https://comprarskypaper.hidrahome.com.br/",
                                            "title": "Lojista"
                                        },
                                        {
                                            "type": "web_url",
                                            "url": "https://comprarskypaper.hidrahome.com.br/",
                                            "title": "Representante"
                                        },
                                        {
                                            "type": "web_url",
                                            "url": "https://skypaperinc.com.br/produtos/",
                                            "title": "Consumidor Final"
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
            resp_gen = await client.post(url, json=generic_payload, headers=headers)
            if resp_gen.status_code == 200:
                logger.info(f"Menu de botões clicáveis enviado com sucesso (Generic Template) para {recipient}")
                return True
            else:
                logger.warning(f"Generic Template falhou ({resp_gen.status_code}): {resp_gen.text}. Enviando fallback em texto...")

            # Tentativa 3: Fallback em texto seguro caso o cliente do usuário não suporte templates
            fallback_text = (
                f"{menu_text}\n\n"
                "👉 Lojista: https://comprarskypaper.hidrahome.com.br/\n"
                "👉 Representante: https://comprarskypaper.hidrahome.com.br/\n"
                "👉 Consumidor Final: https://skypaperinc.com.br/produtos/"
            )
            resp_txt = await client.post(url, json={"recipient": recipient, "message": {"text": fallback_text}}, headers=headers)
            return resp_txt.status_code == 200

    except Exception as e:
        logger.error(f"Exceção ao enviar menu de botões para {recipient}: {e}", exc_info=True)
        return False

async def send_private_reply_to_comment(comment_id: str, text: str) -> bool:
    """Envia uma DM privada padrão para o autor de um comentário em QUALQUER post ou Reel."""
    return await send_button_menu({"comment_id": comment_id}, text=text)

async def send_public_comment_reply(comment_id: str, text: str) -> bool:
    """
    Responde publicamente ao comentário no post ou Reel.
    A Meta exige form-data (data=...) ou query param em vez de JSON para evitar o erro 20 (OAuthException).
    """
    if not META_PAGE_ACCESS_TOKEN:
        logger.error("META_PAGE_ACCESS_TOKEN não configurado!")
        return False

    url = f"{META_GRAPH_URL}/{comment_id}/replies"
    headers = {
        "Authorization": f"Bearer {META_PAGE_ACCESS_TOKEN}"
    }
    data = {"message": text}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, data=data, headers=headers)
            if resp.status_code == 200:
                logger.info(f"Resposta pública enviada com sucesso para comentário {comment_id}")
                return True
            else:
                logger.error(f"Erro ao responder publicamente comentário: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Exceção ao responder comentário {comment_id}: {e}", exc_info=True)
        return False
