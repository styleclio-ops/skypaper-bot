import asyncio
import logging
import random
from fastapi import FastAPI, Request, Query, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse

from config import META_VERIFY_TOKEN, INSTAGRAM_ACCOUNT_ID
from gemini_agent import generate_dm_response, memory
from meta_client import (
    send_dm,
    send_button_menu,
    send_private_reply_to_comment,
    send_public_comment_reply
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("skypaper_bot")

app = FastAPI(title="SkyPaper Instagram AI Bot (Tsuru)")

# 12 Variações oficiais de respostas públicas aos comentários
PUBLIC_REPLY_TEMPLATES = [
    "Te chamei no direct para te passar todos os detalhes! Dá uma olhadinha lá 📩✨",
    "Prontinho! Acabei de te enviar uma mensagem no direct 📒💖",
    "Informações enviadas por direct! Confere lá na sua DM! 🥰",
    "Já te respondi no direct! Qualquer dúvida nos chame por lá 📝✨",
    "Opa, acabei de te mandar uma DM! Dá uma conferida 🚀",
    "Que legal seu comentário! Te enviei um direct agora mesmo 💛",
    "Dá uma olhadinha no seu direct, já mandei tudo certinho por lá! 📬✨",
    "Acabei de te responder por DM! Confere lá no seu direct 💌",
    "Mensagem enviada com sucesso no seu direct! Corre lá pra ver 📒✨",
    "Prontinho, te chamei no direct com todas as informações! Dá uma olhada 💬💖",
    "Te respondi por DM Qualquer coisa estamos à disposição por lá 🌸📝",
    "Acabei de te mandar uma DM com tudo o que você precisa! Confere lá ✨"
]

# Texto de abertura do menu enviado ao usuário no Direct
COMMENT_MENU_TEXT = (
    "Olá! Vi que você comentou no nosso post da SkyPaper! 📒✨\n\n"
    "Para conseguir te atender melhor, me informe o que você é:"
)

DM_GREETING_MENU_TEXT = (
    "Olá! Sou o Tsuru, assistente virtual da SkyPaper! 🕊️✨\n\n"
    "Para conseguir te atender melhor, me informe o que você é:"
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SkyPaper Instagram AI Bot (Tsuru)",
        "version": "2.2.0"
    }

@app.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Endpoint de verificação exigido pela Meta ao cadastrar a URL de retorno.
    """
    logger.info(f"Recebendo verificação do webhook: mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso pela Meta!")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    
    logger.warning("Falha na verificação do token do webhook.")
    return Response(content="Token de verificação inválido", status_code=403)


async def process_instagram_event(payload: dict):
    """
    Processa eventos em background para responder ao Webhook da Meta em tempo recorde (< 2s).
    Trata comentários em posts/reels, cliques em botões interativos e mensagens diretas.
    """
    try:
        logger.info(f"Payload do Webhook recebido: {payload}")
        entries = payload.get("entry", [])
        for entry in entries:
            # 1. TRATAMENTO DE COMENTÁRIOS EM TODOS OS POSTS E REELS
            changes = entry.get("changes", [])
            for change in changes:
                field = change.get("field")
                if field == "comments":
                    value = change.get("value", {})
                    comment_id = value.get("id")
                    comment_text = value.get("text", "").strip()
                    from_user = value.get("from", {})
                    user_id = from_user.get("id")

                    # Ignora comentários da própria conta
                    if user_id and INSTAGRAM_ACCOUNT_ID and str(user_id) == str(INSTAGRAM_ACCOUNT_ID):
                        continue

                    logger.info(f"Novo comentário recebido em post/reel: '{comment_text}' (ID: {comment_id})")
                    public_reply = random.choice(PUBLIC_REPLY_TEMPLATES)

                    # Envia o menu com botões clicáveis no Direct e a resposta pública no post em paralelo
                    await asyncio.gather(
                        send_button_menu({"comment_id": comment_id}, text=COMMENT_MENU_TEXT),
                        send_public_comment_reply(comment_id, public_reply),
                        return_exceptions=True
                    )

            # 2. EXTRAÇÃO DE EVENTOS DE MENSAGENS E BOTÕES (messaging, standby e changes)
            messaging_events = list(entry.get("messaging", [])) + list(entry.get("standby", []))
            for change in changes:
                if change.get("field") in ["messages", "messaging_postbacks"]:
                    val = change.get("value", {})
                    if isinstance(val, dict):
                        messaging_events.append(val)
                    elif isinstance(val, list):
                        messaging_events.extend(val)

            for messaging in messaging_events:
                sender_id = str(messaging.get("sender", {}).get("id"))
                is_echo = messaging.get("message", {}).get("is_echo", False)

                # Ignora mensagens enviadas por nós mesmos ou eventos de eco
                if is_echo or (sender_id and INSTAGRAM_ACCOUNT_ID and sender_id == str(INSTAGRAM_ACCOUNT_ID)):
                    continue

                # --- 2.1 TRATAMENTO DE CLIQUES EM BOTÕES CLICÁVEIS (POSTBACK) ---
                postback = messaging.get("postback")
                if postback:
                    payload_data = postback.get("payload", "")
                    button_title = postback.get("title", "")
                    logger.info(f"Clique em botão recebido de {sender_id}: payload='{payload_data}', title='{button_title}'")

                    if payload_data == "PERFIL_CONSUMIDOR" or "consumidor" in button_title.lower():
                        consumidor_reply = (
                            "Que maravilha! 💖 A SkyPaper atende papelarias e lojas de todo o país, "
                            "mas você também encontra nossos produtos nas principais papelarias físicas e lojas parceiras online (como Mercado Livre e Shopee).\n\n"
                            "Qual produto ou linha você está procurando no momento? "
                            "(Ex: Rebecca Bonbon, Luluca, Linha Capivara, Linha Fofa, One Piece, Cadernos, etc.) "
                            "Me conta aqui que te envio o link certinho do nosso site! 🌸📒"
                        )
                        memory.add_message(sender_id, "user", "Sou Consumidor Final")
                        memory.add_message(sender_id, "model", consumidor_reply)
                        await send_dm(sender_id, consumidor_reply)
                        continue

                    elif payload_data == "PERFIL_LOJISTA" or "lojista" in button_title.lower():
                        lojista_reply = (
                            "Excelente! Se você é lojista ou quer revender os produtos da SkyPaper no atacado, "
                            "acesse nosso portal exclusivo:\n"
                            "👉 https://comprarskypaper.hidrahome.com.br/\n\n"
                            "Cadastre-se na página para que a nossa equipe comercial entre em contato e passe todas as condições de compras! 📒✨"
                        )
                        memory.add_message(sender_id, "user", "Sou Lojista")
                        memory.add_message(sender_id, "model", lojista_reply)
                        await send_dm(sender_id, lojista_reply)
                        continue

                    elif payload_data == "PERFIL_REPRESENTANTE" or "representante" in button_title.lower():
                        rep_reply = (
                            "Perfeito! Para representantes comerciais ou parceiros de vendas, acesse nossa área comercial:\n"
                            "👉 https://comprarskypaper.hidrahome.com.br/\n\n"
                            "Faça seu cadastro para que possamos alinhar a parceria e regiões de atendimento! 💼✨"
                        )
                        memory.add_message(sender_id, "user", "Sou Representante")
                        memory.add_message(sender_id, "model", rep_reply)
                        await send_dm(sender_id, rep_reply)
                        continue

                # --- 2.2 TRATAMENTO DE MENSAGENS DE TEXTO E QUICK REPLIES ---
                message = messaging.get("message", {})
                quick_reply = message.get("quick_reply", {})
                qr_payload = quick_reply.get("payload", "")

                if qr_payload == "PERFIL_CONSUMIDOR":
                    consumidor_reply = (
                        "Que maravilha! 💖 A SkyPaper atende papelarias e lojas de todo o país, "
                        "mas você também encontra nossos produtos nas principais papelarias físicas e lojas parceiras online (como Mercado Livre e Shopee).\n\n"
                        "Qual produto ou linha você está procurando no momento? "
                        "(Ex: Rebecca Bonbon, Luluca, Linha Capivara, Linha Fofa, One Piece, Cadernos, etc.) "
                        "Me conta aqui que te envio o link certinho do nosso site! 🌸📒"
                    )
                    memory.add_message(sender_id, "user", "Sou Consumidor Final")
                    memory.add_message(sender_id, "model", consumidor_reply)
                    await send_dm(sender_id, consumidor_reply)
                    continue

                message_text = message.get("text", "").strip()
                if not message_text:
                    continue

                logger.info(f"Nova DM de texto recebida de {sender_id}: '{message_text}'")
                normalized_text = message_text.lower().strip()

                # Se o usuário digitou uma das opções do menu por texto
                if any(k in normalized_text for k in ["consumidor final", "sou consumidor", "sou consumidora", "consumidor", "cliente", "b2c"]) or normalized_text in ["3", "3️⃣"]:
                    consumidor_reply = (
                        "Que maravilha! 💖 A SkyPaper atende papelarias e lojas de todo o país, "
                        "mas você também encontra nossos produtos nas principais papelarias físicas e lojas parceiras online (como Mercado Livre e Shopee).\n\n"
                        "Qual produto ou linha você está procurando no momento? "
                        "(Ex: Rebecca Bonbon, Luluca, Linha Capivara, Linha Fofa, One Piece, Cadernos, etc.) "
                        "Me conta aqui que te envio o link certinho do nosso site! 🌸📒"
                    )
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", consumidor_reply)
                    await send_dm(sender_id, consumidor_reply)
                    continue

                elif any(k in normalized_text for k in ["lojista", "sou lojista", "revender", "quero revender", "atacado", "comprar no atacado"]) or normalized_text in ["1", "1️⃣"]:
                    lojista_reply = (
                        "Excelente! Se você é lojista ou quer revender os produtos da SkyPaper no atacado, "
                        "acesse nosso portal exclusivo:\n"
                        "👉 https://comprarskypaper.hidrahome.com.br/\n\n"
                        "Cadastre-se na página para que a nossa equipe comercial entre em contato e passe todas as condições de compras! 📒✨"
                    )
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", lojista_reply)
                    await send_dm(sender_id, lojista_reply)
                    continue

                elif any(k in normalized_text for k in ["representante", "sou representante", "representação", "representacao"]) or normalized_text in ["2", "2️⃣"]:
                    rep_reply = (
                        "Perfeito! Para representantes comerciais ou parceiros de vendas, acesse nossa área comercial:\n"
                        "👉 https://comprarskypaper.hidrahome.com.br/\n\n"
                        "Faça seu cadastro para que possamos alinhar a parceria e regiões de atendimento! 💼✨"
                    )
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", rep_reply)
                    await send_dm(sender_id, rep_reply)
                    continue

                elif normalized_text in ["menu", "opções", "opcoes", "início", "inicio", "começar", "comecar", "ajuda"]:
                    await send_button_menu({"id": sender_id}, text=DM_GREETING_MENU_TEXT)
                    continue

                # Se for saudação inicial sem histórico de conversa anterior, apresenta o menu de botões clicáveis
                history = memory.get_history(sender_id)
                if not history and normalized_text in ["oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "oii", "oiee", "hey", "hello"]:
                    await send_button_menu({"id": sender_id}, text=DM_GREETING_MENU_TEXT)
                    continue

                # Chama o cérebro da IA (Tsuru) com memória de conversa e catálogo completo do site
                ai_reply = await generate_dm_response(sender_id, message_text)
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
        background_tasks.add_task(process_instagram_event, payload)
        return JSONResponse(content={"status": "EVENT_RECEIVED"}, status_code=200)
    except Exception as e:
        logger.error(f"Erro ao receber payload: {e}")
        return JSONResponse(content={"status": "ERROR"}, status_code=400)
