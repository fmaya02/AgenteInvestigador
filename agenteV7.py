"""Agente V7: lógica del agente con streaming, reutilizable desde consola y Streamlit.

`stream_turn` ejecuta un turno y emite *eventos* (razonamiento, llamadas a tools,
resultados, texto) a medida que el agente avanza. `saved_turns` reconstruye los
mismos eventos desde la conversación guardada. Cada interfaz solo los presenta.

Consola:    python agenteV7.py
Streamlit:  streamlit run appV7.py
"""
import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from uuid import uuid4

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

from model import get_model
from toolsV7 import TOOLS, Context, ResearchState

# La fecha se fija al declarar el prompt (al iniciar el programa); no se
# actualiza si la sesión cruza la medianoche.
HOY = date.today()

SYSTEM_PROMPT = (
    "Sos un asistente útil y conciso. Respondé en el idioma del usuario. "
    f"La fecha de hoy es {HOY.isoformat()} (AAAA-MM-DD). Tené en cuenta esta "
    "fecha para razonar sobre qué es 'reciente', 'actual' o 'último', y no "
    "asumas que el año actual es el de tu entrenamiento. "
    "Usá la herramienta de búsqueda web cuando la pregunta requiera información "
    "actual o que no conozcas con certeza; si la búsqueda es sobre algo "
    f"reciente, incluí el año ({HOY.year}) en la consulta. Si buscás, citá las "
    "URLs de las fuentes que usaste. "
    "Para preguntas sobre LangChain o LangGraph, consultá primero la base de "
    "conocimiento (search_knowledge_base) y complementá con la búsqueda web si "
    "hace falta información actual. Citá los archivos de la base de conocimiento "
    "que uses. "
    "Ante una tarea de varios pasos, planificá primero con la lista de TODOs y "
    "mantenela actualizada mientras avanzás."
)

DIR = Path(__file__).parent
CONV_FILE = DIR / "conversaciones.txt"   # un thread_id por línea; el último es el activo

agent = create_agent(
    model=get_model(),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    state_schema=ResearchState,     # estado extendido: messages + todos + sources
    context_schema=Context,         # datos de solo lectura por invocación (turno)
    checkpointer=SqliteSaver(sqlite3.connect(DIR / "memoria.db", check_same_thread=False)),
)


# --- Conversaciones (sin cambios respecto de V5.5) ---------------------------

def _config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


def _thread_ids() -> list[str]:
    return CONV_FILE.read_text().split() if CONV_FILE.exists() else []


def select_thread(thread_id: str) -> RunnableConfig:
    """Marca una conversación como la activa: pasa a ser la última del archivo."""
    ids = [i for i in _thread_ids() if i != thread_id]
    CONV_FILE.write_text("\n".join(ids + [thread_id]))
    return _config(thread_id)


def new_thread() -> RunnableConfig:
    return select_thread(str(uuid4()))


def resume_thread() -> RunnableConfig:
    """Retoma la última conversación usada; si no hay ninguna, crea una nueva."""
    ids = _thread_ids()
    return select_thread(ids[-1]) if ids else new_thread()


def saved_state(config: RunnableConfig) -> dict:
    """Estado guardado de la conversación (vacío si es nueva)."""
    return agent.get_state(config).values


def list_threads(limit: int = 5) -> list[tuple[str, str]]:
    """Últimas conversaciones con mensajes, la más reciente primero: (thread_id, título)."""
    conversaciones = []
    for thread_id in reversed(_thread_ids()):
        mensajes = saved_state(_config(thread_id)).get("messages", [])
        if mensajes:
            conversaciones.append((thread_id, mensajes[0].text[:40]))
        if len(conversaciones) == limit:
            break
    return conversaciones


# --- Eventos: lo único que las interfaces necesitan conocer ------------------

def _razonamiento(m) -> str:
    """Razonamiento de un mensaje del agente.

    Gemini y OpenRouter lo traen como bloques estándar `reasoning`; LM Studio
    como `reasoning_content` (lo conserva chat_lmstudio.py).
    """
    bloques = [
        b["reasoning"] for b in m.content_blocks
        if b["type"] == "reasoning" and b.get("reasoning")
    ]
    return "\n\n".join(bloques) or m.additional_kwargs.get("reasoning_content", "")


def eventos(mensajes: list) -> Iterator[dict]:
    """Traduce mensajes del grafo a eventos para mostrar."""
    for m in mensajes:
        if m.type == "ai":
            if razonamiento := _razonamiento(m):
                yield {"tipo": "razonamiento", "texto": razonamiento}
            if m.text:
                yield {"tipo": "texto", "texto": m.text}
            for call in m.tool_calls:
                yield {"tipo": "llamada", "id": call["id"], "nombre": call["name"], "args": call["args"]}
        elif m.type == "tool":
            yield {"tipo": "resultado", "id": m.tool_call_id, "texto": m.text, "datos": m.artifact}


def _evento_fuentes(estado: dict, turno: int) -> list[dict]:
    """Fuentes consultadas en un turno (lista vacía si no hubo)."""
    fuentes = [s for s in estado.get("sources", []) if s["turn"] == turno]
    return [{"tipo": "fuentes", "fuentes": fuentes}] if fuentes else []


def stream_turn(user_input: str, config: RunnableConfig, turno: int) -> Iterator[dict]:
    """Ejecuta un turno del agente y emite sus eventos a medida que ocurren."""
    vistos = len(saved_state(config).get("messages", []))
    estado: dict = {}
    # stream_mode="values": tras cada paso del agente llega el estado completo;
    # solo se emiten los mensajes que no se habían visto todavía.
    for estado in agent.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        context=Context(turn=turno),
        stream_mode="values",
    ):
        yield from eventos(estado["messages"][vistos:])
        vistos = len(estado["messages"])
    yield from _evento_fuentes(estado, turno)


def saved_turns(config: RunnableConfig) -> list[tuple[str, list[dict]]]:
    """La conversación guardada como turnos: (pregunta, eventos del agente)."""
    estado = saved_state(config)
    turnos: list[tuple[str, list[dict]]] = []
    for m in estado.get("messages", []):
        if m.type == "human":
            turnos.append((m.text, []))
        else:
            turnos[-1][1].extend(eventos([m]))
    for n, (_, evs) in enumerate(turnos, 1):
        evs.extend(_evento_fuentes(estado, n))
    return turnos


# --- Consola -----------------------------------------------------------------

def print_evento(e: dict) -> None:
    """Muestra un evento por consola."""
    tipo = e["tipo"]
    if tipo == "razonamiento":
        print(f"[razonamiento] {e['texto']}\n")
    elif tipo == "llamada":
        print(f"[tool] {e['nombre']}({e['args']})")
    elif tipo == "resultado":
        print(f"[resultado] {e['texto'][:200]}\n")
    elif tipo == "fuentes":
        for s in e["fuentes"]:
            print(f"[fuente] {s['title']} - {s['url']}")
    elif tipo == "texto":
        print(f"Agente: {e['texto']}\n")


def main() -> None:
    print("Agente V7 (streaming) listo. Escribí 'salir' para terminar.\n")
    config = resume_thread()

    turnos = saved_turns(config)      # muestra lo que ya se había hablado
    for pregunta, evs in turnos:
        print(f"Vos: {pregunta}")
        for e in evs:
            print_evento(e)
    turno = len(turnos)

    while True:
        user_input = input("Vos: ").strip()
        if user_input.lower() in {"salir", "exit", "quit"}:
            break
        if not user_input:
            continue

        turno += 1
        for e in stream_turn(user_input, config, turno):
            print_evento(e)


if __name__ == "__main__":
    main()