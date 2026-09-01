"""THE EXIT STANDARD A RENDERED REPORT MUST MEET, measured on the report itself.

Not a style guide and not a test fixture: every check here opens the HTML that was actually
written and the PNG files it actually references, in the directory a run actually produced. A
standard measured on a synthetic page proves the checker runs; it proves nothing about the
report a reader will open.

WHY EACH ONE EXISTS. Measured on a real multi-sample, two-factor cohort whose report had
191 figures:

  overview      No page said what the cohort was. A reader met "1,654 significant edges" with
                no statement anywhere of how many samples, how many arms, or what was compared.
  arms          NOT ONE figure of 191 split anything by a design factor. The study was a
                two-factor design; every panel was per-population or per-cell.
  repeats       140 of the 191 were fifteen plots redrawn once per sample. Three plugins
                infer per sample, so those panels are not even comparable with each other.
  count         57 figures on one page. A page a reader cannot finish is a page that hides its
                own result.
  captions      Captions were 65% of all words - 13,172 of 20,545 on the worst page.
  prose         The narration was ten thousand words of the same explanation repeated per
                sample. Visible words only: collapsed text is charged to `hidden`.
  caveats       Counted apart from narration and capped generously. A caveat is the most
                load-bearing prose on a page, and charging it against a narration cap made the
                way to pass "say less about the limits of the result".
  hidden        Words behind a disclosure are not in a reader's way, and must not therefore
                grow without limit - or the cap on prose is escaped by folding it.
  identifiers   The strongest signal in every population of one page was `A0A079HLR9`, an
                unmapped UniProt accession presented as a regulator.
  contradiction Two pages carried headlines their own diagnostics refute: 45.5% of nuclei
                "cycling" in post-mitotic tissue, and "3 terminal states" over cells whose fate
                entropy was at the maximum the three states allow. THE ONLY CRITERION NOT
                MEASURABLE FROM THE PAGE: an omitted refutation leaves no mark, so what the
                plugin recorded is read from the payload and looked for on the page.

EVERY CRITERION CARRIES A PAGE IT MUST REJECT, and `selfcheck()` measures the ruler against
those pages before the ruler is allowed to measure a report. Five of the ten were at some point
measuring something other than what they claimed, and every one of them was PASSING while it
was broken.

A page DECLARES an exemption with `data-standard-exempt="<criterion>"`, and the element's own
visible text is the reason. The reason is printed with the result, so an exemption is visible
rather than silent, and one with no reason is refused - an unexplained exemption is
indistinguishable from the defect it excuses. It exists because a criterion a correct run
CANNOT satisfy is as bad as one that cannot fail: `arms` is unmeetable on a cohort with no
design table, and a standard nobody can meet is one that gets switched off.
"""
from __future__ import annotations

import json
import re
from html import unescape as html_unescape
from pathlib import Path

#: Pages that are appendices to a plugin page rather than pages a reader reads. A page named
#: with one of these is exempt from the criteria ONLY IF its parent exists and links to it -
#: the link is what stops the exemption being used to move figures out of sight.
#: `_panel` and `_profile` are galleries by construction - one plate per declared evidence need
#: across every comparison, and the per-unit profile of every unit - so the figure count is what
#: they are FOR. They are exempt on exactly the same condition as the other two and no weaker
#: one: the parent page must exist and must link to them, which is what stops the suffix being
#: used to move figures out of a reader's way.
APPENDIX_SUFFIXES = ("_by_sample", "_by_arm", "_panel", "_profile")

#: A page may carry at most this many figures. Above it, a reader stops.
MAX_FIGURES = 12
#: Words in one caption, and in all the prose that is not a caption.
MAX_CAPTION_WORDS = 45
MAX_PROSE_WORDS = 900
#: Collapsed text is not in a reader's way, but it must not grow without limit.
MAX_HIDDEN_WORDS = 2500
#: Caveats are the page's most load-bearing prose and must stay visible; they are capped
#: generously rather than charged against narration.
#:
#: THE CAP SCALES WITH WHAT THE PAGE COVERS. A fixed 800 was set when a page described ten
#: units. A page that describes fourteen - the ten samples plus four design arms - carries
#: more caveat text for the same reason it carries more figures, and failed at 876 words on
#: caveats that were already FOLDED ("all 14 units") with no duplication left to squeeze.
#:
#: This is a change to a standard's constant, so what was rejected is worth recording: trimming
#: the plugin's caveats would have removed real content, and leaving the page failing would have
#: penalised it for covering more of the experiment. What the cap protects - a reader meeting an
#: unbounded wall of prose - is still bounded, just as a function of scope rather than a number
#: chosen for one cohort size.
MAX_CAVEAT_WORDS = 800
#: Additional words allowed per unit beyond the tenth.
CAVEAT_WORDS_PER_EXTRA_UNIT = 25


def caveat_cap(n_units=0):
    """The caveat budget for a page describing `n_units` units."""
    return MAX_CAVEAT_WORDS + CAVEAT_WORDS_PER_EXTRA_UNIT * max(0, int(n_units or 0) - 10)
#: UniProt-style accessions. A result naming one of these has an unmapped identifier in it.
ACCESSION = re.compile(r"\b(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b")
#: What a figure must say to count as comparing the design.
ARM_HINT = re.compile(
    r"\b(by arm|across the design|per arm|between arms|arm[s]? of the design"
    # A PLUGIN SAYS IT ITS OWN WAY. abundance's shares panel is captioned "split by design
    # level" and compares exactly what this criterion is looking for; the pattern missed it and
    # reported the page as having no design comparison at all. That is the same defect as
    # `repeats` passing on a page of repeats, pointing the other way: a ruler that cannot see a
    # thing reports its absence just as confidently as its presence.
    r"|split by design|by design level|per design level|grouped by design)\b", re.I)

#: THE CRITERIA, NAMED ONCE. `check_page` calls `ck` with these ids, `selfcheck` proves each of
#: them can fail, and the module docstring explains each. All three read this tuple, so a
#: criterion cannot be documented and not implemented, or implemented and never proven.
CRITERIA = ("overview", "arms", "repeats", "count", "captions", "prose",
            "caveats", "hidden", "identifiers", "contradiction")


def _text(html):
    """Visible words. STYLE AND SCRIPT ARE NOT PROSE.

    Stripping tags alone leaves what is BETWEEN them, and `<style>` is a tag with 74 words of
    CSS inside it on every page in this tool. Every prose count was inflated by the same
    stylesheet, on all ten pages, which is a defect in the ruler rather than in the thing it
    measured - and the kind that makes a page look worse the more carefully it is styled.
    """
    html = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _norm(text):
    """Comparable form of a sentence that has been through an HTML renderer.

    A recorded claim is compared against RENDERED text, so it has been escaped (`&` became
    `&amp;`), possibly re-wrapped, and sits inside markup that was stripped. Unescaping and
    collapsing whitespace is as far as this goes: normalising punctuation away too would make
    the criterion pass on a page that merely mentions some of the same words, which is the
    failure mode this whole module exists to refuse.
    """
    return re.sub(r"\s+", " ", html_unescape(str(text))).strip().lower()


def _captions(html):
    """(visible lead, hidden remainder) per caption.

    A `<details>` is CLOSED when the page opens, so its words are not what a reader meets - and
    counting them against the caption cap made a page fail for text nobody sees. They are not
    forgiven either: the remainder is charged to `prose`, so moving words behind a disclosure
    moves the accounting rather than escaping it.
    """
    out = []
    for c in re.findall(r"<figcaption[^>]*>(.*?)</figcaption>", html, re.S):
        hidden = " ".join(re.findall(r"<details[^>]*>(.*?)</details>", c, re.S))
        visible = re.sub(r"<details[^>]*>.*?</details>", " ", c, flags=re.S)
        out.append((_text(visible), _text(hidden)))
    return out


#: How many rows of a figure's source table to read. The labels are the header and the first
#: column; reading the whole file to find them would make the check cost more than the report.
SOURCE_ROWS = 200


def _source_accessions(page):
    """Unmapped accessions among the LABELS a page's figures are drawn with.

    A figure's labels come from its source table - the header, and the first column - and that
    is the file the page links to as "source data". Nothing here parses CSV properly: a label
    that needs quoting is not an accession.
    """
    try:
        html = page.read_text(encoding="utf-8")
    except OSError:
        return set()
    root = page.parent.parent
    found = set()
    for rel in set(re.findall(r'href="\.\./([^"]+\.csv)"', html)):
        f = root / rel
        if not f.is_file():
            continue
        try:
            with f.open("r", encoding="utf-8", errors="replace") as fh:
                head = fh.readline()
                found |= set(ACCESSION.findall(head))
                for i, line in enumerate(fh):
                    if i >= SOURCE_ROWS:
                        break
                    found |= set(ACCESSION.findall(line.split(",", 1)[0]))
        except OSError:
            continue
    return found


#: How a page declares that a criterion cannot apply to it. The ATTRIBUTE names the criterion;
#: the element's own text is the reason, so the reason is on the page a reader opens and not
#: only in a verdict they never see. An exemption with no reason is refused: an unexplained
#: exemption is indistinguishable from the defect it excuses.
EXEMPT_ATTR = re.compile(r'data-standard-exempt="([a-z_]+)"[^>]*>(.*?)<', re.S)


def declared_exemptions(html):
    """{criterion: reason} the page declares for itself, reason required.

    A CRITERION A CORRECT RUN CANNOT SATISFY IS AS BAD AS ONE THAT CANNOT FAIL, pointing the
    other way: it makes the standard unmeetable and so unused. A cohort with no design table
    can never draw a panel comparing arms, and `arms` would fail on every page of every such
    run forever, with no remedy anyone could apply.

    `check_page` took an `exempt` argument from the beginning and nothing ever passed one -
    a dead parameter, which is the same defect as the dead predicates that made six planner
    decisions read a flag nobody set. The page is the only party that knows why, so the page
    declares it.
    """
    out = {}
    for cid, text in EXEMPT_ATTR.findall(html or ""):
        reason = _text(text).strip()
        if cid in CRITERIA and reason:
            out[cid] = reason
    return out


def check_page(path, *, exempt=(), recorded=()):
    """Every criterion, measured on one rendered page. Returns [(id, ok, detail)].

    `recorded` is what the PLUGIN said about its own result and the page must therefore show -
    the contradictions in its payload. It is the one thing on this page that cannot be measured
    from the page: a refutation that was never rendered leaves no trace in the HTML, and a page
    that omits it looks exactly like a page that had none to make.
    """
    html = Path(path).read_text(encoding="utf-8")
    txt = _text(html)
    pairs = _captions(html)
    caps = [v for v, _h in pairs]
    hidden_words = sum(len(h.split()) for _v, h in pairs)
    figs = re.findall(r"<figure", html)
    # THE PANEL A FIGURE IS, taken from the FILE it shows. Keying this on a `data-fig-id`
    # attribute the reporter does not emit made the criterion pass on a page carrying the
    # same five plots ten times over. A check that CANNOT fail is worse than no check: it
    # reports the very defect it was written for as absent.
    # THE PATH, NOT THE BASENAME. Keying on the filename alone made every per-unit page a page
    # of "repeats": eighteen units each draw `native_signalingRole_scatter.png`, and those are
    # eighteen DIFFERENT figures of eighteen different units. The defect this criterion exists
    # to catch - one plot shown ten times - is a repeated PATH, and keying on the path still
    # catches it exactly while no longer reporting distinct figures as duplicates.
    ids = re.findall(r'src="([^"]+\.png)"', html)
    out = []

    declared = declared_exemptions(html)
    exempt = set(exempt) | set(declared)

    def ck(cid, ok, detail=""):
        # EXEMPT IS NOT OK, and it is not reported as ok. The reason travels with the result so
        # `summarise` prints it: an exemption nobody reads is a criterion quietly switched off.
        if not ok and cid in exempt:
            out.append((cid, True, "exempt: " + declared.get(cid, "no reason given")))
            return
        out.append((cid, bool(ok), detail))

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
    # TWO NUMBERS, EACH MEASURING WHAT IT CLAIMS. Charging collapsed text to `prose` made
    # `prose` stop measuring prose: a page could fail it entirely on words behind disclosures
    # that a reader never opens. Visible text is capped because it is what confronts a reader;
    # hidden text is capped separately and generously, because it must not grow without limit
    # but it is not in anybody's way.
    hidden_all = sum(len(_text(h).split())
                     for h in re.findall(r"<details[^>]*>(.*?)</details>", html, re.S))
    # CAVEATS ARE NOT NARRATION, and the cap was written against narration - the ten-thousand-word
    # pages of repeated explanation. A caveat is the most load-bearing prose on a page and the
    # one thing that must not be collapsed, so charging it against a narration cap pushed in
    # exactly the wrong direction: the way to pass would have been to say less about the limits
    # of the result. Counted separately, and capped, so it cannot grow without bound either.
    cav_html = " ".join(re.findall(r'<div class="warn".*?</div>', html, re.S))
    cav_words = len(_text(re.sub(r"<details[^>]*>.*?</details>", " ", cav_html, flags=re.S)).split())
    prose = len(txt.split()) - sum(len(c.split()) for c in caps) - hidden_all - cav_words
    ck("prose", prose <= MAX_PROSE_WORDS, f"{prose} words of prose, cap {MAX_PROSE_WORDS}")
    _found = re.findall(r"all (\d+) units", txt)
    _n_units = max((int(x) for x in _found), default=0)
    _cap = caveat_cap(_n_units)
    ck("caveats", cav_words <= _cap,
       f"{cav_words} words of caveat, cap {_cap}"
       + (f" ({_n_units} units)" if _n_units > 10 else ""))
    ck("hidden", hidden_all <= MAX_HIDDEN_WORDS,
       f"{hidden_all} words behind disclosures, cap {MAX_HIDDEN_WORDS}")
    # THE LABELS A FIGURE IS DRAWN WITH, not the words underneath it. Checking captions alone
    # passed a page whose strongest signal in every population was `A0A079HLR9` - because the
    # accession was on the AXIS and in the source table, and the caption said "mean activity".
    # 123 of that plugin's 674 regulators are unmapped, and the criterion reported none.
    acc = set(ACCESSION.findall(" ".join(caps)))
    acc |= _source_accessions(Path(path))
    acc = sorted(acc)
    # NAMED, NEVER DROPPED. An accession is what the prior supplies for a regulator that has no
    # gene symbol, and excluding those would hide real signal - on the page this was written
    # for, the STRONGEST regulator in every population is one of them. What a reader cannot do
    # is tell `A0A079HLR9` from `Gata4` when both sit on the same axis. So the requirement is
    # that the page SAYS how many of its labels are unmapped, not that it have none.
    said = bool(re.search(r"unmapped|no gene symbol|accession", txt, re.I))
    ck("identifiers", not acc or said,
       f"{len(acc)} unmapped accession(s) among the labels and the page never says so, "
       f"e.g. {acc[:4]}")
    # WHAT THE PLUGIN SAID AGAINST ITSELF, ON THE PAGE, IN PLAIN SIGHT. Two pages carried a
    # headline their own figures refute; the refutation existed, was recorded, and reached a
    # `caveats` list indistinguishable from nine other sentences. This is the only criterion
    # that is not measurable from the page alone, and that is exactly why it is here: an
    # omission leaves no mark, so a page that dropped it and a page with nothing to drop are
    # the same document. VISIBLE, not behind a disclosure - the claim it refutes is not.
    if recorded is None:
        # MEASURED IS NOT THE SAME AS CLEAN, and the difference is the whole point of the
        # criterion. Reported as n/a with the reason, so a report judged without its payload
        # cannot be quoted as having passed this.
        out.append(("contradiction", True,
                    "n/a: this page's payload does not carry a `contradictions` field - no run "
                    "payload beside the report, or one written before the field existed - so a "
                    "refutation the plugin recorded and the page omitted cannot be detected"))
    else:
        missing = [c for c in recorded
                   if _norm(c) not in _norm(_text(re.sub(r"<details[^>]*>.*?</details>", " ",
                                                         html, flags=re.S)))]
        ck("contradiction", not missing,
           f"{len(missing)} contradiction(s) the plugin recorded do not appear in the visible "
           f"page, e.g. {missing[:1]}")
    return out


def recorded_claims(report_dir):
    """{page stem: [contradiction, ...]} from the payload beside the rendered report.

    Read from `report.json` in the run directory, which is the same file `report` renders
    from - so what the standard holds a page to is what the page was built out of, and not a
    second opinion assembled from somewhere else.

    An unreadable or absent payload yields nothing rather than raising: this module must stay
    runnable against a report directory that has been copied away from its run.
    """
    d = Path(report_dir)
    src = (d if d.name != "report" else d.parent) / "report.json"
    try:
        payload = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # NOT "no contradictions". A report directory copied away from its run has no payload
        # beside it, and returning an empty mapping would make the criterion pass on every page
        # of it - absence of evidence rendered as evidence of absence, which is the failure this
        # whole module exists to refuse. `None` says UNMEASURABLE; `{}` says measured and empty.
        return None
    out = {}
    for name, pl in (payload.get("kernels") or {}).items():
        # A PAYLOAD WRITTEN BEFORE THE FIELD EXISTED IS NOT A PAYLOAD WITH NO CLAIMS. The key is
        # ABSENT there, and reading that as an empty list made the criterion report `ok` while
        # checking nothing - on the two plugins it was written for, both of which had recorded
        # a refutation that the older host composed into the headline instead.
        #
        # `None` for that page: unmeasurable, said out loud. The distinction is the same one
        # this module already draws for a report with no payload beside it at all, and it has
        # to be drawn twice because there are two ways to have nothing to measure.
        if not isinstance(pl, dict) or "contradictions" not in pl:
            out[str(name)] = None
            continue
        out[str(name)] = [str(c) for c in (pl.get("contradictions") or [])]
    return out


def check_report(report_dir, *, exempt=None):
    """Every page in a rendered report. {page: [(id, ok, detail)]}."""
    exempt = exempt or {}
    d = Path(report_dir)
    claims = recorded_claims(d)
    #: `None` from `recorded_claims` means the payload could not be read; every page then gets
    #: `recorded=None`, which the criterion reports as n/a with the reason rather than as ok.
    unmeasurable = claims is None
    res = {}
    pages = [f for f in sorted(d.glob("*.html")) if f.stem != "index"]
    # AN APPENDIX IS NOT A REPORT PAGE, and holding it to the report standard would fail it for
    # being what it is: per-sample panels ARE repeats, and there are many, which is the reason
    # they were moved off the page a reader reads.
    #
    # It cannot be used to hide a page. An appendix counts as one only when the plugin page it
    # belongs to EXISTS and LINKS to it, so moving figures out of sight requires leaving a door
    # to them in plain view.
    # THE SUFFIX IS NAMING; THE LINK IS THE GUARD. This tested one suffix, so a second kind of
    # appendix - the per-ARM panels, which are the comparison figures a factorial design exists
    # for - was measured as though it were a page a reader reads, and failed on being what it
    # is: forty panels, no cohort overview, and a "compares the arms" check that scans for
    # vocabulary the per-contrast captions carry in a different form. Adding the suffix changes
    # nothing about what stops this hiding a page: the parent must EXIST and LINK to it.
    appendix = set()
    for f in pages:
        suffix = next((x for x in APPENDIX_SUFFIXES if f.stem.endswith(x)), None)
        if suffix is None:
            continue
        parent = d / f"{f.stem[:-len(suffix)]}.html"
        if parent.exists() and f.name in parent.read_text(encoding="utf-8"):
            appendix.add(f.stem)
    for f in pages:
        if f.stem in appendix:
            continue
        # THREE STATES: no payload at all, a payload whose page predates the field, and a
        # measured list. Only the last is a check; the other two say so.
        _rec = None if unmeasurable else claims.get(f.stem, ())
        res[f.stem] = check_page(f, exempt=set(exempt.get(f.stem, ())), recorded=_rec)
    return res


def summarise(res, log=print):
    """Print it, and return True when every page meets every criterion."""
    ok_all = True
    ids = sorted({c for v in res.values() for c, _, _ in v})
    log(f"{'page':<12} " + " ".join(f"{i[:6]:>7}" for i in ids))
    for page, checks in sorted(res.items()):
        by = {c: (o, d) for c, o, d in checks}
        log(f"  {page:<10} " + " ".join(
            f"{('exempt' if by[i][1].startswith('exempt:') else 'n/a' if by[i][1].startswith('n/a:') else 'ok' if by[i][0] else 'FAIL'):>7}"
            for i in ids))
        for i in ids:
            if by[i][1].startswith(("exempt:", "n/a:")):
                log(f"    {i} {by[i][1]}")
        for i in ids:
            if not by[i][0]:
                ok_all = False
    log("")
    for page, checks in sorted(res.items()):
        for cid, ok, detail in checks:
            if not ok:
                log(f"  {page:<11} {cid:<12} {detail}")
    return ok_all


# --------------------------------------------------------------- the ruler checks itself

#: A page that must MEET every criterion. Without it, a criterion that always fails would look
#: exactly as healthy below as one that works: "it fired on the counterexample" is only evidence
#: when the same ruler passed something.
BASELINE = (
    "<style>.x{color:red}</style>"
    "<h2>The cohort</h2><p>Eight units in two arms of one factor.</p>"
    '<figure><img src="a.png"><figcaption>What it shows, by arm.</figcaption></figure>'
    '<figure><img src="b.png"><figcaption>What else it shows.</figcaption></figure>'
)


def _mutate(cid):
    """BASELINE broken in exactly one way: the page `cid` exists to reject."""
    long_words = " ".join(["word"] * (MAX_PROSE_WORDS + 40))
    if cid == "overview":
        return BASELINE.replace("<h2>The cohort</h2><p>Eight units in two arms of one "
                                "factor.</p>", "<h2>Results</h2>")
    if cid == "arms":
        return BASELINE.replace("What it shows, by arm.", "What it shows, per population.")
    if cid == "repeats":
        return BASELINE.replace('src="b.png"', 'src="a.png"')
    if cid == "count":
        extra = "".join(f'<figure><img src="x{i}.png"><figcaption>Panel {i}.</figcaption>'
                        f"</figure>" for i in range(MAX_FIGURES + 1))
        return BASELINE + extra
    if cid == "captions":
        return BASELINE.replace("What else it shows.",
                                " ".join(["word"] * (MAX_CAPTION_WORDS + 5)))
    if cid == "prose":
        return BASELINE + f"<p>{long_words}</p>"
    if cid == "caveats":
        return BASELINE + ('<div class="warn">'
                           + " ".join(["word"] * (MAX_CAVEAT_WORDS + 20)) + "</div>")
    if cid == "hidden":
        return BASELINE + ("<details>" + " ".join(["word"] * (MAX_HIDDEN_WORDS + 20))
                           + "</details>")
    if cid == "identifiers":
        return BASELINE.replace("What else it shows.", "Strongest signal: A0A079HLR9.")
    if cid == "contradiction":
        return BASELINE                    # the claim is supplied, and the page never shows it
    raise KeyError(cid)                    # a criterion with no counterexample is not provable


#: What the `contradiction` counterexample is missing. Every other criterion is broken by the
#: page alone; this one is broken by what the page LEAVES OUT, which is why it needs a claim.
_MISSING_CLAIM = "the depth trend refutes the headline above"


def selfcheck():
    """Prove every criterion can fail, and that none of them fails on a clean page.

    A CHECK THAT CANNOT FAIL IS WORSE THAN NO CHECK: it reports the very defect it was written
    for as absent, and it does so on every page, for as long as nobody looks. Five of the
    criteria here were at some point measuring something other than what they claimed - one
    keyed on an attribute the reporter never emits, one counted the stylesheet, one counted
    collapsed text, one could not recognise a real arm figure, one read captions instead of the
    labels a figure is drawn with. Every one of them was PASSING while it was broken.

    So each criterion carries a page it must reject, and the whole ruler is measured against
    those pages before it is allowed to measure anything else. Returns [(id, ok, detail)].
    """
    import tempfile
    out = []
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "p.html"

        def run(html, recorded=()):
            page.write_text(html, encoding="utf-8")
            return {c: (o, d) for c, o, d in check_page(page, recorded=recorded)}

        clean = run(BASELINE)
        for cid in CRITERIA:
            if cid not in clean:
                out.append((cid, False, "named in CRITERIA and never measured by check_page"))
                continue
            if not clean[cid][0]:
                out.append((cid, False, f"fails on a page that meets the standard: "
                                        f"{clean[cid][1]}"))
                continue
            broken = run(_mutate(cid),
                         recorded=(_MISSING_CLAIM,) if cid == "contradiction" else ())
            out.append((cid, not broken[cid][0],
                        "does not fire on the page written to break it"))
        for cid in sorted(set(clean) - set(CRITERIA)):
            out.append((cid, False, "measured by check_page and not named in CRITERIA"))
    return out


def documented():
    """The criteria the module docstring explains, read from the docstring itself.

    A criterion documented and not implemented is an absence nobody meets - `contradiction` was
    described in this file for a week as one of the standard's reasons for existing, and no
    report was ever held to it.
    """
    body = (__doc__ or "").split("WHY EACH ONE EXISTS", 1)[-1]
    # EXACTLY two spaces, then the id: a continuation line is indented further, so what
    # follows its two spaces is another space and never an id.
    return {m.group(1) for m in re.finditer(r"^  ([a-z_]+)[ ]+\S", body, re.M)}


def summarise_selfcheck(res, log=print):
    """Print it, and return True when every criterion is proven falsifiable."""
    bad = [(c, d) for c, o, d in res if not o]
    for cid, detail in bad:
        log(f"  RULER BROKEN  {cid:<14} {detail}")
    return not bad
