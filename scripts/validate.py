"""Check the pairs before publishing. Exits with code 1 on any failure.

    python scripts/validate.py --data sample --sample      # the GitHub sample (CI)
    python scripts/validate.py --data D:/pares3            # the full build (pairs.parquet + build_stats.json)

The gold pairs (gold/gold_pairs.csv) are checked in both modes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
LABEL_OF_TYPE = {
    "same_code": 1, "same_group_name_rule": 1, "same_image": 1,
    "same_code_attribute_conflict": 0, "same_code_no_shared_word": 0,
    "same_group_attribute_conflict": 0, "same_group_model_conflict": 0,
    "same_image_attribute_conflict": 0, "same_image_model_conflict": 0,
    "similar_name_attribute_conflict": 0, "similar_name_model_conflict": 0, "refused_2019": 0,
}
COLUMNS = ["pair_id", "split", "pair_type", "label", "reason", "key", "cluster", "offer_a", "offer_b", "name_a", "name_b",
           "brand_a", "brand_b", "store_a", "store_b", "price_a", "price_b", "image_hash_a", "image_hash_b",
           "group_a", "group_b", "group_rule_a", "group_rule_b", "name_similarity"]
FAILS: list[str] = []


def check(ok: bool, message: str) -> None:
    print(("OK   " if ok else "FAIL ") + message)
    if not ok:
        FAILS.append(message)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--sample", action="store_true")
    args = ap.parse_args()
    con = duckdb.connect()
    src = (f"read_csv_auto('{(args.data / 'pairs_sample.csv').as_posix()}', header=true)" if args.sample
           else f"read_parquet('{(args.data / 'pairs.parquet').as_posix()}')")
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731

    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
    check(cols == COLUMNS, f"columns are {', '.join(COLUMNS)}")
    n = one(f"SELECT count(*) FROM {src}")
    check(n > 0, f"{n:,} pairs")
    check(one(f"SELECT count(*) - count(DISTINCT pair_id) FROM {src}") == 0, "pair_id is unique")
    types = {t: lab for t, lab in con.execute(f"SELECT DISTINCT pair_type, label FROM {src}").fetchall()}
    check(set(types) <= set(LABEL_OF_TYPE), "only known pair types")
    check(all(LABEL_OF_TYPE.get(t) == lab for t, lab in types.items()), "label matches the pair type")
    check(one(f"SELECT count(*) FROM {src} WHERE split NOT IN ('train', 'valid', 'test')") == 0, "split is train, valid or test")
    check(one(f"SELECT count(*) FROM (SELECT cluster FROM {src} GROUP BY cluster HAVING count(DISTINCT split) > 1)") == 0,
          "no cluster crosses splits")
    check(one(f"SELECT count(*) FROM {src} WHERE offer_a >= offer_b") == 0, "offer_a < offer_b when both are known")
    check(one(f"SELECT count(*) FROM {src} WHERE pair_type <> 'refused_2019' AND (offer_a IS NULL OR offer_b IS NULL)") == 0,
          "only refused_2019 pairs may lack offer ids")
    check(one(f"SELECT count(*) FROM {src} WHERE store_a = store_b AND pair_type <> 'refused_2019'") == 0,
          "the two offers come from different stores (2019 refusals are kept as logged)")
    check(one(f"SELECT count(*) FROM {src} WHERE name_a = name_b") == 0, "the two names differ")
    check(one(f"SELECT count(*) FROM {src} WHERE name_similarity < 0 OR name_similarity > 1") == 0, "name_similarity in [0, 1]")
    check(one(f"SELECT count(*) FROM {src} WHERE regexp_matches(name_a || ' ' || name_b, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[a-z]{{2,}}')") == 0,
          "no e-mail addresses in names")
    check(one(f"SELECT count(*) FROM (SELECT least(offer_a, offer_b), greatest(offer_a, offer_b) FROM {src} "
              f"WHERE offer_a IS NOT NULL AND offer_b IS NOT NULL GROUP BY ALL HAVING count(*) > 1)") == 0, "each pair of offers appears once")
    if not args.sample:
        stats = json.loads((args.data / "build_stats.json").read_text(encoding="utf-8"))
        check(stats["pairs"] == n, "build_stats.json pairs = rows")
        by_type = dict(con.execute(f"SELECT pair_type, count(*) FROM {src} GROUP BY 1").fetchall())
        check(by_type == stats["by_type"], "build_stats.json counts by type = rows")

    gold = f"read_csv_auto('{(ROOT / 'gold' / 'gold_pairs.csv').as_posix()}', header=true, all_varchar=true)"
    check(one(f"SELECT count(*) FROM {gold}") == 780, "780 gold pairs")
    check(one(f"SELECT count(*) FROM {gold} WHERE label IS NOT NULL AND label NOT IN ('0', '1')") == 0, "gold label is 0, 1 or empty")
    check(one(f"SELECT count(*) FROM {gold} WHERE pair_type IS NOT NULL AND pair_type NOT IN "
              f"({', '.join(repr(t) for t in LABEL_OF_TYPE)})") == 0, "gold pair types are known")

    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
