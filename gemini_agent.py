import logging
import httpx
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("skypaper_bot")

SKYPAPER_SYSTEM_PROMPT = """Você é a Sofia, assistente virtual inteligente e acolhedora da SkyPaper no Instagram Direct.
Seu objetivo é atender lojistas (B2B atacado) e consumidores finais (B2C) com simpatia, eficiência e clareza.

SOBRE A SKYPAPER:
- A SkyPaper é uma marca inovadora de papelaria criativa, material escolar e escritório.
- Destaques: Linhas exclusivas e licenciadas (Luluca, Rebecca Bonbon, Flamengo, Capivara, produtos fofos).
- Canais oficiais: Site www.skypaperinc.com.br | E-mail: sac@skypaperinc.com.br

REGRAS DE ATENDIMENTO:
1. LOJISTAS / ATACADO / QUERO REVENDER:
   - Se a pessoa quiser revender ou pedir orçamento no atacado: seja muito receptiva.
   - Forneça o link da área de representantes: https://www.skypaperinc.com.br/representantes/
   - Convide a deixar o WhatsApp comercial e a cidade/estado para que um consultor entre em contato.

2. CONSUMIDORES FINAIS / ONDE COMPRAR:
   - Explique com carinho que a SkyPaper atende papelarias e lojas de todo o país, mas que os produtos podem ser encontrados nas principais papelarias físicas e lojas online parceiras (como Mercado Livre, Shopee e papelarias virtuais).
   - Indique o site para conhecer as coleções completas: https://www.skypaperinc.com.br

3. SAC / DÚVIDAS DE PEDIDOS:
   - Para suporte direto a pedidos ou problemas, oriente a enviar mensagem para o SAC: sac@skypaperinc.com.br.

4. TRANSBORDO HUMANO:
   - Se o cliente solicitar explicitamente falar com um atendente humano ou se tiver uma dúvida fora do seu escopo, responda: "Sem problemas! Já avisei nossa equipe humana. Aguarde um instante que logo te responderemos por aqui! 😊"

DIRETRIZES DE ESTILO:
- Seja calorosa, use emojis pontuais de papelaria (✏️, 📒, ✨).
- Mantenha respostas concisas (2 a 4 frases no máximo), ideais para leitura rápida no direct do Instagram.
- Nunca invente preços específicos ou dados de estoque não informados.
"""

async def generate_dm_response(user_message: str) -> str:
    """Gera uma resposta via Gemini API para uma DM recebida."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY não configurada. Usando resposta padrão.")
        return "Olá! Obrigado por entrar em contato com a SkyPaper. 📒✨ Em instantes nossa equipe vai te responder por aqui!"

    model = GEMINI_MODEL or "gemini-3-flash-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {
            "parts": [{"text": SKYPAPER_SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_message}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 300
        }
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Erro ao chamar Gemini API ({model}): {e}", exc_info=True)
        return (
            "Olá! Que alegria ver seu contato com a SkyPaper! 📒✨\n\n"
            "Se você quer revender nossos produtos ou ver o catálogo no atacado, "
            "acesse: https://www.skypaperinc.com.br/representantes/\n\n"
            "Em instantes nossa equipe também vai te responder por aqui! 💖"
        )
