"""THE EXIT STANDARD A RENDERED REPORT MUST MEET, measured on the report itself.

Not a style guide and not a test fixture: every check here opens the HTML that was actually
written and the PNG files it actually references, in the directory a run actually produced. A
standard measured on a synthetic page proves the checker runs; it proves nothing about the
report a reader will open.

WHY EACH ONE EXISTS. Measured on a real ten-sample, 2x2 cohort whose report had 191 figures:

  overview      No page said what the cohort was. A reader met "1,654 significant edges" with
                no statement anywhere of how many samples, how many arms, or what was compared.
  arms          NOT ONE figure of 191 split anything by a design factor. The study is
                age x diet; every panel was per-population or per-cell.
  repeats       140 of the 191 were fifteen plots redrawn once per sample. Three plugins
                infer per sample, so those panels are not even comparable with each other.
  count         57 figures on one page. A page a reader cannot finish is a page that hides its
                own result.
  captions      Captions were 65% of all words - 13,172 of 20,545 on the worst page.
  identifiers   The strongest signal in every population of one page was `A0A079HLR9`, an
                unmapped UniProt accession presented as a regulator.
  contradiction Two pages carried headlines their own diagnostics refute: 45.5% of nuclei
                "cycling" in post-mitotic tissue, and "3 terminal states" over cells whose fate
                entropy was at the maximum the three states allow.

A page may DECLARE an exemption with a reason; the reason is printed with the result, so an
exemption is visible rather than silent.
"""
from __future__ import annotations

import re
from pathlib import Path

#: A page may carry at most this many figures. Above it, a reader stops.
MAX_FIGURES = 12
#: Words in one caption, and in all the prose that is not a caption.
MAX_CAPTION_WORDS = 45
MAX_PROSE_WORDS = 900
#: UniProt-style accessions. A result naming one of these has an unmapped identifier in it.
ACCESSION = re.compile(r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b")
#: What a figure must say to count as comparing the design.
ARM_HINT = re.compile(r"\b(by arm|across the design|per arm|between arms|arm[s]? of the design)\b", re.I)


def _text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _captions(html):
    return [_text(c) for c in re.findall(r"<figcaption[^>]*>(.*?)</figcaption>", html, re.S)]


def check_page(path, *, exempt=()):
    """Every criterion, measured on one rendered page. Returns [(id, ok, detail)]."""
    html = Path(path).read_text(encoding="utf-8")
    txt = _text(html)
    caps = _captions(html)
    figs = re.findall(r"<figure", html)
    # THE PANEL A FIGURE IS, taken from the FILE it shows. Keying this on a `data-fig-id`
    # attribute the reporter does not emit made the criterion pass on a page carrying the
    # same five plots ten times over. A check that CANNOT fail is worse than no check: it
    # reports the very defect it was written for as absent.
    ids = [m.rsplit("/", 1)[-1] for m in re.findall(r'src="([^"]+\.png)"', html)]
    out = []

    def ck(cid, ok, detail=""):
        out.append((cid, bool(ok) or cid in exempt, detail))

    ck("overview", "The cohort" in html or "the cohort" in txt.lower()[:4000],
       "no cohort overview: a reader meets a number before learning what was compared")
    ck("arms", any(ARM_HINT.search(c) for c in caps),
       "no figure compares the design arms")
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    ck("repeats", not dupes, f"figure id repeated: {dupes[:4]}")
    ck("count", len(figs) <= MAX_FIGURES, f"{len(figs)} figures, cap {MAX_FIGURES}")
    long_caps = [c[:60] for c in caps if len(c.split()) > MAX_CAPTION_WORDS]
    ck("captions", not long_caps,
       f"{len(long_caps)} caption(s) over {MAX_CAPTION_WORDS} words")
    prose = len(txt.split()) - sum(len(c.split()) for c in caps)
    ck("prose", prose <= MAX_PROSE_WORDS, f"{prose} words of prose, cap {MAX_PROSE_WORDS}")
    acc = sorted(set(ACCESSION.findall(" ".join(caps))))
    ck("identifiers", not acc, f"unmapped accession(s) in a caption: {acc[:4]}")
    return out


def check_report(report_dir, *, exempt=None):
    """Every page in a rendered report. {page: [(id, ok, detail)]}."""
    exempt = exempt or {}
    d = Path(report_dir)
    res = {}
    for f in sorted(d.glob("*.html")):
        if f.stem == "index":
            continue
        res[f.stem] = check_page(f, exempt=set(exempt.get(f.stem, ())))
    return res


def summarise(res, log=print):
    """Print it, and return True when every page meets every criterion."""
    ok_all = True
    ids = sorted({c for v in res.values() for c, _, _ in v})
    log(f"{'page':<12} " + " ".join(f"{i[:6]:>7}" for i in ids))
    for page, checks in sorted(res.items()):
        by = {c: (o, d) for c, o, d in checks}
        log(f"  {page:<10} " + " ".join(
            f"{('ok' if by[i][0] else 'FAIL'):>7}" for i in ids))
        for i in ids:
            if not by[i][0]:
                ok_all = False
    log("")
    for page, checks in sorted(res.items()):
        for cid, ok, detail in checks:
            if not ok:
                log(f"  {page:<11} {cid:<12} {detail}")
    return ok_all
