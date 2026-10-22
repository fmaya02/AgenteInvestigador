"""Agente V4: la lógica del agente, reutilizable desde la consola y desde Streamlit.

`run_turn` ejecuta un turno y devuelve un `TurnResult` con todo lo que hay que
mostrar; cada interfaz (consola o appV4.py) solo se ocupa de presentarlo.

Consola:    python agenteV4.py
Streamlit:  streamlit run appV4.py
"""
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from model import get_model
from toolsV4 import TOOLS, Context, ResearchState, Todo

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
    "Ante una tarea de varios pasos, planificá primero con la lista de TODOs y "
    "mantenela actualizada mientras avanzás. Guardá como notas los resultados "
    "intermedios que vayas a necesitar después, para no repetir búsquedas."
)

agent = create_agent(
    model=get_model(),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    state_schema=ResearchState,     # estado extendido: messages + todos + notes + sources
    context_schema=Context,         # datos de solo lectura por invocación (turno)
    checkpointer=InMemorySaver(),   # persiste el estado entre invocaciones (por thread)
)


@dataclass
class TurnResult:
    """Todo lo que hay que mostrar de un turno, independiente de la interfaz."""
    answer: str
    reasoning: list[str]
    todos: list[Todo]
    notes: dict[str, str]
    sources: list[dict]   # solo las fuentes consultadas en este turno


def new_thread() -> RunnableConfig:
    """Config de una conversación nueva: el thread_id identifica su estado en el checkpointer."""
    return {"configurable": {"thread_id": str(uuid4())}}


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
        notes=result.get("notes", {}),
        sources=[s for s in result.get("sources", []) if s["turn"] == turno],
    )


def print_turn(r: TurnResult) -> None:
    """Muestra un turno por consola."""
    for texto in r.reasoning:
        print(f"[razonamiento] {texto}\n")
    for t in r.todos:
        print(f"[TODO {t['status']}] {t['task']}")
    for key, text in r.notes.items():
        print(f"[nota '{key}'] {len(text)} caracteres")
    for s in r.sources:
        print(f"[fuente] {s['title']} - {s['url']}")
    print(f"Agente: {r.answer}\n")


def main() -> None:
    print("Agente V4 (web search + memoria) listo. Escribí 'salir' para terminar.\n")
    config = new_thread()
    turno = 0

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