import sqlite3
import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("skypaper_bot.analytics")
DB_PATH = os.getenv("ANALYTICS_DB_PATH", "skypaper_analytics.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db():
    """Inicializa as tabelas de métricas e auditoria da SkyPaper."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabela de Interações
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                event_type TEXT, -- comment, dm, story_mention, button_click
                profile_type TEXT, -- lojista, representante, consumidor, sac, contingencia, geral
                sentiment TEXT, -- positive, neutral, negative
                campaign_tag TEXT, -- quero, catalogo, revender, volta_as_aulas, padrao
                text_snippet TEXT
            );
            """)

            # Tabela de buscas de produtos e linhas
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                product_line TEXT
            );
            """)

            # Tabela de status e contingência de sites
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_health_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                site_name TEXT,
                site_url TEXT,
                status_code INTEGER,
                is_up BOOLEAN,
                latency_ms INTEGER
            );
            """)

            conn.commit()
            logger.info("Banco de dados SQLite de Analytics e Auditoria inicializado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de analytics: {e}", exc_info=True)

# Inicializa o banco no carregamento do módulo
init_db()

def record_interaction(
    user_id: str,
    event_type: str,
    profile_type: str = "geral",
    sentiment: str = "neutral",
    campaign_tag: Optional[str] = None,
    text_snippet: str = ""
):
    """Registra uma interação no banco de dados para os relatórios da diretoria."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interactions (user_id, event_type, profile_type, sentiment, campaign_tag, text_snippet)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(user_id), event_type, profile_type, sentiment, campaign_tag or "padrao", text_snippet[:250]))
            conn.commit()
    except Exception as e:
        logger.error(f"Erro ao registrar interação no banco: {e}")

def record_product_search(user_id: str, product_line: str):
    """Registra menção de uma linha ou produto específico."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO product_searches (user_id, product_line)
                VALUES (?, ?)
            """, (str(user_id), product_line))
            conn.commit()
    except Exception as e:
        logger.error(f"Erro ao registrar busca de produto: {e}")

def record_site_health(site_name: str, site_url: str, status_code: int, is_up: bool, latency_ms: int):
    """Registra resultado do monitoramento de saúde do site."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO site_health_logs (site_name, site_url, status_code, is_up, latency_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (site_name, site_url, status_code, 1 if is_up else 0, latency_ms))
            conn.commit()
    except Exception as e:
        logger.error(f"Erro ao registrar saúde de site: {e}")

def get_executive_summary() -> Dict[str, Any]:
    """Compila os dados executivos para a diretoria da SkyPaper."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # 1. Total Geral e por Evento
            cursor.execute("SELECT COUNT(*) as total FROM interactions")
            total_interactions = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total_today FROM interactions WHERE date(timestamp) = date('now')")
            today_interactions = cursor.fetchone()["total_today"]

            cursor.execute("""
                SELECT event_type, COUNT(*) as count 
                FROM interactions 
                GROUP BY event_type
            """)
            by_event = {row["event_type"]: row["count"] for row in cursor.fetchall()}

            # 2. Distribuição por Perfil de Cliente
            cursor.execute("""
                SELECT profile_type, COUNT(*) as count 
                FROM interactions 
                GROUP BY profile_type
            """)
            by_profile = {row["profile_type"]: row["count"] for row in cursor.fetchall()}

            # 3. Distribuição por Sentimento (SAC e Satisfação)
            cursor.execute("""
                SELECT sentiment, COUNT(*) as count 
                FROM interactions 
                GROUP BY sentiment
            """)
            by_sentiment = {row["sentiment"]: row["count"] for row in cursor.fetchall()}

            # 4. Campanhas mais acionadas
            cursor.execute("""
                SELECT campaign_tag, COUNT(*) as count 
                FROM interactions 
                WHERE campaign_tag != 'padrao'
                GROUP BY campaign_tag 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_campaigns = [{"campaign": row["campaign_tag"], "count": row["count"]} for row in cursor.fetchall()]

            # 5. Top Produtos/Linhas mais procuradas
            cursor.execute("""
                SELECT product_line, COUNT(*) as count 
                FROM product_searches 
                GROUP BY product_line 
                ORDER BY count DESC 
                LIMIT 8
            """)
            top_products = [{"product": row["product_line"], "count": row["count"]} for row in cursor.fetchall()]

            # 6. Últimos registros de saúde dos sites
            cursor.execute("""
                SELECT site_name, site_url, status_code, is_up, latency_ms, timestamp
                FROM site_health_logs
                ORDER BY id DESC
                LIMIT 2
            """)
            latest_health = [dict(row) for row in cursor.fetchall()]

            # 7. Últimas 15 interações
            cursor.execute("""
                SELECT timestamp, event_type, profile_type, sentiment, campaign_tag, text_snippet 
                FROM interactions 
                ORDER BY id DESC 
                LIMIT 15
            """)
            recent_interactions = [dict(row) for row in cursor.fetchall()]

            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_interactions": total_interactions,
                "today_interactions": today_interactions,
                "by_event": by_event,
                "by_profile": by_profile,
                "by_sentiment": by_sentiment,
                "top_campaigns": top_campaigns,
                "top_products": top_products,
                "latest_health": latest_health,
                "recent_interactions": recent_interactions
            }
    except Exception as e:
        logger.error(f"Erro ao gerar resumo executivo: {e}", exc_info=True)
        return {
            "error": str(e),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_interactions": 0
        }
