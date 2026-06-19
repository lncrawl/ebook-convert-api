from enum import StrEnum


class InputFormat(StrEnum):
    AZW = "azw"
    AZW3 = "azw3"
    AZW4 = "azw4"
    CB7 = "cb7"
    CBC = "cbc"
    CBR = "cbr"
    CBZ = "cbz"
    CHM = "chm"
    DJVU = "djvu"
    DOCX = "docx"
    EPUB = "epub"
    FB2 = "fb2"
    FBZ = "fbz"
    HTML = "html"
    HTMLZ = "htmlz"
    IMP = "imp"
    KEPUB = "kepub"
    LIT = "lit"
    LRF = "lrf"
    LRX = "lrx"
    MOBI = "mobi"
    ODT = "odt"
    OEBZIP = "oebzip"
    PDB = "pdb"
    PDF = "pdf"
    PML = "pml"
    PMLZ = "pmlz"
    POBI = "pobi"
    PRC = "prc"
    RB = "rb"
    RTF = "rtf"
    SNB = "snb"
    TCR = "tcr"
    TXT = "txt"
    TXTZ = "txtz"
    UPDB = "updb"
    XHTML = "xhtml"
    XHTM = "xhtm"
    ZIP = "zip"


class OutputFormat(StrEnum):
    AZW3 = "azw3"
    DOCX = "docx"
    EPUB = "epub"
    FB2 = "fb2"
    HTML = "html"
    HTMLZ = "htmlz"
    KEPUB = "kepub"
    LIT = "lit"
    LRF = "lrf"
    MOBI = "mobi"
    OEB = "oeb"
    PDB = "pdb"
    PDF = "pdf"
    PML = "pml"
    PMLZ = "pmlz"
    RB = "rb"
    RTF = "rtf"
    SNB = "snb"
    TCR = "tcr"
    TXT = "txt"
    TXTZ = "txtz"
    ZIP = "zip"


INPUT_FORMATS: frozenset[str] = frozenset(InputFormat)
OUTPUT_FORMATS: frozenset[str] = frozenset(OutputFormat)
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
