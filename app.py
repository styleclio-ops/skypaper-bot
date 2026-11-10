import asyncio
import logging
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Query, Response, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse, HTMLResponse

from config import META_VERIFY_TOKEN, INSTAGRAM_ACCOUNT_ID
from gemini_agent import generate_dm_response, memory, understand_comment_context
from meta_client import (
    send_dm,
    send_button_menu,
    send_private_reply_to_comment,
    send_public_comment_reply
)
from analytics import (
    record_interaction,
    record_product_search,
    get_executive_summary,
    add_pending_site_notification
)
from campaigns import (
    analyze_text,
    get_sac_comment_reply,
    get_sac_dm_response,
    is_no_invoice_mention,
    get_no_invoice_reply
)
from contingency import (
    periodic_healthcheck_loop,
    get_contingency_response,
    check_all_sites,
    SITE_HEALTH
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("skypaper_bot")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa checagem dos sites e inicia loop de contingência em background
    logger.info("Iniciando serviços do SkyPaper AI Bot v3.0.0...")
    asyncio.create_task(check_all_sites())
    health_task = asyncio.create_task(periodic_healthcheck_loop(600))
    yield
    health_task.cancel()

app = FastAPI(title="SkyPaper Instagram AI Bot (Tsuru)", lifespan=lifespan)

# 12 Variações oficiais de respostas públicas aos comentários gerais
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

# Textos padrão do menu no Direct
COMMENT_MENU_TEXT = (
    "Olá! Vi que você comentou no nosso post da SkyPaper! 📒✨\n\n"
    "Para conseguir te atender melhor, me informe o que você é:"
)

DM_GREETING_MENU_TEXT = (
    "Olá! Sou o Tsuru, assistente virtual da SkyPaper! 🕊️✨\n\n"
    "Para conseguir te atender melhor, me informe o que você é:"
)

STORY_MENTION_REPLY = (
    "Que amor! Muito obrigado por marcar a SkyPaper nos seus Stories! 💖✨\n\n"
    "Amamos fazer parte da sua rotina, estudos e criatividade! "
    "Se precisar de algo ou quiser conferir os novos lançamentos, conte sempre com a gente! 🕊️📒"
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "SkyPaper Instagram AI Bot (Tsuru)",
        "version": "3.1.0",
        "features": [
            "Respostas automaticas a comentarios e DMs",
            "Menu interativo de botoes (Lojista, Representante, Consumidor)",
            "Inteligencia de Atendimento e SAC Prioritario",
            "Engajamento em Campanhas (Quero, Catalogo, Revender, Volta as Aulas)",
            "Reconhecimento de Story Mentions",
            "Plano de Contingencia e Healthcheck de Sites",
            "Painel de Metricas para a Diretoria (/relatorio)"
        ]
    }

@app.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """Endpoint de verificação exigido pela Meta ao cadastrar o Webhook."""
    logger.info(f"Recebendo verificação do webhook: mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso pela Meta!")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    
    logger.warning("Falha na verificação do token do webhook.")
    return Response(content="Token de verificação inválido", status_code=403)


async def process_instagram_event(payload: dict):
    """
    Processa eventos em background para responder ao Webhook da Meta em tempo recorde (< 2s).
    Trata comentários, story mentions, DMs, campanhas, SAC prioritário e contingência.
    """
    try:
        logger.info(f"Payload do Webhook recebido: {payload}")
        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])

            # =========================================================================
            # 1. TRATAMENTO DE COMENTÁRIOS EM TODOS OS POSTS E REELS
            # =========================================================================
            for change in changes:
                field = change.get("field")
                if field == "comments":
                    value = change.get("value", {})
                    comment_id = value.get("id")
                    comment_text = value.get("text", "").strip()
                    from_user = value.get("from", {})
                    user_id = from_user.get("id")

                    # Ignora comentários da própria conta SkyPaper
                    if user_id and INSTAGRAM_ACCOUNT_ID and str(user_id) == str(INSTAGRAM_ACCOUNT_ID):
                        continue

                    logger.info(f"Novo comentário recebido: '{comment_text}' (ID: {comment_id})")

                    # Análise de Produtos
                    analysis = analyze_text(comment_text)
                    for prod in analysis.get("products", []):
                        record_product_search(user_id, prod)

                    # 1. TENTA LEITURA CONTEXTUAL PROFUNDA VIA IA (GEMINI)
                    ai_context = await understand_comment_context(comment_text)

                    if ai_context:
                        intent = ai_context.get("intent", "geral")
                        is_sac = ai_context.get("is_sac", False)
                        public_reply = ai_context.get("public_reply")
                        dm_intro = ai_context.get("dm_intro")

                        if is_sac:
                            logger.warning(f"🚨 ALERTA SAC (detectado por IA no comentário {comment_id}): '{comment_text}'")
                            record_interaction(
                                user_id=user_id,
                                event_type="comment",
                                profile_type="sac",
                                sentiment="negative",
                                text_snippet=comment_text
                            )
                            await asyncio.gather(
                                send_public_comment_reply(comment_id, public_reply or get_sac_comment_reply()),
                                send_dm(user_id, dm_intro or get_sac_dm_response()),
                                return_exceptions=True
                            )
                            continue
                        else:
                            logger.info(f"✨ Contexto do comentário compreendido por IA (intent: {intent})")
                            record_interaction(
                                user_id=user_id,
                                event_type="comment",
                                profile_type=intent,
                                sentiment="positive" if intent == "elogio" else "neutral",
                                text_snippet=comment_text
                            )
                            await asyncio.gather(
                                send_public_comment_reply(comment_id, public_reply),
                                send_button_menu({"comment_id": comment_id}, text=dm_intro),
                                return_exceptions=True
                            )
                            continue

                    # 2. FALLBACK SE A IA NÃO RESPONDER EM TEMPO HÁBIL
                    if analysis["is_sac"]:
                        logger.warning(f"🚨 ALERTA SAC detectado no comentário {comment_id}: '{comment_text}'")
                        record_interaction(
                            user_id=user_id,
                            event_type="comment",
                            profile_type="sac",
                            sentiment="negative",
                            text_snippet=comment_text
                        )
                        public_reply = get_sac_comment_reply()
                        dm_reply = get_sac_dm_response()
                        await asyncio.gather(
                            send_public_comment_reply(comment_id, public_reply),
                            send_dm(user_id, dm_reply),
                            return_exceptions=True
                        )
                        continue

                    elif analysis["campaign_id"]:
                        camp_data = analysis["campaign_data"]
                        logger.info(f"🎯 Campanha detectada no comentário: '{analysis['campaign_id']}'")
                        record_interaction(
                            user_id=user_id,
                            event_type="comment",
                            profile_type="campanha",
                            sentiment="positive",
                            campaign_tag=analysis["campaign_id"],
                            text_snippet=comment_text
                        )
                        await asyncio.gather(
                            send_public_comment_reply(comment_id, camp_data["public_reply"]),
                            send_button_menu({"comment_id": comment_id}, text=camp_data["dm_text"]),
                            return_exceptions=True
                        )
                        continue

                    else:
                        record_interaction(
                            user_id=user_id,
                            event_type="comment",
                            profile_type="geral",
                            sentiment="neutral",
                            text_snippet=comment_text
                        )
                        public_reply = random.choice(PUBLIC_REPLY_TEMPLATES)
                        await asyncio.gather(
                            send_public_comment_reply(comment_id, public_reply),
                            send_button_menu({"comment_id": comment_id}, text=COMMENT_MENU_TEXT),
                            return_exceptions=True
                        )
                        continue

            # =========================================================================
            # 2. EXTRAÇÃO DE EVENTOS DE MENSAGENS, STORY MENTIONS E BOTÕES
            # =========================================================================
            messaging_events = list(entry.get("messaging", [])) + list(entry.get("standby", []))
            for change in changes:
                if change.get("field") in ["messages", "messaging_postbacks", "mentions"]:
                    val = change.get("value", {})
                    if isinstance(val, dict):
                        messaging_events.append(val)
                    elif isinstance(val, list):
                        messaging_events.extend(val)

            for messaging in messaging_events:
                sender_id = str(messaging.get("sender", {}).get("id"))
                is_echo = messaging.get("message", {}).get("is_echo", False)

                # Ignora mensagens enviadas pela própria conta
                if is_echo or (sender_id and INSTAGRAM_ACCOUNT_ID and sender_id == str(INSTAGRAM_ACCOUNT_ID)):
                    continue

                message_obj = messaging.get("message", {})

                # --- 2.1 TRATAMENTO DE STORY MENTIONS (MENÇÕES NOS STORIES) ---
                attachments = message_obj.get("attachments", [])
                is_story_mention = any(
                    att.get("type") in ["story_mention", "story_reply"] for att in attachments
                ) or messaging.get("story_mention") is not None

                if is_story_mention:
                    logger.info(f"📸 Story Mention recebido de {sender_id}!")
                    record_interaction(
                        user_id=sender_id,
                        event_type="story_mention",
                        profile_type="engajamento",
                        sentiment="positive",
                        text_snippet="Marcou @skypaper.inc nos Stories"
                    )
                    await send_dm(sender_id, STORY_MENTION_REPLY)
                    continue

                # --- 2.2 TRATAMENTO DE CLIQUES EM BOTÕES CLICÁVEIS (POSTBACK) ---
                postback = messaging.get("postback")
                if postback:
                    payload_data = postback.get("payload", "")
                    button_title = postback.get("title", "")
                    logger.info(f"Clique em botão recebido de {sender_id}: payload='{payload_data}', title='{button_title}'")

                    if payload_data == "PERFIL_CONSUMIDOR" or "consumidor" in button_title.lower():
                        record_interaction(sender_id, "button_click", profile_type="consumidor", text_snippet="Clicou Consumidor Final")
                        consumidor_reply = (
                            "Que maravilha! 💖 Conheça todo o nosso catálogo e produtos no site oficial da SkyPaper:\n"
                            "👉 https://skypaperinc.com.br/produtos/\n\n"
                            "Você também encontra nossos produtos nas melhores papelarias físicas do Brasil e em lojas parceiras online. "
                            "Se tiver qualquer dúvida ou procurar um item específico, é só me chamar aqui! 🌸📒"
                        )
                        memory.add_message(sender_id, "user", "Sou Consumidor Final")
                        memory.add_message(sender_id, "model", consumidor_reply)
                        await send_dm(sender_id, consumidor_reply)
                        continue

                    elif payload_data == "PERFIL_LOJISTA" or "lojista" in button_title.lower():
                        record_interaction(sender_id, "button_click", profile_type="lojista", text_snippet="Clicou Lojista")
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
                        record_interaction(sender_id, "button_click", profile_type="representante", text_snippet="Clicou Representante")
                        rep_reply = (
                            "Perfeito! Para representantes comerciais ou parceiros de vendas, acesse nossa área comercial:\n"
                            "👉 https://comprarskypaper.hidrahome.com.br/\n\n"
                            "Faça seu cadastro para que possamos alinhar a parceria e regiões de atendimento! 💼✨"
                        )
                        memory.add_message(sender_id, "user", "Sou Representante")
                        memory.add_message(sender_id, "model", rep_reply)
                        await send_dm(sender_id, rep_reply)
                        continue

                # --- 2.3 TRATAMENTO DE MENSAGENS DE TEXTO E QUICK REPLIES ---
                message_text = message_obj.get("text", "").strip()
                if not message_text:
                    continue

                logger.info(f"Nova DM recebida de {sender_id}: '{message_text}'")
                normalized_text = message_text.lower().strip()

                # Análise de inteligência da DM
                analysis = analyze_text(message_text)

                # Registra menções de produtos
                for prod in analysis.get("products", []):
                    record_product_search(sender_id, prod)

                # CENÁRIO 0: CLIENTE INFORMA QUE NÃO POSSUI NOTA FISCAL
                if is_no_invoice_mention(message_text):
                    logger.info(f"Cliente {sender_id} informou ausência de nota fiscal.")
                    record_interaction(sender_id, "dm", "sac", "neutral", text_snippet=message_text)
                    no_inv_reply = get_no_invoice_reply()
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", no_inv_reply)
                    await send_dm(sender_id, no_inv_reply)
                    continue

                # CENÁRIO 1: RELATO DE ERRO NO SITE (CONTINGÊNCIA - NOTIFICAÇÃO AGENDADA QUANDO O SITE VOLTAR)
                if analysis["is_contingency"]:
                    logger.warning(f"⚠️ Relato de contingência/erro de site por {sender_id}: '{message_text}'")
                    # Registra cliente na fila para ser notificado assim que o site voltar!
                    add_pending_site_notification(sender_id, "hidrahome_portal", "https://comprarskypaper.hidrahome.com.br/")
                    record_interaction(
                        user_id=sender_id,
                        event_type="dm",
                        profile_type="contingencia",
                        sentiment="negative",
                        text_snippet=message_text
                    )
                    contingency_msg = get_contingency_response("erro_site")
                    await send_dm(sender_id, contingency_msg)
                    continue

                # CENÁRIO 2: RECLAMAÇÃO OU SAC PRIORITÁRIO
                if analysis["is_sac"]:
                    logger.warning(f"🚨 SAC PRIORITÁRIO acionado por {sender_id}: '{message_text}'")
                    record_interaction(
                        user_id=sender_id,
                        event_type="dm",
                        profile_type="sac",
                        sentiment="negative",
                        text_snippet=message_text
                    )
                    sac_msg = get_sac_dm_response()
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", sac_msg)
                    await send_dm(sender_id, sac_msg)
                    continue

                # CENÁRIO 3: SELEÇÃO MANUAL DO MENU POR TEXTO
                if any(k in normalized_text for k in ["consumidor final", "sou consumidor", "sou consumidora", "consumidor", "cliente", "b2c"]) or normalized_text in ["3", "3️⃣"]:
                    record_interaction(sender_id, "dm", profile_type="consumidor", sentiment="neutral", text_snippet=message_text)
                    consumidor_reply = (
                        "Que maravilha! 💖 Conheça todo o nosso catálogo e produtos no site oficial da SkyPaper:\n"
                        "👉 https://skypaperinc.com.br/produtos/\n\n"
                        "Você também encontra nossos produtos nas melhores papelarias físicas do Brasil e em lojas parceiras online. "
                        "Se tiver qualquer dúvida ou procurar um item específico, é só me chamar aqui! 🌸📒"
                    )
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", consumidor_reply)
                    await send_dm(sender_id, consumidor_reply)
                    continue

                elif any(k in normalized_text for k in ["lojista", "sou lojista", "revender", "quero revender", "atacado", "comprar no atacado"]) or normalized_text in ["1", "1️⃣"]:
                    record_interaction(sender_id, "dm", profile_type="lojista", sentiment="neutral", text_snippet=message_text)
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
                    record_interaction(sender_id, "dm", profile_type="representante", sentiment="neutral", text_snippet=message_text)
                    rep_reply = (
                        "Perfeito! Para representantes comerciais ou parceiros de vendas, acesse nossa área comercial:\n"
                        "👉 https://comprarskypaper.hidrahome.com.br/\n\n"
                        "Faça seu cadastro para que possamos alinhar a parceria e regiões de atendimento! 💼✨"
                    )
                    memory.add_message(sender_id, "user", message_text)
                    memory.add_message(sender_id, "model", rep_reply)
                    await send_dm(sender_id, rep_reply)
                    continue

                # CENÁRIO 4: SOLICITAÇÃO EXPLÍCITA DE MENU OU SAUDAÇÃO INICIAL
                elif normalized_text in ["menu", "opções", "opcoes", "início", "inicio", "começar", "comecar", "ajuda"]:
                    record_interaction(sender_id, "dm", profile_type="geral", text_snippet=message_text)
                    await send_button_menu({"id": sender_id}, text=DM_GREETING_MENU_TEXT)
                    continue

                history = memory.get_history(sender_id)
                if not history and normalized_text in ["oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "oii", "oiee", "hey", "hello"]:
                    record_interaction(sender_id, "dm", profile_type="saudacao", text_snippet=message_text)
                    await send_button_menu({"id": sender_id}, text=DM_GREETING_MENU_TEXT)
                    continue

                # CENÁRIO 5: DÚVIDA ABERTA -> CÉREBRO DA IA (TSURU GEMINI)
                record_interaction(sender_id, "dm", profile_type="duvida_ia", text_snippet=message_text)
                ai_reply = await generate_dm_response(sender_id, message_text)
                await send_dm(sender_id, ai_reply)

    except Exception as e:
        logger.error(f"Erro ao processar evento do Instagram: {e}", exc_info=True)


@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Recebe os webhooks da Meta em tempo real e processa em background."""
    try:
        payload = await request.json()
        background_tasks.add_task(process_instagram_event, payload)
        return JSONResponse(content={"status": "EVENT_RECEIVED"}, status_code=200)
    except Exception as e:
        logger.error(f"Erro ao receber payload: {e}")
        return JSONResponse(content={"status": "ERROR"}, status_code=400)


# =========================================================================
# 3. ENDPOINTS EXECUTIVOS & RELATÓRIOS PARA A DIRETORIA
# =========================================================================

@app.get("/api/relatorio")
async def api_relatorio():
    """Retorna dados executivos estruturados em JSON para integrações ou CRM."""
    summary = get_executive_summary()
    summary["sites_health"] = SITE_HEALTH
    return JSONResponse(content=summary, status_code=200)

@app.get("/api/health")
async def api_health():
    """Healthcheck completo dos serviços e portais."""
    return JSONResponse(content={
        "bot_status": "online",
        "version": "3.1.0",
        "monitored_sites": SITE_HEALTH,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.get("/relatorio", response_class=HTMLResponse)
async def dashboard_relatorio():
    """Painel Executivo Web da SkyPaper para a Diretoria."""
    data = get_executive_summary()
    health = SITE_HEALTH

    total = data.get("total_interactions", 0)
    today = data.get("today_interactions", 0)
    by_profile = data.get("by_profile", {})
    by_event = data.get("by_event", {})
    top_products = data.get("top_products", [])
    top_campaigns = data.get("top_campaigns", [])
    recent = data.get("recent_interactions", [])

    lojistas = by_profile.get("lojista", 0)
    representantes = by_profile.get("representante", 0)
    consumidores = by_profile.get("consumidor", 0)
    sac = by_profile.get("sac", 0)

    # Health status badges
    sky_up = health.get("skypaper_site", {}).get("is_up", True)
    sky_lat = health.get("skypaper_site", {}).get("latency_ms", 0)
    hidra_up = health.get("hidrahome_portal", {}).get("is_up", True)
    hidra_lat = health.get("hidrahome_portal", {}).get("latency_ms", 0)

    # HTML Dashboard
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SkyPaper Intelligence | Painel da Diretoria</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <meta http-equiv="refresh" content="30">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', sans-serif;
      background: #0f172a;
      color: #f8fafc;
      padding: 24px;
      min-height: 100vh;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    
    /* Header */
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      padding-bottom: 24px;
      border-bottom: 1px solid #1e293b;
      margin-bottom: 24px;
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .brand-title {{ font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; }}
    .brand-title span {{ color: #00acb9; }}
    .brand-sub {{ font-size: 13px; color: #94a3b8; }}

    .health-bar {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
    .badge {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge-online {{ background: rgba(34, 197, 94, 0.15); color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3); }}
    .badge-warn {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); }}
    .dot {{ width: 8px; height: 8px; border-radius: 50%; background: currentColor; }}

    /* KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: #1e293b;
      padding: 20px;
      border-radius: 14px;
      border: 1px solid #334155;
    }}
    .kpi-label {{ font-size: 12px; font-weight: 500; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-value {{ font-size: 32px; font-weight: 800; color: #ffffff; margin: 8px 0 4px; }}
    .kpi-desc {{ font-size: 12px; color: #00acb9; }}
    .kpi-alert .kpi-value {{ color: #f87171; }}

    /* Main Content Grid */
    .grid-2 {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }}
    .card {{
      background: #1e293b;
      border-radius: 14px;
      padding: 24px;
      border: 1px solid #334155;
    }}
    .card-title {{ font-size: 16px; font-weight: 700; color: #ffffff; margin-bottom: 18px; display: flex; justify-content: space-between; }}

    /* Progress Rows */
    .bar-row {{ margin-bottom: 14px; }}
    .bar-header {{ display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 6px; }}
    .bar-label {{ font-weight: 600; color: #e2e8f0; }}
    .bar-track {{ height: 8px; background: #334155; border-radius: 6px; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 6px; background: #00acb9; }}
    .bar-fill-orange {{ background: #f59e0b; }}
    .bar-fill-purple {{ background: #a855f7; }}
    .bar-fill-red {{ background: #ef4444; }}

    /* Table */
    .table-container {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
    th {{ color: #94a3b8; font-weight: 600; padding: 10px 12px; border-bottom: 1px solid #334155; }}
    td {{ padding: 12px; border-bottom: 1px solid #273549; color: #cbd5e1; }}
    .tag {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
    }}
    .tag-lojista {{ background: rgba(0, 172, 185, 0.2); color: #00acb9; }}
    .tag-rep {{ background: rgba(168, 85, 247, 0.2); color: #c084fc; }}
    .tag-sac {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .tag-consumidor {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}

    .footer {{ text-align: center; color: #64748b; font-size: 12px; margin-top: 32px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">
        <div>
          <div class="brand-title">SkyPaper <span>Intelligence</span></div>
          <div class="brand-sub">Painel Executivo de Vendas & Atendimento (Tsuru Bot v3.0.0)</div>
        </div>
      </div>
      <div class="health-bar">
        <div class="badge {'badge-online' if sky_up else 'badge-warn'}">
          <div class="dot"></div> Site Oficial: {'ONLINE (' + str(sky_lat) + 'ms)' if sky_up else 'INSTÁVEL'}
        </div>
        <div class="badge {'badge-online' if hidra_up else 'badge-warn'}">
          <div class="dot"></div> Portal Lojista: {'ONLINE (' + str(hidra_lat) + 'ms)' if hidra_up else 'CONTINGÊNCIA'}
        </div>
      </div>
    </div>

    <!-- KPIs -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Atendimentos</div>
        <div class="kpi-value">{total}</div>
        <div class="kpi-desc">+{today} hoje</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Lojistas / Atacado</div>
        <div class="kpi-value">{lojistas}</div>
        <div class="kpi-desc">Portal Hidra Home</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Representantes</div>
        <div class="kpi-value">{representantes}</div>
        <div class="kpi-desc">Parcerias Comerciais</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Consumidor Final</div>
        <div class="kpi-value">{consumidores}</div>
        <div class="kpi-desc">Catálogo de Produtos</div>
      </div>
      <div class="kpi-card {'kpi-alert' if sac > 0 else ''}">
        <div class="kpi-label">Ocorrências SAC</div>
        <div class="kpi-value">{sac}</div>
        <div class="kpi-desc">{'Requer atenção' if sac > 0 else 'Nenhuma pendência'}</div>
      </div>
    </div>

    <div class="grid-2">
      <!-- Distribuição de Público -->
      <div class="card">
        <div class="card-title">Distribuição por Perfil de Contato</div>
        <div class="bar-row">
          <div class="bar-header">
            <span class="bar-label">Lojistas (B2B Atacado)</span>
            <span>{lojistas}</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width: {min(100, int((lojistas/max(1, total))*100))}%;"></div></div>
        </div>
        <div class="bar-row">
          <div class="bar-header">
            <span class="bar-label">Consumidores Finais (B2C)</span>
            <span>{consumidores}</span>
          </div>
          <div class="bar-track"><div class="bar-fill bar-fill-purple" style="width: {min(100, int((consumidores/max(1, total))*100))}%;"></div></div>
        </div>
        <div class="bar-row">
          <div class="bar-header">
            <span class="bar-label">Representantes Comerciais</span>
            <span>{representantes}</span>
          </div>
          <div class="bar-track"><div class="bar-fill bar-fill-orange" style="width: {min(100, int((representantes/max(1, total))*100))}%;"></div></div>
        </div>
        <div class="bar-row">
          <div class="bar-header">
            <span class="bar-label">Suporte / SAC Prioritário</span>
            <span>{sac}</span>
          </div>
          <div class="bar-track"><div class="bar-fill bar-fill-red" style="width: {min(100, int((sac/max(1, total))*100))}%;"></div></div>
        </div>
      </div>

      <!-- Top Produtos Buscados -->
      <div class="card">
        <div class="card-title">Linhas Mais Procuradas</div>
        {"".join([f'''
        <div class="bar-row">
          <div class="bar-header">
            <span class="bar-label">{p.get('product')}</span>
            <span>{p.get('count')} menções</span>
          </div>
          <div class="bar-track"><div class="bar-fill" style="width: {min(100, int(p.get('count', 1)*15))}%;"></div></div>
        </div>
        ''' for p in top_products]) if top_products else '<p style="color: #64748b; font-size: 13px;">Aguardando novas buscas de clientes para consolidar o ranking.</p>'}
      </div>
    </div>

    <!-- Tabela Recente -->
    <div class="card">
      <div class="card-title">Últimas Interações no Instagram</div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Data/Hora</th>
              <th>Canal</th>
              <th>Perfil</th>
              <th>Sentimento</th>
              <th>Conteúdo</th>
            </tr>
          </thead>
          <tbody>
            {"".join([f'''
            <tr>
              <td>{r.get('timestamp', '')[:19]}</td>
              <td>{r.get('event_type')}</td>
              <td><span class="tag tag-{r.get('profile_type')}">{r.get('profile_type')}</span></td>
              <td>{r.get('sentiment')}</td>
              <td>{r.get('text_snippet', '')}</td>
            </tr>
            ''' for r in recent]) if recent else '<tr><td colspan="5" style="text-align: center; color: #64748b;">Nenhuma interação recente registrada ainda.</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">
      SkyPaper Inc. &bull; Sistema Oficial de Inteligência e Automação &bull; Atualiza a cada 30 segundos
    </div>
  </div>
</body>
</html>
"""
    return HTMLResponse(content=html, status_code=200)
