import os

import pypdfium2 as pdfium
import requests
import streamlit as st

API_URL = os.environ.get("WINBOT_API_URL", "http://127.0.0.1:8000")
FILE_TYPES = ["pdf", "docx", "pptx", "xlsx", "csv", "txt", "md"]

st.set_page_config(page_title="Winbot", layout="wide")


def api_error(response):
    """The plain-language reason the API gave, or a generic one."""
    try:
        return response.json()["detail"]
    except (ValueError, KeyError, TypeError):
        return f"The API returned an error ({response.status_code})."


def load_documents():
    response = requests.get(f"{API_URL}/documents", timeout=10)
    response.raise_for_status()
    return response.json()


@st.cache_data(max_entries=3, show_spinner=False)
def pdf_bytes(doc_id):
    """Download the document's PDF once and keep it for the next page views."""
    link = requests.get(f"{API_URL}/documents/{doc_id}/file", timeout=10)
    link.raise_for_status()
    pdf = requests.get(link.json()["url"], timeout=60)
    pdf.raise_for_status()
    return pdf.content


@st.cache_data(max_entries=40, show_spinner=False)
def page_image(doc_id, page):
    """One page of the PDF as a picture (page numbers start at 1)."""
    pdf = pdfium.PdfDocument(pdf_bytes(doc_id))
    try:
        return pdf[page - 1].render(scale=2).to_pil()
    finally:
        pdf.close()


def load_messages(doc_id):
    response = requests.get(f"{API_URL}/documents/{doc_id}/messages", timeout=10)
    response.raise_for_status()
    return response.json()


def ask_question(doc_id, question):
    """Returns (answer, None) or (None, plain-language error)."""
    try:
        response = requests.post(
            f"{API_URL}/documents/{doc_id}/ask",
            json={"question": question},
            timeout=90,
        )
    except requests.RequestException:
        return None, "Could not reach the Winbot API. Try again."
    if response.status_code == 200:
        return response.json(), None
    return None, api_error(response)


def jump_to(doc_id, page):
    """Button callback: move the viewer to this page."""
    st.session_state[f"page-{doc_id}"] = page


def show_answer(doc_id, tag, answer, pages, provider):
    st.markdown(answer)
    if pages:
        columns = st.columns([1] * len(pages) + [max(1, 6 - len(pages))])
        for column, number in zip(columns, pages):
            column.button(
                f"Page {number}",
                key=f"source-{doc_id}-{tag}-{number}",
                on_click=jump_to,
                args=(doc_id, number),
            )
    if provider != "none":
        st.caption(f"Answered by {provider}")


def upload_document(uploaded):
    response = requests.post(
        f"{API_URL}/documents",
        files={"file": (uploaded.name, uploaded.getvalue())},
        timeout=300,  # converting a big Office file can take a while
    )
    if response.status_code == 201:
        return response.json(), None
    return None, api_error(response)


if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

st.title("Winbot")

try:
    documents = load_documents()
except requests.RequestException:
    st.error(f"Cannot reach the Winbot API at {API_URL}.")
    st.stop()

with st.sidebar:
    st.header("Documents")

    uploaded = st.file_uploader(
        "Upload a document",
        type=FILE_TYPES,
        key=f"uploader-{st.session_state.uploader_key}",
    )
    if uploaded and st.button("Upload", type="primary"):
        with st.spinner("Reading your document..."):
            created, error = upload_document(uploaded)
        if error:
            st.error(error)
        else:
            st.session_state.selected = created["doc_id"]
            st.session_state.uploader_key += 1  # empties the upload box
            st.rerun()

    ready = [d for d in documents if d["status"] == "ready"]
    if ready:
        ids = [d["doc_id"] for d in ready]
        names = {d["doc_id"]: d["filename"] for d in ready}
        selected = st.selectbox(
            "Open a document",
            ids,
            format_func=names.get,
            key="selected",
        )
    else:
        selected = None
        st.caption("No documents yet. Upload one to begin.")

if selected is None:
    st.info("Upload a document in the sidebar to get started.")
    st.stop()

document = next(d for d in ready if d["doc_id"] == selected)
st.subheader(document["filename"])
st.caption(f"{document['pages']} pages · ready to answer questions")

viewer, chat = st.columns([3, 2], gap="large")

with viewer:
    page_key = f"page-{selected}"
    st.session_state.setdefault(page_key, 1)
    page = st.number_input(
        "Go to page",
        min_value=1,
        max_value=document["pages"],
        step=1,
        key=page_key,
    )
    try:
        image = page_image(selected, page)
    except (requests.RequestException, pdfium.PdfiumError):
        st.error("Could not load the document preview. Try again in a moment.")
    else:
        st.image(image, width="stretch")

with chat:
    st.markdown("**Ask about this document**")
    try:
        history = load_messages(selected)
    except requests.RequestException:
        history = []
        st.warning("Could not load the earlier chat. You can still ask a question.")

    messages = st.container(height=560)
    with messages:
        if not history:
            st.caption("No questions yet. Ask your first one below.")
        for number, message in enumerate(history):
            with st.chat_message("user"):
                st.write(message["question"])
            with st.chat_message("assistant"):
                show_answer(
                    selected,
                    f"h{number}",
                    message["answer"],
                    message["pages"],
                    message["provider"],
                )

    question = st.chat_input("Ask a question about this document", max_chars=1000)
    if question:
        with messages:
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                with st.spinner("Looking through the document..."):
                    result, error = ask_question(selected, question)
                if error:
                    st.error(error)
                else:
                    show_answer(
                        selected,
                        "new",
                        result["answer"],
                        result["pages"],
                        result["provider"],
                    )