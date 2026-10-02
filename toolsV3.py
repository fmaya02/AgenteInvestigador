"""Tools de la versión 3: búsqueda web + memoria de corto plazo (TODOs y notas).

Las tools leen el estado con `runtime.state` y lo escriben devolviendo un
`Command(update=...)`. El checkpointer (ver agenteV3.py) persiste ese estado
por thread.
"""
import os
from typing import Annotated, Literal, Any
from dotenv import load_dotenv
from langchain_tavily import TavilySearch
from langchain.agents import AgentState
from langchain.messages import ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.types import Command
from typing_extensions import TypedDict
from dataclasses import dataclass

MAX_NOTAS = 8          # cantidad máxima de notas guardadas en el estado
MAX_CHARS_NOTA = 1500  # largo máximo de cada nota (el excedente se trunca)

load_dotenv()

if not os.getenv("TAVILY_API_KEY"):
    raise RuntimeError("Falta TAVILY_API_KEY. Agregala a tu .env (ver .env.example).")

_tavily = TavilySearch(
    max_results=4,
    topic="general",
    search_depth="basic",
    include_answer=False,
)

class Todo(TypedDict):
    task: str
    status: Literal["pending", "in_progress", "done"]

@dataclass
class Context:
    """Datos de solo lectura de cada invocación (runtime context, no se guarda en el estado)."""
    turn: int

def _merge_notes(actuales: dict | None, nuevas: dict) -> dict:
    """Reducer: combina las notas nuevas con las existentes en vez de pisarlas."""
    return {**(actuales or {}), **nuevas}

def _merge_sources(actuales: list | None, nuevas: list) -> list:
    """Reducer: acumula fuentes sin repetir la misma URL dentro de un turno."""
    por_clave = {(s["turn"], s["url"]): s for s in (actuales or []) + nuevas}
    return list(por_clave.values())

class ResearchState(AgentState):
    """Estado del agente: `messages` (heredado) + TODOs + notas + fuentes."""
    todos: list[Todo]
    notes: Annotated[dict[str, str], _merge_notes]
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
def write_todos(todos: list[Todo], runtime: ToolRuntime) -> Command:
    """Escribe la lista de TODOs del plan, REEMPLAZANDO la anterior.

    Usala al empezar una tarea de varios pasos y cada vez que cambie el estado
    de un item (pending -> in_progress -> done). Enviá siempre la lista completa.
    """
    return _respond(runtime, f"TODOs actualizados ({len(todos)} items).", todos=todos)


@tool
def read_todos(runtime: ToolRuntime) -> str:
    """Lee la lista de TODOs actual, con el estado de cada item."""
    todos = runtime.state.get("todos", [])
    if not todos:
        return "No hay TODOs."
    return "\n".join(f"[{t['status']}] {t['task']}" for t in todos)


@tool
def save_note(key: str, content: str, runtime: ToolRuntime) -> Command:
    """Guarda un resultado intermedio (resumido) bajo una clave corta y descriptiva.

    Si la clave ya existe, se sobrescribe. Hay un máximo de notas y de largo por
    nota: guardá solo lo esencial (datos, cifras, URLs), no páginas completas.
    """
    notes = runtime.state.get("notes", {})
    if key not in notes and len(notes) >= MAX_NOTAS:
        return _respond(
            runtime,
            f"Límite de {MAX_NOTAS} notas alcanzado. Sobrescribí una existente: {list(notes)}.",
        )
    aviso = f" (truncada a {MAX_CHARS_NOTA} caracteres)" if len(content) > MAX_CHARS_NOTA else ""
    return _respond(runtime, f"Nota '{key}' guardada{aviso}.", notes={key: content[:MAX_CHARS_NOTA]})


@tool
def read_notes(runtime: ToolRuntime, key: str = "") -> str:
    """Lee una nota por su clave. Sin clave, lista las claves disponibles."""
    notes = runtime.state.get("notes", {})
    if not key:
        return f"Claves disponibles: {list(notes)}" if notes else "No hay notas."
    return notes.get(key, f"No existe la nota '{key}'. Claves: {list(notes)}")


TOOLS: list = [web_search, write_todos, read_todos, save_note, read_notes]