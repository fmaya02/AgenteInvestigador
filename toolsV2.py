"""Tools de la versión 2: búsqueda web con Tavily."""
import os

from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv()

if not os.getenv("TAVILY_API_KEY"):
    raise RuntimeError(
        "Falta TAVILY_API_KEY. Agregala a tu .env (ver .env.example)."
    )

# TavilySearch lee TAVILY_API_KEY del entorno automáticamente.
web_search = TavilySearch(
    max_results=4,          # pocos resultados = menos tokens de contexto
    topic="general",        # también existe "news" y "finance"
    search_depth="basic",   # "advanced" es más preciso pero gasta más créditos
    include_answer=False,   # que el resumen lo haga nuestro agente, no Tavily
)

TOOLS: list = [web_search]