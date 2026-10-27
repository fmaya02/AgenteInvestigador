"""Tools de la versión 4: búsqueda web + memoria de corto plazo (mensajes + TODOs).

Las tools leen el estado con `runtime.state` y lo escriben devolviendo un
`Command(update=...)`. El checkpointer (ver agenteV4.py) persiste ese estado
por thread. El turno actual llega por el runtime context (`runtime.context`).
"""
import os
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain.agents import AgentState
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from typing_extensions import TypedDict


load_dotenv()

from rag.store import DB_DIR, get_store

if not DB_DIR.exists():
    raise RuntimeError("Falta la base vectorial del RAG. Ejecutá: python -m rag.ingest")

_kb = get_store()

if not os.getenv("TAVILY_API_KEY"):
    raise RuntimeError("Falta TAVILY_API_KEY. Agregala a tu .env (ver .env.example).")

_tavily = TavilySearch(
    max_results=4,
    topic="general",
    search_depth="basic",
    include_answer=False,
)


@dataclass
class Context:
    """Datos de solo lectura de cada invocación (runtime context, no se guarda en el estado)."""
    turn: int


class Todo(TypedDict):
    task: str
    status: Literal["pending", "in_progress", "done"]


def _merge_sources(actuales: list | None, nuevas: list) -> list:
    """Reducer: acumula fuentes sin repetir la misma URL dentro de un turno."""
    por_clave = {(s["turn"], s["url"]): s for s in (actuales or []) + nuevas}
    return list(por_clave.values())


class ResearchState(AgentState):
    """Estado del agente: `messages` (heredado) + TODOs + fuentes."""
    todos: list[Todo]
    sources: Annotated[list[dict], _merge_sources]   # fuentes, cada una con su turno


def _respond(runtime: ToolRuntime[Any, Any], texto: str, **update) -> Command:
    """Actualiza el estado y agrega el ToolMessage que exige todo tool call."""
    msg = ToolMessage(texto, tool_call_id=runtime.tool_call_id)
    return Command(update={**update, "messages": [msg]})


@tool
def web_search(query: str, runtime: ToolRuntime[Context]) -> Command:
    """Busca información actual en la web. Devuelve resultados numerados con su URL.

    En tu respuesta final, citá las URLs de las fuentes que usaste.
    """
    resultados = _tavily.invoke({"query": query}).get("results", [])
    texto = "\n\n".join(
        f"[{i}] {r['title']}\nURL: {r['url']}\n{r['content']}"
        for i, r in enumerate(resultados, 1)
    ) or "Sin resultados."
    turno = runtime.context.turn
    fuentes = [{"turn": turno, "title": r["title"], "url": r["url"]} for r in resultados]
    return _respond(runtime, texto, sources=fuentes)

@tool
def search_knowledge_base(query: str, runtime: ToolRuntime[Context]) -> Command:
    """Busca en la base de conocimiento local: documentos sobre LangChain y LangGraph
    (qué es cada uno, para qué sirven, en qué se diferencian y cuándo usar cada uno).

    Devuelve fragmentos numerados con su archivo de origen. Preferila a la búsqueda
    web para preguntas sobre estos temas.
    """
    chunks = _kb.similarity_search(query, k=4)
    texto = "\n\n".join(
        f"[{i}] Fuente: {c.metadata['source']}\n{c.page_content}"
        for i, c in enumerate(chunks, 1)
    ) or "Sin resultados."
    turno = runtime.context.turn
    fuentes = [
        {
            "turn": turno,
            "title": f"Base de conocimiento: {c.metadata['source']}",
            "url": f"rag/docs/{c.metadata['source']}",   # ruta local, no un link
        }
        for c in chunks
    ]
    return _respond(runtime, texto, sources=fuentes)

@tool
def write_todos(todos: list[Todo], runtime: ToolRuntime[Context]) -> Command:
    """Escribe la lista de TODOs del plan, REEMPLAZANDO la anterior.

    Usala al empezar una tarea de varios pasos y cada vez que cambie el estado
    de un item (pending -> in_progress -> done). Enviá siempre la lista completa.
    """
    return _respond(runtime, f"TODOs actualizados ({len(todos)} items).", todos=todos)


@tool
def read_todos(runtime: ToolRuntime[Context]) -> str:
    """Lee la lista de TODOs actual, con el estado de cada item."""
    todos = runtime.state.get("todos", [])
    if not todos:
        return "No hay TODOs."
    return "\n".join(f"[{t['status']}] {t['task']}" for t in todos)


TOOLS: list = [web_search, search_knowledge_base, write_todos, read_todos]