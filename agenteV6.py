"""Agente V6: la lógica del agente, reutilizable desde la consola y desde Streamlit.

`run_turn` ejecuta un turno y devuelve un `TurnResult` con todo lo que hay que
mostrar; cada interfaz (consola o appV6.py) solo se ocupa de presentarlo.

Consola:    python agenteV6.py
Streamlit:  streamlit run appV6.py
"""
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from model import get_model
from toolsV6 import TOOLS, Context, ResearchState, Todo

import sqlite3
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver   # reemplaza a InMemorySaver

DIR = Path(__file__).parent
CONV_FILE = DIR / "conversaciones.txt"   # un thread_id por línea; el último es el activo

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

agent = create_agent(
    model=get_model(),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    state_schema=ResearchState,     # estado extendido: messages + todos + sources
    context_schema=Context,         # datos de solo lectura por invocación (turno)
    # Mismo rol que InMemorySaver, pero persiste el estado en un archivo.
    checkpointer=SqliteSaver(sqlite3.connect(DIR / "memoria.db", check_same_thread=False)),   # persiste el estado entre invocaciones (por thread)
)


@dataclass
class TurnResult:
    """Todo lo que hay que mostrar de un turno, independiente de la interfaz."""
    answer: str
    reasoning: list[str]
    todos: list[Todo]
    sources: list[dict]   # solo las fuentes consultadas en este turno


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


def list_threads(limit: int = 5) -> list[tuple[str, str]]:
    """Últimas conversaciones con mensajes, la más reciente primero: (thread_id, título).

    El título es el comienzo del primer mensaje del usuario.
    """
    conversaciones = []
    for thread_id in reversed(_thread_ids()):
        mensajes = saved_state(_config(thread_id)).get("messages", [])
        if mensajes:
            conversaciones.append((thread_id, mensajes[0].text[:40]))
        if len(conversaciones) == limit:
            break
    return conversaciones


def saved_state(config: RunnableConfig) -> dict:
    """Estado guardado de la conversación (vacío si es nueva)."""
    return agent.get_state(config).values


def count_turns(messages: list) -> int:
    """Cada mensaje humano es un turno; sirve para seguir numerando al retomar."""
    return sum(m.type == "human" for m in messages)


def _extract_reasoning(new_messages: list) -> list[str]:
    """Razonamiento de los mensajes del agente del turno actual."""
    return [
        block["reasoning"]
        for m in new_messages if m.type == "ai"
        for block in m.content_blocks
        if block["type"] == "reasoning" and block.get("reasoning")
    ]


def run_turn(user_input: str, config: RunnableConfig, turno: int) -> TurnResult:
    """Ejecuta un turno del agente y devuelve lo que hay que mostrar."""
    # Solo se envía el mensaje nuevo: el historial lo recupera el checkpointer.
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config,
        context=Context(turn=turno),
    )
    messages = result["messages"]
    # Lo que viene después del último mensaje humano es de este turno.
    ultimo_humano = max(i for i, m in enumerate(messages) if m.type == "human")
    return TurnResult(
        answer=messages[-1].text,
        reasoning=_extract_reasoning(messages[ultimo_humano + 1:]),
        todos=result.get("todos", []),
        sources=[s for s in result.get("sources", []) if s["turn"] == turno],
    )


def print_turn(r: TurnResult) -> None:
    """Muestra un turno por consola."""
    for texto in r.reasoning:
        print(f"[razonamiento] {texto}\n")
    for t in r.todos:
        print(f"[TODO {t['status']}] {t['task']}")
    for s in r.sources:
        print(f"[fuente] {s['title']} - {s['url']}")
    print(f"Agente: {r.answer}\n")


def main() -> None:
    print("Agente V6 (web search + memoria) listo. Escribí 'salir' para terminar.\n")
    config = resume_thread()
    mensajes = saved_state(config).get("messages", [])
    turno = count_turns(mensajes)

    # Muestra lo que ya se había hablado.
    for m in mensajes:
        if m.type == "human":
            print(f"Vos: {m.text}")
        elif m.type == "ai" and m.text:
            print(f"Agente: {m.text}\n")

    while True:
        user_input = input("Vos: ").strip()
        if user_input.lower() in {"salir", "exit", "quit"}:
            break
        if not user_input:
            continue

        turno += 1
        print_turn(run_turn(user_input, config, turno))


if __name__ == "__main__":
    main()