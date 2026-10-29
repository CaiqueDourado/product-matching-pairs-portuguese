"""Write one labelled pair as nested JSON (docs/example-pair.json), built from the sample and the gold pairs.

    python scripts/make_json.py

Takes one row of sample/pairs_sample.csv (PAIR_ID: two phone cases with the same photo and different screen
sizes), splits it into its two offers, says which keys of the two offers are equal, and adds the label checked
one by one in gold/gold_pairs.csv (joined by the two names). Needs duckdb (requirements.txt).
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
PAIR_ID = 1426369
OFFER_COLUMNS = ("offer", "name", "brand", "store", "price", "image_hash", "group", "group_rule")


def row(sql: str, params: list) -> dict | None:
    rel = duckdb.execute(sql, params)
    names = [d[0] for d in rel.description]
    rows = rel.fetchall()
    return dict(zip(names, rows[0])) if rows else None


def build() -> dict:
    sample = (ROOT / "sample" / "pairs_sample.csv").as_posix()
    gold_csv = (ROOT / "gold" / "gold_pairs.csv").as_posix()
    p = row(f"SELECT * FROM read_csv('{sample}', all_varchar = true) WHERE pair_id = ?", [str(PAIR_ID)])
    gold = row(f"SELECT gold_id, source, silver_label, label FROM read_csv('{gold_csv}', all_varchar = true) "
               "WHERE name_a = ? AND name_b = ?", [p["name_a"], p["name_b"]])

    def num(v: str | None):
        if v is None or v == "":
            return None
        return float(v) if "." in v else int(v)

    def offer(side: str) -> dict:
        o = {c: p[f"{c}_{side}"] for c in OFFER_COLUMNS}
        for c in ("offer", "store", "price", "group"):
            o[c] = num(o[c])
        return o

    a, b = offer("a"), offer("b")
    return {
        "pair_id": int(p["pair_id"]),
        "split": p["split"],
        "pair_type": p["pair_type"],
        "label": int(p["label"]),
        "reason": p["reason"],
        "key": p["key"],
        "cluster": p["cluster"],
        "offer_a": a,
        "offer_b": b,
        "same": {c: a[c] == b[c] for c in ("image_hash", "group", "brand", "store")},
        "name_similarity": num(p["name_similarity"]),
        "gold": None if gold is None else {k: num(v) if k != "source" else v for k, v in gold.items()},
    }


def main() -> None:
    rec = build()
    out = ROOT / "docs" / "example-pair.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
