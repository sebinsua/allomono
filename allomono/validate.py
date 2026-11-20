"""Validate the built fonts with Font Bakery: `python -m allomono.validate`.

The four styles are checked together as one family. Failures that are deliberate are listed in WAIVED with the reason,
and reported separately, so a real regression cannot hide among them.
"""
import collections
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAMILIES = {"allomono": ["Regular", "Bold", "Italic", "BoldItalic"]}
WAIVED = {}


def run(family, styles):
    out = ROOT / "proofs" / ("fontbakery-%s.json" % family.replace(" ", ""))
    out.parent.mkdir(exist_ok=True)
    fonts = [str(ROOT / "fonts" / ("allomono-%s.ttf" % s)) for s in styles]
    out.unlink(missing_ok=True)      # never read a report left by an earlier run
    subprocess.run([str(Path(sys.executable).parent / "fontbakery"), "check-universal", "--json", str(out), "-q", "-n", *fonts], capture_output=True)
    data = json.loads(out.read_text())
    found = collections.defaultdict(list)
    for section in data["sections"]:
        for check in section["checks"]:
            if check["result"] in ("FAIL", "ERROR", "FATAL", "WARN"):
                key = check["key"][1].split(":")[-1].rstrip(">")
                text = "; ".join(str(log["message"].get("message") if isinstance(log["message"], dict) else log["message"]).replace("\n", " ")[:200] for log in check["logs"] if log["status"] != "PASS")
                found[(check["result"], key)].append(((check.get("filename") or "").split("/")[-1], text))
    return data["result"], found


def main():
    bad = 0
    for family, styles in FAMILIES.items():
        totals, found = run(family, styles)
        print("\n%s: %d passed, %d failed, %d warnings" % (family, totals.get("PASS", 0), totals.get("FAIL", 0) + totals.get("ERROR", 0), totals.get("WARN", 0)))
        for (result, key), items in sorted(found.items()):
            waived = key in WAIVED
            bad += 0 if waived else (result != "WARN")
            files = ", ".join(sorted({f.replace("allomono-", "").replace(".ttf", "") for f, _ in items if f})) or "family"
            print("  [%s%s] %s (%s)" % (result, ", waived" if waived else "", key, files))
            print("      %s" % (WAIVED[key] if waived else items[0][1]))
    print("\n%s" % ("No unwaived failures." if not bad else "%d unwaived failure(s)." % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
