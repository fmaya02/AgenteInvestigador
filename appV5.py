"""UI de Streamlit para el agente V5. Solo se ocupa de la presentación.

La lógica del agente vive en agenteV5.py; acá se llama a `run_turn` y se muestra
el `TurnResult` que devuelve.

Ejecutar con:  streamlit run appV5.py
"""
import streamlit as st

try:
    from agenteV5 import (
        TurnResult, count_turns, new_thread, resume_thread, run_turn, saved_state,
    )
except RuntimeError as e:  # por ejemplo, faltan API keys en el .env
    st.error(str(e))
    st.stop()

st.set_page_config(page_title="Agente investigador", page_icon="🔎")


def init_session(config) -> None:
    """Estado de la conversación: vive en st.session_state, que persiste entre reruns.

    Si la conversación ya existía en el checkpointer, se reconstruye el historial.
    """
    mensajes = saved_state(config).get("messages", [])
    st.session_state.config = config
    st.session_state.turno = count_turns(mensajes)
    st.session_state.historial = [
        {"role": "user" if m.type == "human" else "assistant", "content": m.text, "result": None}
        for m in mensajes
        if m.type in ("human", "ai") and m.text   # se omiten tool calls y resultados de tools
    ]


def render_details(r: TurnResult) -> None:
    """Muestra, bajo la respuesta, lo que hizo el agente en ese turno."""
    if r.reasoning:
        with st.expander("Razonamiento"):
            for texto in r.reasoning:
                st.markdown(texto)
    if r.sources:
        with st.expander(f"Fuentes consultadas ({len(r.sources)})"):
            for s in r.sources:
                st.markdown(f"- [{s['title']}]({s['url']})")


def render_sidebar() -> None:
    """Muestra los TODOs guardados en el estado de la conversación."""
    todos = saved_state(st.session_state.config).get("todos", [])
    with st.sidebar:
        st.header("Memoria del agente")

        st.subheader("TODOs")
        if todos:
            for t in todos:
                st.markdown(f"- {t['task']}")
        else:
            st.caption("Todavía no hay TODOs.")

        if st.button("Nueva conversación"):
            init_session(new_thread())
            st.rerun()


if "config" not in st.session_state:
    init_session(resume_thread())

st.title("🔎 Agente investigador")
render_sidebar()

# Streamlit re-ejecuta todo el script en cada interacción: se redibuja el historial guardado.
for entrada in st.session_state.historial:
    with st.chat_message(entrada["role"]):
        st.markdown(entrada["content"])   # st.markdown renderiza el markdown del modelo
        if entrada["result"] is not None:
            render_details(entrada["result"])

if prompt := st.chat_input("Escribí tu consulta..."):
    turno = st.session_state.turno + 1
    st.chat_message("user").markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("El agente está trabajando..."):
            try:
                resultado = run_turn(prompt, st.session_state.config, turno)
            except Exception as e:
                st.error(f"El agente falló: {e}")
                st.stop()

    st.session_state.turno = turno
    st.session_state.historial += [
        {"role": "user", "content": prompt, "result": None},
        {"role": "assistant", "content": resultado.answer, "result": resultado},
    ]
    st.rerun()   # redibuja todo (historial y barra lateral) desde session_state