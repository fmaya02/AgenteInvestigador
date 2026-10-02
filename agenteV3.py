"""Agente V3: V2 + memoria de corto plazo (checkpointer) con TODOs y notas.

Ejecutar con:  python agenteV3.py
"""
from datetime import date
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from model import get_model
from toolsV3 import TOOLS, Context, ResearchState

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
    state_schema=ResearchState,     # estado extendido: messages + todos + notes + turn + sources
    context_schema=Context,   # datos de solo lectura por invocación (turno)
    checkpointer=InMemorySaver(),   # persiste el estado entre invocaciones (por thread)
)


def print_reasoning(new_messages: list) -> None:
    """Imprime el razonamiento de los mensajes del agente del turno actual."""
    for m in new_messages:
        if m.type != "ai":
            continue
        for block in m.content_blocks:
            if block["type"] == "reasoning" and block.get("reasoning"):
                print(f"[razonamiento] {block['reasoning']}\n")


def print_memory(result: dict) -> None:
    """Imprime el estado de la memoria (TODOs y notas) al final del turno."""
    for t in result.get("todos", []):
        print(f"[TODO {t['status']}] {t['task']}")
    for key, text in result.get("notes", {}).items():
        print(f"[nota '{key}'] {len(text)} caracteres")

def print_sources(result: dict, turno: int) -> None:
    """Imprime las fuentes consultadas en este turno (vienen del estado)."""
    for s in result.get("sources", []):
        if s["turn"] == turno:
            print(f"[fuente] {s['title']} - {s['url']}")

def main() -> None:
    print("Agente V3 (web search + memoria) listo. Escribí 'salir' para terminar.\n")
    # El thread_id identifica la conversación: el checkpointer guarda su estado.
    config: RunnableConfig = {"configurable": {"thread_id": str(uuid4())}}
    turno = 0

    while True:
        user_input = input("Vos: ").strip()
        if user_input.lower() in {"salir", "exit", "quit"}:
            break
        if not user_input:
            continue

        turno += 1
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config,
            context=Context(turn=turno),
        )

        messages = result["messages"]
        # Lo que viene después del último mensaje humano es de este turno.
        ultimo_humano = max(i for i, m in enumerate(messages) if m.type == "human")
        print_reasoning(messages[ultimo_humano + 1:])
        print_memory(result)
        print_sources(result, turno)
        print(f"Agente: {messages[-1].text}\n")


if __name__ == "__main__":
    main()