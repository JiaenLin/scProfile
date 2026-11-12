"""A plugin's source, and a check that it exists (harness RULES item 18, ROUTE R45).

A SOURCE IS A DOI, AND THE DOI'S OWN RECORD SAYS WHAT IT IS. `wraps.cite` is free text a reader
cannot check: an author and a year can be misremembered, and a reference that was never published
reads exactly like one that was. So a plugin declares the paper its method comes from as a DOI
(`wraps.doi`, a string, or a list for several papers), and beside it the title and the year the
DOI's registry record gives (`wraps.doi_record`, keyed by DOI). Offline, the form is checked; with
`scprofile source <plugin> --resolve` each DOI is resolved at doi.org and its record's title and
year are compared with what the plugin recorded: a DOI that does not resolve, or whose record
says another title or year, fails by name. Nothing but the DOI is sent.

A PIN IS ONE VERSION, AND IT IS THE ONE THAT IS BUILT. `wraps.version` names the exact version of
the wrapped tool, never a range; where this repository ships a lock holding the plugin, the lock's
line for the tool must be that version, so the pin cannot drift from what an environment really
gets. An R tool installed from a remote at a commit (`owner/Pkg@<sha>` in `requires.r`) is pinned
by that commit.

What this does not establish: that the paper describes what the code does. One cited claim per
plugin is read against its source by a person (RULES item 18); a resolver cannot.
"""
import json
import re
from pathlib import Path

#: A DOI as the registries write it: the directory indicator `10.`, a registrant code, a slash and
#: a suffix with no whitespace. A URL form (`https://doi.org/...`) is refused, not stripped, so the
#: field holds one spelling.
DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s]+$")
#: One version: digits and dots, an optional pre/post/dev suffix. No operator, no wildcard.
VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}((a|b|rc|\.post|\.dev)\d+)?$")
_COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
RESOLVER = "https://doi.org/"


def dois(spec):
    """The DOIs a plugin declares, as written (a string or a list), or [] with none."""
    w = spec.get("wraps") if isinstance(spec.get("wraps"), dict) else {}
    v = w.get("doi")
    if v is None:
        return []
    return [v] if isinstance(v, str) else (list(v) if isinstance(v, (list, tuple)) else [v])


def _norm(name):
    return re.sub(r"[-_.]+", "-", str(name)).lower()


def lock_pin(root, plugin, tool):
    """(version, lock file) the shipped lock holding `plugin` pins `tool` at, or (None, why)."""
    for lk in sorted(Path(root).glob("setup/locks/*/*.txt")):
        text = lk.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^# members:(.*)$", text, re.M)
        if not m or plugin not in m.group(1).split():
            continue
        for line in text.splitlines():
            p = re.match(r"^([A-Za-z0-9_.\-]+)==(\S+)", line)
            if p and _norm(p.group(1)) == _norm(tool):
                return p.group(2), lk.relative_to(root).as_posix()
        return None, f"{lk.relative_to(root).as_posix()} holds {plugin} and no line for {tool}"
    return None, f"no shipped lock holds {plugin}"


def r_pin(spec, tool):
    """The commit (or exact `==` version) `requires.r` installs `tool` from, or None."""
    req = spec.get("requires") if isinstance(spec.get("requires"), dict) else {}
    for e in req.get("r") or []:
        s = str(e)
        if "@" in s:
            left, ref = s.rsplit("@", 1)
            if _norm(left.rsplit("/", 1)[-1]) == _norm(tool) and _COMMIT.match(ref):
                return ref
        elif "==" in s:
            left, ref = s.split("==", 1)
            if _norm(left.rsplit("/", 1)[-1]) == _norm(tool) and VERSION_RE.match(ref):
                return ref
    return None


def findings(spec, plugin, root):
    """[(level, message)]: the source and the pin, offline. An absent source is a WARN (the
    plugin cannot be refused for it - `run` validates first); a declared one that is malformed,
    or a pin that is a range or is not what the lock builds, is an ERROR naming the field."""
    out = []
    w = spec.get("wraps") if isinstance(spec.get("wraps"), dict) else None
    if not w:
        return out
    tool = w.get("tool")
    ds = dois(spec)
    rec = w.get("doi_record")
    if not ds:
        out.append(("WARN", "no source: `wraps.doi` is not declared. A plugin names the paper its "
                            "method comes from by DOI, with the title and year its record gives "
                            "(`wraps.doi_record`); `scprofile source <plugin> --resolve` checks it"))
    else:
        seen = []
        for d in ds:
            if not isinstance(d, str) or not DOI_RE.match(d):
                out.append(("ERROR", f"`wraps.doi` {d!r} is not a DOI: write the bare DOI, "
                                     f"`10.<registrant>/<suffix>`, with no URL and no whitespace"))
                continue
            if d.lower() in seen:
                out.append(("ERROR", f"`wraps.doi` names {d!r} twice"))
            seen.append(d.lower())
        if not isinstance(rec, dict):
            out.append(("ERROR", "`wraps.doi_record` is missing: each DOI needs the title and "
                                 "year its own record gives, {doi: {\"title\": ..., \"year\": ...}}"))
        else:
            keys = {str(k).lower(): k for k in rec}
            for d in seen:
                if d not in keys:
                    out.append(("ERROR", f"`wraps.doi_record` has no entry for {d!r}"))
                    continue
                e = rec[keys[d]]
                if not isinstance(e, dict) or set(e) != {"title", "year"}:
                    out.append(("ERROR", f"`wraps.doi_record[{keys[d]!r}]` must hold exactly "
                                         f"`title` and `year`"))
                    continue
                if not isinstance(e["title"], str) or not e["title"].strip() \
                        or "\n" in e["title"]:
                    out.append(("ERROR", f"`wraps.doi_record[{keys[d]!r}].title` must be the "
                                         f"record's title, one line of text"))
                if type(e["year"]) is not int or not 1900 <= e["year"] <= 2100:
                    out.append(("ERROR", f"`wraps.doi_record[{keys[d]!r}].year` must be the "
                                         f"record's year, an integer"))
            for k in keys:
                if k not in seen:
                    out.append(("ERROR", f"`wraps.doi_record` holds {keys[k]!r}, which "
                                         f"`wraps.doi` does not name"))
    v = w.get("version")
    rp = r_pin(spec, tool) if tool else None
    if v is None and rp is None:
        out.append(("WARN", f"no exact pin of {tool}: declare `wraps.version`, the one version "
                            f"the environment builds (a range in `requires` says what is "
                            f"tolerated, not what ran)"))
    elif v is not None:
        if not isinstance(v, str) or not VERSION_RE.match(v):
            out.append(("ERROR", f"`wraps.version` {v!r} is not one exact version"))
        elif root is not None:
            got, where = lock_pin(root, plugin, tool)
            if got is not None and got != v:
                out.append(("ERROR", f"`wraps.version` says {tool} {v} and {where} builds "
                                     f"{tool} {got}: the pin is not what the environment gets"))
    return out


def _fetch(doi, timeout=30):
    """The registry's record for one DOI, as CSL JSON, from doi.org. Sends the DOI and nothing
    else (a generic client name, no contact address)."""
    import urllib.request
    req = urllib.request.Request(RESOLVER + doi, headers={
        "Accept": "application/vnd.citationstyles.csl+json",
        "User-Agent": "scprofile-source-check"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _title(t):
    t = t[0] if isinstance(t, list) and t else t
    return re.sub(r"\s+", " ", str(t or "")).strip()


def record_of(csl):
    """(title, year) of a CSL record: its title with runs of whitespace made one space, and the
    first date part of `issued` - the year the registry itself gives."""
    parts = ((csl.get("issued") or {}).get("date-parts") or [[None]])[0] or [None]
    return _title(csl.get("title")), parts[0]


def resolve(spec, fetch=None):
    """[(ok, doi, message)]: each declared DOI resolved and compared with its recorded title and
    year. `fetch(doi)` returns the CSL record or raises; the default asks doi.org."""
    fetch = fetch or _fetch
    w = spec.get("wraps") if isinstance(spec.get("wraps"), dict) else {}
    rec = {str(k).lower(): v for k, v in (w.get("doi_record") or {}).items()} \
        if isinstance(w.get("doi_record"), dict) else {}
    out = []
    for d in dois(spec):
        mine = rec.get(str(d).lower()) or {}
        try:
            csl = fetch(d)
        except Exception as e:                                            # noqa: BLE001
            out.append((False, d, f"{d} does not resolve: {type(e).__name__}: {e}"))
            continue
        title, year = record_of(csl if isinstance(csl, dict) else {})
        want_t = _title(mine.get("title"))
        if not title:
            out.append((False, d, f"{d} resolved to a record with no title"))
        elif title != want_t:
            out.append((False, d, f"{d}: the record's title is {title!r}; the plugin records "
                                  f"{want_t!r}"))
        elif year != mine.get("year"):
            out.append((False, d, f"{d}: the record's year is {year}; the plugin records "
                                  f"{mine.get('year')}"))
        else:
            out.append((True, d, f"{d}: {title!r} ({year}), as recorded"))
    return out
