import re
from typing import Dict, Any, List, Optional, Tuple

# Mapeamento de Campanhas Estratégicas da SkyPaper
CAMPAIGN_RULES = {
    "quero": {
        "keywords": ["quero", "eu quero", "quero saber", "me manda", "manda pra mim"],
        "public_reply": "Acabei de te enviar as novidades exclusivas no seu direct! Dá uma olhadinha lá 💖✨",
        "dm_text": (
            "Olá! Que alegria ver seu interesse nos nossos lançamentos da SkyPaper! 📒✨\n\n"
            "Para eu te passar o material certinho, me conta o que você procura:"
        )
    },
    "catalogo": {
        "keywords": ["catalogo", "catálogo", "pdf", "tabela", "ver produtos"],
        "public_reply": "Te enviei o nosso catálogo oficial por direct! Confere lá 📒📬",
        "dm_text": (
            "Aqui está o seu acesso ao catálogo e linhas exclusivas da SkyPaper! 📚✨\n\n"
            "Escolha abaixo como gostaria de navegar:"
        )
    },
    "revender": {
        "keywords": ["revender", "atacado", "lojista", "comprar no atacado", "quero revender", "tabela de lojista"],
        "public_reply": "Maravilha! Já te mandei o portal exclusivo de atacado no seu direct! 🚀💼",
        "dm_text": (
            "Excelente! A SkyPaper tem condições exclusivas e margens excelentes para lojistas e revendedores! 💼✨\n\n"
            "Acesse nosso canal de compras ou fale com um representante:"
        )
    },
    "volta_as_aulas": {
        "keywords": ["volta as aulas", "volta às aulas", "material escolar", "escolar", "caderno", "mochila"],
        "public_reply": "O Volta às Aulas da SkyPaper está imperdível! Te chamei no direct com tudo 🥰📒",
        "dm_text": (
            "O Volta às Aulas mais lindo e fofo do Brasil está na SkyPaper! 🎒✏️\n\n"
            "Como você gostaria de comprar os materiais:"
        )
    }
}

# Palavras de Alerta para SAC, Reclamações e Problemas Críticos
SAC_KEYWORDS = [
    "defeito", "quebrado", "quebrada", "avariado", "avariada",
    "atraso", "atrasado", "atrasada", "não recebi", "nao recebi",
    "reclamação", "reclamacao", "péssimo", "pessimo", "ruim",
    "estragado", "estragada", "problema", "extravio", "procon",
    "devolver", "devolução", "devolucao", "reembolso", "troca", "trocar"
]

# Palavras para Detecção de Erros ou Instabilidade de Site (Contingência)
CONTINGENCY_KEYWORDS = [
    "fora do ar", "site caiu", "caiu o site", "não consigo acessar", "nao consigo acessar",
    "não consigo entrar", "nao consigo entrar", "não consigo abrir", "nao consigo abrir",
    "erro no site", "site travou", "erro 404", "página não abre", "pagina nao abre",
    "link não funciona", "link nao funciona", "link quebrado", "não carrega", "nao carrega",
    "site com erro", "site dando erro", "site não abre", "site nao abre"
]

# Linhas de Produtos Oficiais da SkyPaper para Rastreamento de Demanda
PRODUCT_LINES = {
    "Rebecca Bonbon": ["rebecca bonbon", "rebeca bonbon", "rb"],
    "Luluca": ["luluca", "lu lú"],
    "Capivara": ["capivara", "linha capivara"],
    "Linha Fofa": ["linha fofa", "kawaii", "fofo", "fofinho"],
    "One Piece": ["one piece", "luffy", "anime"],
    "Flamengo": ["flamengo", "mengo", "mengão"],
    "Naruto": ["naruto"],
    "Moranguinho": ["moranguinho"],
    "Cadernos": ["caderno", "cadernos", "caderneta"],
    "Escrita & Canetas": ["caneta", "marca-texto", "marcador", "borracha", "lápis", "lapis"],
    "Artesanato & EVA": ["eva", "e.v.a", "cola", "tesoura", "artesanato"]
}

def analyze_text(text: str) -> Dict[str, Any]:
    """
    Analisa um comentário ou DM recebido para identificar:
    - Sentimento e alerta de SAC
    - Campanha associada
    - Se é relato de erro no site (contingência)
    - Linhas de produto citadas
    """
    clean_text = (text or "").lower().strip()

    # 1. Checagem de SAC e Reclamação
    is_sac = any(kw in clean_text for kw in SAC_KEYWORDS)
    sentiment = "negative" if is_sac else "neutral"

    # 2. Checagem de Contingência (Site com erro)
    is_contingency = any(kw in clean_text for kw in CONTINGENCY_KEYWORDS)

    # 3. Detecção de Campanha
    campaign_detected = None
    campaign_data = None
    for camp_id, data in CAMPAIGN_RULES.items():
        if any(kw in clean_text for kw in data["keywords"]):
            campaign_detected = camp_id
            campaign_data = data
            if sentiment == "neutral":
                sentiment = "positive"
            break

    # 4. Detecção de Produtos/Linhas
    detected_products = []
    for prod_name, aliases in PRODUCT_LINES.items():
        if any(alias in clean_text for alias in aliases):
            detected_products.append(prod_name)

    return {
        "is_sac": is_sac,
        "is_contingency": is_contingency,
        "sentiment": sentiment,
        "campaign_id": campaign_detected,
        "campaign_data": campaign_data,
        "products": detected_products
    }

NO_INVOICE_KEYWORDS = [
    "não tenho nota", "nao tenho nota", "sem nota", "perdi a nota", "perdi a nf",
    "não tenho nf", "nao tenho nf", "sem nf", "foi presente", "ganhei de presente",
    "comprei sem nota", "não acho a nota", "nao acho a nota", "não tenho a nota", "nao tenho a nota"
]

def is_no_invoice_mention(text: str) -> bool:
    """Verifica se o cliente mencionou que não possui nota fiscal."""
    clean = (text or "").lower().strip()
    return any(kw in clean for kw in NO_INVOICE_KEYWORDS)

def get_no_invoice_reply() -> str:
    """Resposta quando o cliente relata não possuir a nota fiscal."""
    return "Sem problemas! Envie o e-mail para sac@skypaperinc.com.br mesmo assim, para que o SAC siga com o atendimento."

def get_sac_comment_reply() -> str:
    """Resposta pública empática para comentários com reclamações ou problemas."""
    return (
        "Sentimos muito por isso! Queremos te ajudar a resolver o quanto antes. "
        "Te enviamos uma mensagem privada no direct com os nossos canais de suporte prioritário 📩"
    )

def get_sac_dm_response() -> str:
    """Resposta privada no Direct para casos de SAC com prioridade (frase oficial SkyPaper)."""
    return (
        "Infelizmente essa não é a experiência que gostaríamos que tivesse, "
        "peço que entre em contato conosco através do nosso email: sac@skypaperinc.com.br "
        "enviando a foto do produto e da nota fiscal."
    )

def get_contingency_dm_response(issue_type: str = "geral") -> str:
    """Resposta de contingência quando o site está indisponível (sem WhatsApp, com promessa de retorno)."""
    return (
        "Pedimos desculpas pela instabilidade no momento! 🙏 Nossa equipe técnica já está cuidando "
        "disso para restabelecer o acesso o quanto antes.\n\n"
        "Assim que o site for restabelecido, eu mesmo retorno e te aviso por aqui no direct! 🌸🕊️\n\n"
        "Se tiver qualquer dúvida urgente, nosso e-mail oficial é sac@skypaperinc.com.br."
    )
