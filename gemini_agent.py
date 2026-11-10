import logging
import time
import json
import urllib.request
import asyncio
from typing import Dict, List, Optional, Any
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

SKYPAPER_SYSTEM_PROMPT = f"""Você é o Tsuru, assistente virtual inteligente, acolhedor e oficial da SkyPaper no Instagram (@skypaper.inc).
Seu objetivo é ler cada mensagem com atenção e empatia, compreendendo profundamente o contexto, a intenção e os sentimentos da pessoa para prestar o melhor atendimento.

SOBRE A SKYPAPER:
- A SkyPaper é uma marca inovadora de papelaria criativa, material escolar e escritório.
- Destaques: Linhas exclusivas e licenciadas (Luluca, Rebecca Bonbon, Flamengo, One Piece, Naruto, Capivara, Moranguinho, Linha Fofa e muito mais).
- Canais oficiais: Site www.skypaperinc.com.br | E-mail: sac@skypaperinc.com.br

REGRAS DE ATENDIMENTO OBRIGATÓRIAS:

1. LOJISTAS / ATACADO / REPRESENTANTES / QUERO REVENDER:
   - Se a pessoa for lojista, papelaria, revendedor ou representante: acolha com entusiasmo.
   - Forneça o link da nossa plataforma de compras e cadastro: https://comprarskypaper.hidrahome.com.br/
   - Convide a se cadastrar na página para que a equipe comercial entre em contato com a tabela de atacado e condições.

2. CONSUMIDORES FINAIS / ONDE COMPRAR:
   - Explique com carinho que a SkyPaper atende papelarias de todo o país, mas que os produtos podem ser encontrados nas principais papelarias físicas e lojas online parceiras (Mercado Livre, Shopee e lojas parceiras).
   - Para ver o catálogo completo com todos os produtos, envie: https://skypaperinc.com.br/produtos/
   - Se perguntarem sobre um produto específico, informe sobre ele com base no catálogo abaixo.

3. SAC / DEFEITO / RECLAMAÇÃO / PROBLEMA COM PRODUTO (REGRA RIGOROSA):
   - Se o cliente relatar defeito, produto quebrado, rasgado, avariado, atraso ou qualquer insatisfação, responda OBRIGATORIAMENTE com esta frase:
     "Infelizmente essa não é a experiência que gostaríamos que tivesse, peço que entre em contato conosco através do nosso email: sac@skypaperinc.com.br enviando a foto do produto e da nota fiscal."
   - SE O CLIENTE RESPONDER OU DISSER QUE NÃO TEM NOTA FISCAL (perdeu a nota, foi presente, comprou sem nota):
     Responda OBRIGATORIAMENTE com esta frase:
     "Sem problemas! Envie o e-mail para sac@skypaperinc.com.br mesmo assim, para que o SAC siga com o atendimento."

4. CONTINGÊNCIA / SITE FORA DO AR OU COM ERRO:
   - NUNCA INFORME NENHUM NÚMERO DE WHATSAPP DA SKYPAPER.
   - Se o cliente relatar que o site está fora do ar, travado ou não abre, responda com acolhimento:
     "Pedimos desculpas pela instabilidade no momento! 🙏 Nossa equipe técnica já foi acionada para restabelecer o acesso o quanto antes. Assim que o site for restabelecido, eu mesmo retorno e te aviso por aqui no direct! 🌸🕊️ Se tiver qualquer dúvida urgente, nosso e-mail oficial é sac@skypaperinc.com.br."

5. TRANSBORDO HUMANO:
   - Se o cliente solicitar falar com atendente humano: "Sem problemas! Já avisei nossa equipe humana. Aguarde um instante que logo te responderemos por aqui! 😊"

DIRETRIZES DE ESTILO:
- Seja caloroso, use emojis pontuais de papelaria e origami (✏️, 📒, ✨, 🕊️).
- Mantenha respostas concisas (2 a 4 frases no máximo), ideais para leitura rápida no direct do Instagram.
- Nunca invente preços específicos ou dados de estoque não informados.
- NUNCA informe número de WhatsApp da empresa em nenhuma hipótese.

REGRA PÉTREA:
- Sua base de dados sobre produtos deve ser exclusivamente o site oficial https://skypaperinc.com.br/
- Caso não encontre um produto específico, forneça a vitrine completa: https://skypaperinc.com.br/produtos/

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
        if user_id in self.last_updated and (now - self.last_updated[user_id]) > self.ttl_seconds:
            self.sessions.pop(user_id, None)
            self.last_updated.pop(user_id, None)
            return []
        return self.sessions.get(user_id, [])

    def add_message(self, user_id: str, role: str, text: str):
        if user_id not in self.sessions:
            self.sessions[user_id] = []
        self.sessions[user_id].append({"role": role, "text": text})
        if len(self.sessions[user_id]) > self.max_history:
            self.sessions[user_id] = self.sessions[user_id][-self.max_history:]
        self.last_updated[user_id] = time.time()

memory = ConversationMemory(max_history=8, ttl_seconds=3600)

def _sync_gemini_call(url: str, payload: dict, timeout: float = 15.0) -> dict:
    """Executa a chamada HTTP à Gemini API de forma síncrona."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

async def understand_comment_context(comment_text: str) -> Optional[Dict[str, Any]]:
    """
    Usa o Gemini para ler a frase completa do comentário no post/reel e entender profundamente o contexto,
    o tom, a intenção da pessoa e o que ela está procurando, gerando uma resposta contextualizada.
    """
    if not GEMINI_API_KEY:
        return None

    model = GEMINI_MODEL or "gemini-3-flash-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

    prompt = f'''Você é o assistente virtual Tsuru da SkyPaper (@skypaper.inc).
Analise com atenção este comentário feito por um usuário em uma publicação ou Reel:
"{comment_text}"

Leia a frase inteira, compreenda o contexto, o sentimento e o que a pessoa realmente deseja (se quer comprar no atacado para loja, se quer o catálogo, se perguntou sobre um produto específico, se elogiou ou se relatou algum problema).

Diretrizes rigorosas:
1. Se for SAC / reclamação / defeito / insatisfação:
   - "intent": "sac"
   - "is_sac": true
   - "public_reply": uma frase pública empática e responsável (sem comemoração), dizendo que chamou no Direct para ajudar com prioridade máxima.
   - "dm_intro": "Infelizmente essa não é a experiência que gostaríamos que tivesse, peço que entre em contato conosco através do nosso email: sac@skypaperinc.com.br enviando a foto do produto e da nota fiscal."

2. Se demonstrar interesse em revenda / atacado / lojista:
   - "intent": "lojista"
   - "is_sac": false
   - "public_reply": frase pública acolhedora de até 15 palavras dizendo que chamou na DM com as condições de atacado.
   - "dm_intro": frase inicial personalizada reconhecendo o interesse da papelaria/loja.

3. Se perguntar de catálogo / onde comprar / produto específico (ex: Luluca, Rebecca Bonbon, Capivara):
   - "intent": "consumidor"
   - "is_sac": false
   - "public_reply": frase pública calorosa mencionando com carinho o interesse e convidando a olhar a DM.
   - "dm_intro": frase inicial demonstrando que entendeu exatamente o que a pessoa procura.

4. Se for elogio, fã ou empolgação:
   - "intent": "elogio"
   - "is_sac": false
   - "public_reply": frase pública muito afetuosa agradecendo o carinho e dizendo que chamou no Direct.
   - "dm_intro": saudação carinhosa.

Retorne EXCLUSIVAMENTE um JSON válido:
{{
  "intent": "sac" ou "lojista" ou "representante" ou "consumidor" ou "elogio" ou "geral",
  "is_sac": false,
  "public_reply": "frase pública de até 15 palavras com emojis",
  "dm_intro": "frase inicial para a mensagem no Direct"
}}
'''

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 1000,
            "responseMimeType": "application/json"
        }
    }

    try:
        data = await asyncio.to_thread(_sync_gemini_call, url, payload, 15.0)
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Remove marcadores de bloco markdown se presentes
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1:
            raw_text = raw_text[start:end+1]
        return json.loads(raw_text)
    except Exception as e:
        logger.warning(f"Exceção ao analisar comentário com IA: {e}")
        return None

async def generate_dm_response(user_id: str, user_message: str) -> str:
    """Gera resposta via Gemini com contexto e histórico da conversa no Direct."""
    if not GEMINI_API_KEY:
        return "Olá! Sou o Tsuru da SkyPaper. 🕊️✨ Em instantes nossa equipe vai te responder por aqui!"

    model = GEMINI_MODEL or "gemini-3-flash-preview"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

    history = memory.get_history(user_id)
    memory.add_message(user_id, "user", user_message)

    contents = []
    for msg in history:
        contents.append({
            "role": msg["role"],
            "parts": [{"text": msg["text"]}]
        })
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
            "temperature": 0.5,
            "maxOutputTokens": 1000
        }
    }

    try:
        data = await asyncio.to_thread(_sync_gemini_call, url, payload, 20.0)
        bot_reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        memory.add_message(user_id, "model", bot_reply)
        return bot_reply
    except Exception as e:
        logger.error(f"Erro ao chamar Gemini API ({model}): {e}", exc_info=True)
        fallback = (
            "Olá! Sou o Tsuru da SkyPaper! 🕊️✨\n\n"
            "Se você quer revender nossos produtos ou ver o catálogo no atacado, "
            "acesse: https://comprarskypaper.hidrahome.com.br/\n\n"
            "Para conhecer nossos produtos, acesse: https://skypaperinc.com.br/produtos/ 💖"
        )
        return fallback
