"""Static format metadata. Supported formats themselves are derived from the
Calibre catalog (see app.core.introspector); this module only carries the MIME
map used to set the download response's media type."""

MIME_TYPES: dict[str, str] = {
    "azw": "application/vnd.amazon.mobi8-ebook",
    "azw3": "application/vnd.amazon.mobi8-ebook",
    "azw4": "application/vnd.amazon.mobi8-ebook",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "epub": "application/epub+zip",
    "fb2": "application/x-fictionbook+xml",
    "html": "text/html",
    "htmlz": "application/zip",
    "kepub": "application/epub+zip",
    "lit": "application/x-ms-reader",
    "lrf": "application/x-sony-bbeb",
    "mobi": "application/x-mobipocket-ebook",
    "oeb": "application/oebps-package+xml",
    "pdb": "application/x-pilot",
    "pml": "text/plain",
    "pmlz": "application/zip",
    "rb": "application/x-rocketbook",
    "rtf": "application/rtf",
    "snb": "application/x-snb",
    "tcr": "application/x-tcr-ebook",
    "txt": "text/plain",
    "txtz": "application/zip",
    "zip": "application/zip",
    "pdf": "application/pdf",
}
