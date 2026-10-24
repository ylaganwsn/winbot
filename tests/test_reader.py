import pytest

from winbot import convert, reader


def test_pdf_goes_straight_to_read_pdf(monkeypatch):
    monkeypatch.setattr(reader, "read_pdf", lambda p: [{"page": 1, "text": f"read {p}"}])

    def no_convert(*args):
        raise AssertionError("PDFs must not be converted")

    monkeypatch.setattr(reader, "convert_to_pdf", no_convert)

    assert reader.read_document("a.PDF") == [{"page": 1, "text": "read a.PDF"}]


@pytest.mark.parametrize(
    "name", ["a.docx", "a.pptx", "a.xlsx", "a.csv", "a.txt", "a.md", "A.DOCX"]
)
def test_other_supported_types_are_converted_then_read(monkeypatch, name):
    converted = []

    def fake_convert(path, outdir):
        converted.append(str(path))
        return "converted.pdf"

    monkeypatch.setattr(reader, "convert_to_pdf", fake_convert)
    monkeypatch.setattr(reader, "read_pdf", lambda p: [{"page": 1, "text": p}])

    result = reader.read_document(name)
    assert converted == [name]
    assert result == [{"page": 1, "text": "converted.pdf"}]


@pytest.mark.parametrize("name", ["a.zip", "a.exe", "noextension"])
def test_unsupported_types_raise(name):
    with pytest.raises(ValueError, match="Unsupported file type"):
        reader.read_document(name)


def test_missing_libreoffice_gives_a_clear_error(monkeypatch):
    monkeypatch.setattr(convert.shutil, "which", lambda name: None)
    monkeypatch.setattr(convert.os.path, "exists", lambda path: False)
    with pytest.raises(RuntimeError, match="LibreOffice not found"):
        convert.find_soffice()