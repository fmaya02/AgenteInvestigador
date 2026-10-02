"""Agente V2: create_agent con una tool de búsqueda web (Tavily).

Ejecutar con:  python agenteV2.py
"""
from datetime import date

from langchain.agents import create_agent

from model import get_model
from toolsV2 import TOOLS

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
    "URLs de las fuentes que usaste."
)

agent = create_agent(
    model=get_model(),
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
)


def print_reasoning(new_messages: list) -> None:
    """Imprime el razonamiento de los mensajes del agente del turno actual."""
    for m in new_messages:
        if m.type != "ai":
            continue
        for block in m.content_blocks:
            if block["type"] == "reasoning" and block.get("reasoning"):
                print(f"[razonamiento] {block['reasoning']}\n")


def main() -> None:
    print("Agente V2 (con web search) listo. Escribí 'salir' para terminar.\n")
    messages: list = []

    while True:
        user_input = input("Vos: ").strip()
        if user_input.lower() in {"salir", "exit", "quit"}:
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        n_previos = len(messages)  # todo lo que venga después es de este turno
        result = agent.invoke({"messages": messages})

        messages = result["messages"]
        print_reasoning(messages[n_previos:])
        print(f"Agente: {messages[-1].text}\n")


if __name__ == "__main__":
    main()