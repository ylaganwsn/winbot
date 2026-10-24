import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

WINDOWS_SOFFICE = r"C:\Program Files\LibreOffice\program\soffice.exe"
CONVERTIBLE = {".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md"}
TIMEOUT_SECONDS = 120


def find_soffice():
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    if os.path.exists(WINDOWS_SOFFICE):
        return WINDOWS_SOFFICE
    raise RuntimeError("LibreOffice not found. Install it to convert this file type.")


def _wait_for_file(path, deadline):
    """soffice can return before the PDF is fully written, so wait for it."""
    last_size = -1
    while time.monotonic() < deadline:
        if path.exists():
            size = path.stat().st_size
            if size > 0 and size == last_size:
                return True
            last_size = size
        time.sleep(0.5)
    return False


def convert_to_pdf(path, outdir):
    path = Path(path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    soffice = find_soffice()
    deadline = time.monotonic() + TIMEOUT_SECONDS

    # ignore_cleanup_errors: on Windows soffice may still hold its profile files
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as work:
        source = path
        if path.suffix.lower() == ".md":
            # LibreOffice does not know .md, so give it a .txt copy
            source = Path(work) / (path.stem + ".txt")
            shutil.copyfile(path, source)

        profile = Path(work) / "profile"
        subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={profile.as_uri()}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(outdir),
                str(source),
            ],
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
        )

        pdf = outdir / (source.stem + ".pdf")
        if not _wait_for_file(pdf, deadline):
            raise RuntimeError(f"Could not convert {path.name} to PDF.")
        return pdf