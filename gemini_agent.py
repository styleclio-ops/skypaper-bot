import logging
import time
from typing import Dict, List
import httpx
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("skypaper_bot")

# Catálogo completo e estruturado extraído diretamente de https://skypaperinc.com.br/
SKYPAPER_CATALOG_KNOWLEDGE = """
CATÁLOGO OFICIAL DE MARCAS, LINHAS E PRODUTOS (https://skypaperinc.com.br/):

1. LINHAS LICENCIADAS E MARCAS OFICIAIS:
- Rebecca Bonbon (Lápis com pompom, lápis grafite, cola bastão, cadernetas, borrachas e apontadores):
  Link direto: https://skypaperinc.com.br/marca/rebecca-bonbon/
- Luluca (Canetas gel, lápis, cadernos, tesouras, apontadores duplos):
  Link direto: https://skypaperinc.com.br/marca/luluca/
- One Piece (Blocos de desenho, apontador duplo, kits presenteáveis, borrachas oficiais):
  Link direto: https://skypaperinc.com.br/marca/one-piece/
- Naruto (Linha escolar oficial Naruto Shippuden):
  Link direto: https://skypaperinc.com.br/marca/naruto/
- Moranguinho (Blocos adesivos, lápis grafite, borrachas temáticas):
  Link direto: https://skypaperinc.com.br/marca/moranguinho/
- Flamengo (Material escolar oficial do Mengão - lápis, borrachas, apontadores):
  Link direto: https://skypaperinc.com.br/marca/flamengo/
- Emilly Vick (Linha exclusiva escolar):
  Link direto: https://skypaperinc.com.br/marca/emilly-vick/
- Dos Rosa (Linha oficial de apontadores, borrachas e lápis grafite):
  Link direto: https://skypaperinc.com.br/marca/dos-rosa/

2. LINHAS TEMÁTICAS EXCLUSIVAS DA SKYPAPER:
- Linha Capivara (Cadernos, blocos adesivos, canetas, lápis grafite, borrachas e apontadores de capivara):
  Link direto: https://skypaperinc.com.br/categoria/linha-capivara/
- Linha Fofa (Borrachas em formato fofo, apontadores criativos, marca-textos fofos e tesouras):
  Link direto: https://skypaperinc.com.br/categoria/linha-fofa/
- Linha Coordenadas (Kits coordenados, canetas gel, blocos adesivos, fitas decorativas):
  Link direto: https://skypaperinc.com.br/categoria/linha-coordenadas/
- Linha Office (Tesouras, grampeadores, estiletes, réguas e produtos para escritório):
  Link direto: https://skypaperinc.com.br/marca/linha-office/

3. DEPARTAMENTOS E CATEGORIAS DE PRODUTOS:
- Cadernos, Planners e Blocos Adesivos:
  Link direto: https://skypaperinc.com.br/categoria/cadernos-planers-e-blocos/
- Material Escolar Geral:
  Link direto: https://skypaperinc.com.br/departamento/material-escolar/
- Escrita (Canetas gel, esferográficas, fine line, canetinhas):
  Link direto: https://skypaperinc.com.br/categoria/escolar/caneta/
- Lápis Grafite e Lápis de Cor:
  Link direto: https://skypaperinc.com.br/categoria/escolar/lapis-grafite/
- Borrachas e Apontadores:
  Link direto: https://skypaperinc.com.br/categoria/escolar/borracha/
- Marca-texto e Marcadores:
  Link direto: https://skypaperinc.com.br/categoria/escolar/marca-texto/
- Escritório:
  Link direto: https://skypaperinc.com.br/departamento/escritorio/
- Artesanato (E.V.A., colas, tesouras):
  Link direto: https://skypaperinc.com.br/departamento/artesanato/
"""

SKYPAPER_SYSTEM_PROMPT = f"""Você é o Tsuru, assistente virtual inteligente e acolhedor da SkyPaper no Instagram Direct.
Seu objetivo é atender lojistas (B2B atacado), representantes e consumidores finais (B2C) com simpatia, eficiência e clareza.

SOBRE A SKYPAPER:
- A SkyPaper é uma marca inovadora de papelaria criativa, material escolar e escritório.
- Destaques: Linhas exclusivas e licenciadas (Luluca, Rebecca Bonbon, Flamengo, One Piece, Naruto, Capivara, Moranguinho, Linha Fofa e muito mais).
- Canais oficiais: Site www.skypaperinc.com.br | E-mail: sac@skypaperinc.com.br

REGRAS DE ATENDIMENTO:
1. LOJISTAS / ATACADO / REPRESENTANTES / QUERO REVENDER:
   - Se a pessoa for lojista, revendedor ou representante comercial: seja muito receptivo.
   - Forneça o link da nossa plataforma oficial de compras/representantes: https://comprarskypaper.hidrahome.com.br/
   - Convide a se cadastrar na página para que a equipe comercial ou representante da região entre em contato.

2. CONSUMIDORES FINAIS / ONDE COMPRAR:
   - Explique com carinho que a SkyPaper atende papelarias e lojas de todo o país, mas que os produtos podem ser encontrados nas principais papelarias físicas e lojas online parceiras (como Mercado Livre, Shopee e papelarias virtuais).
   - Descubra qual o produto, personagem ou categoria que o consumidor está procurando e envie o link exato do nosso catálogo abaixo.

3. SAC / DÚVIDAS DE PEDIDOS:
   - Para suporte direto a pedidos, defeitos ou problemas, oriente a enviar mensagem para o SAC: sac@skypaperinc.com.br.

4. TRANSBORDO HUMANO:
   - Se o cliente solicitar explicitamente falar com um atendente humano ou se tiver uma dúvida fora do seu escopo, responda: "Sem problemas! Já avisei nossa equipe humana. Aguarde um instante que logo te responderemos por aqui! 😊"

DIRETRIZES DE ESTILO:
- Seja caloroso, use emojis pontuais de papelaria e origami (✏️, 📒, ✨, 🕊️).
- Mantenha respostas concisas (2 a 4 frases no máximo), ideais para leitura rápida no direct do Instagram.
- Nunca invente preços específicos ou dados de estoque não informados.

REGRA PÉTREA:
- Sua base de dados sobre produtos deve ser exclusivamente o site oficial https://skypaperinc.com.br/
- Nunca invente nenhuma resposta que você não tenha certeza absoluta. Caso na sua consulta não encontre o produto específico procurado, devolva o link da nossa página principal: https://skypaperinc.com.br/

{SKYPAPER_CATALOG_KNOWLEDGE}
"""

class ConversationMemory:
    """Gerencia memória em curto prazo das conversas por usuário."""
    def __init__(self, max_history: int = 8, ttl_seconds: int = 3600):
        self.max_history = max_history
        self.ttl_seconds = ttl_seconds
        self.sessions: Dict[str, List[dict]] = {}
        self.last_updated: Dict[str, float] = {}

    def get_history(self, user_id: str) -> List[dict]:
        now = time.time()
        # Se passou de 1 hora sem falar, zera a memória
        if user_id in self.last_updated and (now - self.last_updated[user_id]) > self.ttl_seconds:
            self.sessions.pop(user_id, None)
            self.last_updated.pop(user_id, None)
            return []
        return self.sessions.get(user_id, [])

    def add_message(self, user_id: str, role: str, text: str):
        if user_id not in self.sessions:
            self.sessions[user_id] = []
        self.sessions[user_id].append({"role": role, "text": text})
        # Mantém apenas as últimas N mensagens
        if len(self.sessions[user_id]) > self.max_history:
            self.sessions[user_id] = self.sessions[user_id][-self.max_history:]
        self.last_updated[user_id] = time.time()

# Instância global da memória de conversas
memory = ConversationMemory(max_history=8, ttl_seconds=3600)

async def generate_dm_response(user_id: str, user_message: str) -> str:
    """Gera uma resposta via Gemini API com histórico e contexto para o Tsuru."""
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY não configurada. Usando resposta padrão.")
        return "Olá! Sou o Tsuru da SkyPaper. 🕊️✨ Em instantes nossa equipe vai te responder por aqui!"

    model = GEMINI_MODEL or "gemini-3-flash-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

    # Resgata histórico existente e adiciona a nova mensagem do usuário
    history = memory.get_history(user_id)
    memory.add_message(user_id, "user", user_message)

    # Monta as mensagens para a API
    contents = []
    for msg in history:
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["text"]}]
        })
    # Adiciona a mensagem atual
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": SKYPAPER_SYSTEM_PROMPT}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": 300
        }
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            bot_reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Salva a resposta do bot na memória para a próxima iteração
            memory.add_message(user_id, "model", bot_reply)
            return bot_reply
    except Exception as e:
        logger.error(f"Erro ao chamar Gemini API ({model}): {e}", exc_info=True)
        fallback = (
            "Olá! Sou o Tsuru da SkyPaper! 🕊️✨\n\n"
            "Se você quer revender nossos produtos ou ver o catálogo no atacado, "
            "acesse: https://comprarskypaper.hidrahome.com.br/\n\n"
            "Para conhecer nossos produtos, acesse: https://skypaperinc.com.br/ 💖"
        )
        return fallback
