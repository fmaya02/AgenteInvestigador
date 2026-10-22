"""UI de Streamlit para el agente V4. Solo se ocupa de la presentación.

La lógica del agente vive en agenteV4.py; acá se llama a `run_turn` y se muestra
el `TurnResult` que devuelve.

Ejecutar con:  streamlit run appV4.py
"""
import streamlit as st

try:
    from agenteV4 import TurnResult, new_thread, run_turn
except RuntimeError as e:  # por ejemplo, faltan API keys en el .env
    st.error(str(e))
    st.stop()

ICONOS = {"pending": "⬜", "in_progress": "🔄", "done": "✅"}

st.set_page_config(page_title="Agente investigador", page_icon="🔎")


def init_session() -> None:
    """Estado de la conversación: vive en st.session_state, que persiste entre reruns."""
    st.session_state.config = new_thread()   # thread_id propio de esta sesión del navegador
    st.session_state.turno = 0
    st.session_state.historial = []          # entradas: {"role", "content", "result"}
    st.session_state.ultimo = None           # último TurnResult (alimenta la barra lateral)


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
    """Muestra la memoria del agente (TODOs y notas) al final del último turno."""
    ultimo: TurnResult | None = st.session_state.ultimo
    with st.sidebar:
        st.header("Memoria del agente")

        st.subheader("TODOs")
        if ultimo and ultimo.todos:
            for t in ultimo.todos:
                st.markdown(f"{ICONOS.get(t['status'], '•')} {t['task']}")
        else:
            st.caption("Todavía no hay TODOs.")

        st.subheader("Notas")
        if ultimo and ultimo.notes:
            for key, text in ultimo.notes.items():
                with st.expander(f"{key} ({len(text)} caracteres)"):
                    st.markdown(text)
        else:
            st.caption("Todavía no hay notas.")

        if st.button("Nueva conversación"):
            st.session_state.clear()   # el próximo rerun llama a init_session()
            st.rerun()


if "config" not in st.session_state:
    init_session()

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
    st.session_state.ultimo = resultado
    st.session_state.historial += [
        {"role": "user", "content": prompt, "result": None},
        {"role": "assistant", "content": resultado.answer, "result": resultado},
    ]
    st.rerun()   # redibuja todo (historial y barra lateral) desde session_state