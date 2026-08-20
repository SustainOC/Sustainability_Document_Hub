#!/usr/bin/env python3
"""
Build catalogue.json / catalogue.csv for the OC Sustainability Document Hub.

Input : manifest_all.csv  (392 rows, produced by the peer-library build)
        files_present.csv  (optional; relative paths actually in the repos)
Output: catalogue.json, catalogue.csv

Run:  python tools/build_catalogue.py manifest_all.csv [files_present.csv]
"""
import csv, json, re, sys, unicodedata
from collections import OrderedDict
from urllib.parse import quote

# ---------------------------------------------------------------- configuration

# Which published site holds which top-level folder.
# Collapse to a single entry here if the library is ever merged into one repo.
SOURCES = OrderedDict([
    ("docs",  {"base": "https://sustainoc.github.io/Docs/",
               "folders": ["01_UBC-Vancouver", "02_UBC-Okanagan"]}),
    ("docs2", {"base": "https://sustainoc.github.io/Docs2/",
               "folders": ["03_UVic", "04_SFU", "05_TRU", "06_UFV",
                           "07_BC-College-Sector", "08_Sector-and-Government",
                           "09_Labour-Market-Research", "10_OC_Competitors"]}),
])

# Public-facing labels for the top-level folders. Folder names on disk stay as
# they are; only the label changes, so no URLs break.
GROUP_LABELS = {
    "01_UBC-Vancouver":        "UBC Vancouver",
    "02_UBC-Okanagan":         "UBC Okanagan",
    "03_UVic":                 "UVic",
    "04_SFU":                  "SFU",
    "05_TRU":                  "TRU",
    "06_UFV":                  "UFV",
    "07_BC-College-Sector":    "BC College Sector",
    "08_Sector-and-Government": "Sector and Government",
    "09_Labour-Market-Research": "Labour Market Research",
    "10_OC_Competitors":       "Comparator Institutions",
}

# The four focus areas and thirteen impact areas, verbatim from
# 'Sust Plan Framework.xlsx'. Do not edit without changing the framework.
FRAMEWORK = OrderedDict([
    ("Planning and Administration", ["Policy / Planning",
                                     "Organizational Structure",
                                     "Investment"]),
    ("Engagement",                  ["Training",
                                     "Performance Measurement",
                                     "Communications"]),
    ("Operations",                  ["UNSDG's",
                                     "Infrastructure (Energy/Water)",
                                     "Supply Chain",
                                     "Transportation",
                                     "Carbon Zero"]),
    ("Academics",                   ["Curriculum",
                                     "Applied Research"]),
])
IMPACT_TO_FOCUS = {ia: fa for fa, ias in FRAMEWORK.items() for ia in ias}

# Free-text tags in the manifest mapped onto the canonical thirteen.
IMPACT_ALIASES = {
    "policy/planning": "Policy / Planning",
    "planning/policy": "Policy / Planning",
    "policy / planning": "Policy / Planning",
    "organizational structure": "Organizational Structure",
    "investment": "Investment",
    "training": "Training",
    "performance measurement": "Performance Measurement",
    "communications": "Communications",
    "unsdgs": "UNSDG's",
    "unsdg's": "UNSDG's",
    "infrastructure": "Infrastructure (Energy/Water)",
    "infrastructure (energy)": "Infrastructure (Energy/Water)",
    "infrastructure (water)": "Infrastructure (Energy/Water)",
    "infrastructure (energy/water)": "Infrastructure (Energy/Water)",
    "supply chain": "Supply Chain",
    "transportation": "Transportation",
    "carbon zero": "Carbon Zero",
    "curriculum": "Curriculum",
    "applied research": "Applied Research",
}

# Real tags that sit outside the thirteen. Kept as a separate facet rather than
# forced into the framework or discarded.
LENS_ALIASES = {
    "climate resilience": "Climate Resilience",
    "indigenous relationality": "Indigenous relationality",
    "trades for the transition": "Trades for the Transition",
}

# Tags meaning "relevant across the whole framework".
CROSSCUT = {"all 4 focus areas", "all four focus areas", "all 13 impact areas",
            "all thirteen impact areas", "all areas (risk component)",
            "all areas", "all focus areas"}

# Raw doc_type values in the manifest are too granular to filter on (74 distinct
# values). Each is kept for display; this maps it to one of ten classes used by
# the facet. Anything unmapped is reported as a warning rather than silently binned.
DOC_CLASSES = OrderedDict([
    ("Plans and strategies", [
        "plan", "strategy", "strategic plan", "academic plan", "master plan",
        "roadmap", "vision", "framework", "charter", "plan (in progress)",
        "plan in development", "plan annex", "semp",
        "integrated rainwater management plan", "utility corridor plan",
        "plan/dashboard", "statement", "climate emergency"]),
    ("Statutory and climate reporting", [
        "ccar", "cnar", "statutory report", "accountability report",
        "ghg inventory", "tcfd disclosure", "disclosure", "compliance",
        "regulation"]),
    ("STARS", ["stars"]),
    ("Reports and progress updates", [
        "report", "annual sustainability report", "report on sustainability",
        "cap progress report", "progress review", "update", "un sdg snapshot",
        "comms"]),
    ("Audits and assessments", [
        "audit", "waste audit", "energy assessment", "assessment",
        "level 1 energy study", "sustainability literacy assessment",
        "methodology"]),
    ("Studies, surveys and data", [
        "study", "research", "applied research", "case study", "survey",
        "traffic survey", "transportation status report", "dataset",
        "database"]),
    ("Dashboards and tools", [
        "dashboard", "tool", "web tool", "toolkit", "tool hub", "web page"]),
    ("Policy and governance", [
        "policy", "governance", "agreement", "policy/tool"]),
    ("Curriculum and programs", [
        "curriculum", "curriculum inventory", "oer curriculum", "program",
        "program lead", "guide"]),
    ("Projects and announcements", [
        "capital project", "project", "news", "infrastructure",
        "funding program", "contact"]),
])
DOC_CLASS_OF = {v: k for k, vs in DOC_CLASSES.items() for v in vs}

FILENAME_RE = re.compile(
    r"^(?P<year>\d{4}(?:-\d{4})?|nd|current|ongoing)_(?P<inst>[^_]+)_(?P<title>.+)\.(?P<ext>pdf|url)$",
    re.I)

# ---------------------------------------------------------------- helpers

# --------------------------------------------------------------------------
# RECONCILIATION FIXES
# The library on disk drifted from the manifest after the manifest was written.
# These tables record the drift explicitly rather than editing the manifest, so
# the original stays auditable. Verified against files_present.csv 2026-08-20.
# --------------------------------------------------------------------------

# Five institutions were moved out of the BC college sector folder into the
# comparator folder. Same files, new home.
FOLDER_MOVES = [
    ("07_BC-College-Sector/Camosun-College/",
     "10_OC_Competitors/Camosun-College/"),
    ("07_BC-College-Sector/College-of-the-Rockies/",
     "10_OC_Competitors/College-of-the-Rockies/"),
    ("07_BC-College-Sector/Douglas-College/",
     "10_OC_Competitors/Douglas-College/"),
    ("07_BC-College-Sector/Langara-College/",
     "10_OC_Competitors/Langara-College/"),
    ("07_BC-College-Sector/Vancouver-Community-College/",
     "10_OC_Competitors/Vancouver-Community-College/"),
]

# Individual files renamed or refiled on disk. Only high-confidence matches are
# listed: same document title, differing only in year prefix, filing folder, or
# an abbreviated filename. Anything ambiguous is left to report as a gap.
PATH_FIXES = {
    # Refiled from Plans-and-Strategies to Governance-and-Policy, year corrected.
    "01_UBC-Vancouver/01_Plans-and-Strategies/2021_UBCV_Wellbeing-Strategic-Framework-Roadmap-Dashboard.pdf":
        "01_UBC-Vancouver/08_Governance-and-Policy/2023_UBCV_Wellbeing-Strategic-Framework-Roadmap.pdf",
    # Filename shortened on save.
    "09_Labour-Market-Research/07_Curriculum-and-Research/2026_Research_The-Demand-for-Green-Skills-and-the-Impact-on-Apprentices-Future-Skills-Centre.pdf":
        "09_Labour-Market-Research/07_Curriculum-and-Research/2026_Research_Demand-for-Green-Skills-Apprentices-Future-Skills-Centre.pdf",
}

def apply_fixes(folder, filename):
    """Return (folder, filename) as they exist on disk."""
    rel = folder.strip("/") + "/" + filename
    for old, new in FOLDER_MOVES:
        if rel.startswith(old):
            rel = new + rel[len(old):]
            break
    rel = PATH_FIXES.get(rel, rel)
    head, _, tail = rel.rpartition("/")
    return head, tail

def group_of(folder):
    return folder.split("/")[0]

def source_of(folder):
    top = group_of(folder)
    for key, cfg in SOURCES.items():
        if top in cfg["folders"]:
            return key
    return None

def make_title(filename):
    m = FILENAME_RE.match(filename)
    if not m:
        return re.sub(r"\.(pdf|url)$", "", filename, flags=re.I).replace("-", " ").strip()
    t = m.group("title").replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

CURRENT_YEAR = 2026   # "Current"/"Ongoing" records sort alongside this year

ONGOING_WORDS = ("current", "ongoing", "recent", "live", "active")
UNDATED_WORDS = ("n.d.", "nd", "n/a", "unknown", "")

def is_ongoing(raw):
    return (raw or "").strip().lower() in ONGOING_WORDS

def sort_year(raw):
    """Numeric year for sorting. Ongoing items rank with the current year, not
    above everything; undated items sort last."""
    if not raw:
        return 0
    m = re.findall(r"\d{4}", raw)
    if m:
        # first year in the string is the publication year; "2021 (to 2040)"
        # and "2024-2030" are horizons, not publication dates.
        return int(m[0])
    if is_ongoing(raw):
        return CURRENT_YEAR
    return 0

def display_year(raw):
    raw = (raw or "").strip()
    if raw.lower() in UNDATED_WORDS:
        return "Undated"
    return raw

def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def split_tags(raw):
    return [t.strip() for t in re.split(r"[;,]", raw or "") if t.strip()]

def encode_path(path):
    return "/".join(quote(seg) for seg in path.split("/"))

# ---------------------------------------------------------------- build


def load_oc_seed(path):
    """
    Okanagan College's own documents. These are NOT mirrored to a public repo.
    Each record carries an access classification and, where one exists, a link
    that resolves for signed-in OC staff (SharePoint). Restricted records
    deliberately carry no link.
    """
    out = []
    try:
        fh = open(path, encoding="utf-8-sig", newline="")
    except FileNotFoundError:
        return out
    with fh:
        for r in csv.DictReader(fh):
            access = clean(r.get("access")) or "Internal"
            url    = clean(r.get("url"))
            out.append({
                "id":          clean(r["id"]),
                "collection":  "oc",
                "title":       clean(r["title"]),
                "institution": "Okanagan College",
                "group":       "Okanagan College",
                "category":    clean(r["category"]),
                "docClass":    DOC_CLASS_OF.get(clean(r["doc_type"]).lower(), "Other"),
                "docType":     clean(r["doc_type"]),
                "yearLabel":   display_year(r["year"]),
                "yearSort":    sort_year(r["year"]),
                "ongoing":     is_ongoing(r["year"]),
                "kind":        "link" if url else "record",
                "priority":    False,
                "focusAreas":  [], "impactAreas": [], "lenses": [],
                "crossCutting": False,
                "verification": "Held by the SustainOC team",
                "summary":     clean(r.get("note")),
                "ocUse":       "",
                "sourceUrl":   url,
                "path":        None, "repo": None, "fileUrl": None,
                "hosted":      False,
                "access":      access,
                "openUrl":     url or None,
                "openTarget":  "source" if url else "none",
            })
    return out

def build(manifest_path, present_path=None):
    with open(manifest_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    present = None
    if present_path:
        with open(present_path, encoding="utf-8-sig", newline="") as fh:
            present = {}
            for r in csv.DictReader(fh):
                p = (r.get("path") or r.get("Path") or r.get("FullName") or "")
                p = p.strip().replace("\\", "/")
                # NB: lstrip("./") would eat the leading dot of a dotfile.
                while p.startswith("./"):
                    p = p[2:]
                # Accept repo-relative paths or full paths from any tool: the
                # library path always begins at a "NN_Name/" folder.
                m = re.search(r"(?:^|/)(\d{2}_[^/]+/.*)$", p)
                if m:
                    p = m.group(1)
                if p:
                    present[p] = clean(r.get("repo"))

    records, warnings = [], []
    for r in rows:
        folder, filename = apply_fixes(clean(r["folder"]).strip("/"),
                                       clean(r["filename"]))
        rel = folder + "/" + filename
        src      = source_of(folder)
        if src is None:
            warnings.append("no source repo mapped for folder: " + folder)

        ext  = filename.rsplit(".", 1)[-1].lower()
        kind = "file" if ext == "pdf" else "link"

        # tag normalisation
        impacts, lenses, crosscut = [], [], False
        for tag in split_tags(r["impact_areas"]):
            key = tag.lower()
            if key in CROSSCUT:
                crosscut = True
            elif key in IMPACT_ALIASES:
                v = IMPACT_ALIASES[key]
                if v not in impacts:
                    impacts.append(v)
            elif key in LENS_ALIASES:
                v = LENS_ALIASES[key]
                if v not in lenses:
                    lenses.append(v)
            elif key == "engagement":
                pass  # focus-area name used as a tag; covered by focusAreas
            else:
                warnings.append("unmapped impact tag: " + tag)

        focus = []
        for ia in impacts:
            fa = IMPACT_TO_FOCUS.get(ia)
            if fa and fa not in focus:
                focus.append(fa)
        if "Engagement" in [t.strip() for t in split_tags(r["impact_areas"])] \
           and "Engagement" not in focus:
            focus.append("Engagement")

        dt = clean(r["doc_type"]).lower()
        doc_class = DOC_CLASS_OF.get(dt)
        if doc_class is None:
            doc_class = "Other"
            warnings.append("unmapped doc_type: " + clean(r["doc_type"]))

        source_url = clean(r["url"])
        hosted_url = (SOURCES[src]["base"] + encode_path(rel)) if (src and kind == "file") else None

        rec = {
            "id":          "R%04d" % int(r["id"]) if r["id"].isdigit() else clean(r["id"]),
            "collection":  "peers",
            "title":       make_title(filename),
            "institution": clean(r["institution"]),
            "group":       GROUP_LABELS.get(group_of(folder), group_of(folder)),
            "category":    clean(r["category"]).replace("-", " "),
            "docType":     clean(r["doc_type"]),
            "docClass":    doc_class,
            "yearLabel":   display_year(r["year"]),
            "yearSort":    sort_year(r["year"]),
            "ongoing":     is_ongoing(r["year"]),
            "kind":        kind,
            "priority":    clean(r["priority"]).upper() == "PRIORITY",
            "focusAreas":  focus,
            "impactAreas": impacts,
            "lenses":      lenses,
            "crossCutting": crosscut,
            "verification": clean(r["verification"]),
            "summary":     clean(r["summary"]),
            "ocUse":       clean(r["oc_use"]),
            "access":      "Public (peer publication)",
            "sourceUrl":   source_url,
            "path":        rel if kind == "file" else None,
            "repo":        src if kind == "file" else None,
            "fileUrl":     hosted_url,
        }

        if present is not None and kind == "file":
            rec["hosted"] = rel in present
        elif kind == "file":
            rec["hosted"] = None          # unknown until reconciled
        else:
            rec["hosted"] = False         # link records are never hosted

        # what the UI should open
        if rec["hosted"] and hosted_url:
            rec["openUrl"], rec["openTarget"] = hosted_url, "hosted"
        else:
            rec["openUrl"], rec["openTarget"] = source_url, "source"

        records.append(rec)

    if present is not None:
        catalogued = set()
        for r in rows:
            f, n = apply_fixes(clean(r["folder"]).strip("/"), clean(r["filename"]))
            catalogued.add(f + "/" + n)
        # Repo scaffolding, not documents: the Pages opt-out marker, repo
        # readmes, and the per-institution web-resource index pages.
        STRUCTURAL = re.compile(r"(^|/)(\.nojekyll|README\.md|00_WEB-RESOURCES\.md)$", re.I)
        orphans = sorted(p for p in present
                         if p not in catalogued and not STRUCTURAL.search(p))
        with open("unmatched_files.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["repo", "path"])
            for p in orphans:
                w.writerow([present[p], p])
        globals()["_ORPHANS"] = orphans
    else:
        globals()["_ORPHANS"] = None

    records.extend(load_oc_seed("oc_seed.csv"))
    records.sort(key=lambda x: (x["collection"] != "oc", x["group"], x["institution"],
                                -x["yearSort"], x["title"]))

    def uniq(field, collection=None):
        seen = []
        for rec in records:
            if collection and rec["collection"] != collection:
                continue
            v = rec[field]
            for item in (v if isinstance(v, list) else [v]):
                if item and item not in seen:
                    seen.append(item)
        return seen

    catalogue = {
        "title": "Okanagan College Sustainability Document Hub",
        "note": ("Machine-readable catalogue. One record per document. "
                 "openUrl is the link to use; sourceUrl is always the original publisher."),
        "framework": {"focusAreas": list(FRAMEWORK.keys()),
                      "impactAreas": [ia for ias in FRAMEWORK.values() for ia in ias]},
        "collections": [
            {"key": "oc",    "label": "Okanagan College",
             "blurb": "Our own plans, assessments and datasets. Catalogued here, held in SharePoint. "
                      "Nothing in this collection is mirrored to a public repository."},
            {"key": "peers", "label": "Peer Institutions",
             "blurb": "What BC post-secondary institutions and sector bodies have already published, "
                      "mapped to the four focus areas and thirteen impact areas."},
        ],
        "facets": {
            "groups":      sorted(uniq("group", "peers")),
            "institutions": sorted(uniq("institution")),
            "categories":  sorted(uniq("category")),
            "docTypes":    sorted(uniq("docType")),
            "docClasses":  [k for k in DOC_CLASSES if any(r["docClass"] == k for r in records)]
                           + (["Other"] if any(r["docClass"] == "Other" for r in records) else []),
            "lenses":      sorted(uniq("lenses")),
        },
        "records": records,
    }
    return catalogue, warnings


def write_csv(records, path):
    cols = ["id", "collection", "access", "title", "institution", "group", "category", "docClass", "docType",
            "yearLabel", "kind", "hosted", "priority", "focusAreas",
            "impactAreas", "lenses", "crossCutting", "verification",
            "openUrl", "fileUrl", "sourceUrl", "path", "summary", "ocUse"]
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in records:
            w.writerow(["; ".join(r[c]) if isinstance(r[c], list)
                        else ("" if r[c] is None else r[c]) for c in cols])


if __name__ == "__main__":
    manifest = sys.argv[1]
    present  = sys.argv[2] if len(sys.argv) > 2 else None
    cat, warns = build(manifest, present)
    with open("catalogue.json", "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False, indent=1)
    write_csv(cat["records"], "catalogue.csv")

    recs = cat["records"]
    print("records          :", len(recs),
          "(peers %d / OC %d)" % (sum(1 for r in recs if r["collection"] == "peers"),
                                  sum(1 for r in recs if r["collection"] == "oc")))
    print("  hosted files   :", sum(1 for r in recs if r["kind"] == "file" and r["hosted"] is True))
    print("  files unknown  :", sum(1 for r in recs if r["kind"] == "file" and r["hosted"] is None))
    print("  files missing  :", sum(1 for r in recs if r["kind"] == "file" and r["hosted"] is False))
    print("  link records   :", sum(1 for r in recs if r["kind"] == "link"))
    orph = globals().get("_ORPHANS")
    if orph is not None:
        print("  in repo, not in manifest:", len(orph), "-> unmatched_files.csv")
        for p in orph[:8]:
            print("      ", p)
        if len(orph) > 8:
            print("       ... and %d more" % (len(orph) - 8))
    print("  priority       :", sum(1 for r in recs if r["priority"]))
    print("  cross-cutting  :", sum(1 for r in recs if r["crossCutting"]))
    print("institutions     :", len(cat["facets"]["institutions"]))
    print("groups           :", cat["facets"]["groups"])
    print("doc types        :", len(cat["facets"]["docTypes"]),
          "-> classes:", len(cat["facets"]["docClasses"]))
    print("lenses           :", cat["facets"]["lenses"])
    if warns:
        from collections import Counter
        print("\nwarnings:")
        for k, v in Counter(warns).most_common():
            print("  %3d x %s" % (v, k))
