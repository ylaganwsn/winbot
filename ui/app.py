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

page = st.number_input(
    "Go to page",
    min_value=1,
    max_value=document["pages"],
    value=1,
    step=1,
    key=f"page-{selected}",
)

try:
    image = page_image(selected, page)
except (requests.RequestException, pdfium.PdfiumError):
    st.error("Could not load the document preview. Try again in a moment.")
else:
    st.image(image, width="stretch")