import logging
import random
from fastapi import FastAPI, Request, Query, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse

from config import META_VERIFY_TOKEN, INSTAGRAM_ACCOUNT_ID
from gemini_agent import generate_dm_response
from meta_client import (
    send_dm,
    send_private_reply_to_comment,
    send_public_comment_reply
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("skypaper_bot")

app = FastAPI(title="SkyPaper Instagram AI Bot")

# Variações de resposta pública nos comentários para evitar bloqueio anti-spam da Meta
PUBLIC_REPLY_TEMPLATES = [
    "Te mandei uma mensagem no direct com todas as informações! Dá uma olhadinha 📩✨",
    "Prontinho! Acabei de te enviar no direct 📒💖",
    "Informações enviadas por mensagem privada! Confere lá seu direct 🥰",
    "Já te respondi no direct! Qualquer dúvida nos chame por lá 📝✨"
]

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SkyPaper Instagram AI Bot",
        "version": "1.0.0"
    }

@app.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Endpoint de verificação exigido pela Meta ao cadastrar a URL de retorno (Callback URL).
    """
    logger.info(f"Recebendo verificação do webhook: mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso pela Meta!")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    
    logger.warning("Falha na verificação do token do webhook.")
    return Response(content="Token de verificação inválido", status_code=403)


async def process_instagram_event(payload: dict):
    """
    Processa eventos em background para responder ao Webhook da Meta em menos de 3 segundos (requisito da API).
    """
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            # 1. TRATAMENTO DE COMENTÁRIOS EM TODOS OS POSTS E REELS
            changes = entry.get("changes", [])
            for change in changes:
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    comment_id = value.get("id")
                    comment_text = value.get("text", "").strip()
                    from_user = value.get("from", {})
                    user_id = from_user.get("id")

                    # Ignora comentários da própria conta
                    if user_id and INSTAGRAM_ACCOUNT_ID and user_id == INSTAGRAM_ACCOUNT_ID:
                        continue

                    logger.info(f"Novo comentário recebido em post/reel: '{comment_text}' (ID: {comment_id})")

                    # Mensagem privada que será enviada no Direct de quem comentou
                    dm_text = (
                        "Olá! Vi que você comentou no nosso post da SkyPaper! 📒✨\n\n"
                        "Se você é lojista e deseja revender ou ver o catálogo no atacado, "
                        "acesse nossa área de representantes: https://www.skypaperinc.com.br/representantes/\n\n"
                        "Para conhecer toda nossa linha ou tirar dúvidas, pode me responder por aqui! 💖"
                    )

                    # 1.1 Envia a DM privada para o autor do comentário
                    await send_private_reply_to_comment(comment_id, dm_text)

                    # 1.2 Envia uma resposta pública no comentário (alternando frases)
                    public_reply = random.choice(PUBLIC_REPLY_TEMPLATES)
                    await send_public_comment_reply(comment_id, public_reply)

            # 2. TRATAMENTO DE DIRECT MESSAGES (DMs) COM O AGENTE DE IA
            messaging_events = entry.get("messaging", [])
            for messaging in messaging_events:
                sender_id = messaging.get("sender", {}).get("id")
                message = messaging.get("message", {})
                message_text = message.get("text", "")
                is_echo = message.get("is_echo", False)

                # Ignora mensagens enviadas por nós mesmos ou eventos de eco
                if is_echo or (sender_id and INSTAGRAM_ACCOUNT_ID and sender_id == INSTAGRAM_ACCOUNT_ID):
                    continue

                if message_text:
                    logger.info(f"Nova DM recebida de {sender_id}: '{message_text}'")
                    # Chama o cérebro da IA (Gemini) com o contexto da Skypaper
                    ai_reply = await generate_dm_response(message_text)
                    # Envia a resposta de volta no Direct do Instagram
                    await send_dm(sender_id, ai_reply)

    except Exception as e:
        logger.error(f"Erro ao processar evento do Instagram: {e}", exc_info=True)


@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint que recebe os eventos em tempo real do Instagram (comentários e DMs).
    """
    try:
        payload = await request.json()
        logger.debug(f"Payload recebido da Meta: {payload}")
        # Processa em background para liberar o webhook da Meta imediatamente com HTTP 200
        background_tasks.add_task(process_instagram_event, payload)
        return JSONResponse(content={"status": "EVENT_RECEIVED"}, status_code=200)
    except Exception as e:
        logger.error(f"Erro ao receber payload: {e}")
        return JSONResponse(content={"status": "ERROR"}, status_code=400)
