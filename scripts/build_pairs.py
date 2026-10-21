"""Build the product-matching pairs from the full catalog.

Needs the catalog's Parquet files (the Kaggle layout: produtos/, eans/, grupos.parquet) and the
2019-2022 table of refused matches (agrupamentos_recusados/). Runs with DuckDB and DedupKit:

    pip install duckdb pyarrow "dedupkit-br @ git+https://github.com/CaiqueDourado/DedupKit@v0.2.0#subdirectory=python"
    python scripts/build_pairs.py --data D:/catalogo_build --refused D:/catalogo_raw/agrupamentos_recusados --out D:/pares

Writes <out>/pairs.parquet, pairs_sample.csv (for GitHub), gold_to_label.csv (for review) and build_stats.json.
`--finalize-only --out <out>` reruns only the last cleaning step on an existing pairs.parquet. Every choice is deterministic (hash-based
sampling), so the same input gives the same pairs. See docs/methodology.md.
"""

from __future__ import annotations

import argparse
import re
import json
import time
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

import dedupkit_br as dk
from dedupkit_br.attributes import conflict_between

# Rules of the 2019 matching that compare names or URLs (not codes, not images)
NAME_RULES = ("productName", "productName_fingerprint", "productName_metaphone", "productName_ngram",
              "productName_tokenizada_fingerprint", "productUrl")
OFFER_COLS = "id, store_id, name, brand, price, image_hash, image_is_generic, group_id, group_rule_original"


def rows_as_dicts(con, query: str) -> list:
    """Run a query and return its rows as dicts (DB-API calls only, stable across DuckDB versions)."""
    cur = con.execute(query)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def sql_candidates(con: duckdb.DuckDBPyConnection, args) -> None:
    """Candidate pairs, one table per source, all with (a, b, source, key, cluster)."""
    pct = args.sample_percent
    con.execute(f"""
        CREATE TEMP TABLE offers AS
        SELECT {OFFER_COLS} FROM read_parquet('{args.data}/produtos/*.parquet')
        WHERE name IS NOT NULL AND length(name) >= 5
    """)
    log(f"offers: {con.execute('SELECT count(*) FROM offers').fetchone()[0]:,}")

    # 1. Offers that share a long code (not blacklisted), from different stores
    con.execute(f"""
        CREATE TEMP TABLE code_offers AS
        SELECT DISTINCT e.code, e.product_id
        FROM read_parquet('{args.data}/eans/*.parquet') e
        WHERE NOT coalesce(e.ignored_in_grouping, false)
          AND length(e.code) >= 8
          AND hash(e.code) % 100 < {pct}
    """)
    con.execute(f"""
        CREATE TEMP TABLE cand_code AS
        WITH blocks AS (
            SELECT code FROM code_offers GROUP BY code HAVING count(*) BETWEEN 2 AND {args.max_block}
        )
        SELECT x.product_id AS a, y.product_id AS b, 'code' AS source, x.code AS key, 'c:' || x.code AS cluster
        FROM code_offers x JOIN code_offers y ON x.code = y.code AND x.product_id < y.product_id
        JOIN blocks ON blocks.code = x.code
    """)
    log(f"code pairs: {con.execute('SELECT count(*) FROM cand_code').fetchone()[0]:,}")

    # 2. Offers in the same 2019 group, both joined through a name or URL rule
    rules = ", ".join(f"'{r}'" for r in NAME_RULES)
    con.execute(f"""
        CREATE TEMP TABLE cand_group AS
        WITH g AS (
            SELECT o.id, o.group_id FROM offers o
            JOIN read_parquet('{args.data}/grupos.parquet') gr ON gr.id = o.group_id
            WHERE gr.group_flag = 'ok' AND gr.offers BETWEEN 2 AND {args.max_block}
              AND o.group_rule_original IN ({rules})
              AND hash(o.group_id) % 100 < {pct}
        )
        SELECT x.id AS a, y.id AS b, 'group' AS source, CAST(x.group_id AS VARCHAR) AS key, 'g:' || x.group_id AS cluster
        FROM g x JOIN g y ON x.group_id = y.group_id AND x.id < y.id
    """)
    log(f"group pairs: {con.execute('SELECT count(*) FROM cand_group').fetchone()[0]:,}")

    # 3. Offers that share an image signature that is not generic
    con.execute(f"""
        CREATE TEMP TABLE cand_image AS
        WITH im AS (
            SELECT id, image_hash FROM offers
            WHERE image_hash IS NOT NULL AND NOT coalesce(image_is_generic, false)
              AND hash(image_hash) % 100 < {pct}
        ), blocks AS (
            SELECT image_hash FROM im GROUP BY 1 HAVING count(*) BETWEEN 2 AND {args.max_block}
        )
        SELECT x.id AS a, y.id AS b, 'image' AS source, x.image_hash AS key, 'i:' || x.image_hash AS cluster
        FROM im x JOIN im y ON x.image_hash = y.image_hash AND x.id < y.id
        JOIN blocks ON blocks.image_hash = x.image_hash
    """)
    log(f"image pairs: {con.execute('SELECT count(*) FROM cand_image').fetchone()[0]:,}")

    # 4. Similar names: same words once numbers and units are removed (size and voltage variants)
    con.execute(f"""
        CREATE TEMP TABLE cand_name AS
        WITH k AS (
            SELECT id, trim(regexp_replace(regexp_replace(lower(strip_accents(name)),
                       '[0-9]+([.,][0-9]+)?\\s*(kg|g|gr|mg|ml|l|lt|litros?|v|w|kw|gb|tb|mb|mah|cm|mm|m|pol|polegadas?|btus?)?\\b', ' ', 'g'),
                       '[^a-z]+', ' ', 'g')) AS key
            FROM offers WHERE hash(id) % 100 < {pct}
        ), blocks AS (
            SELECT key FROM k WHERE length(key) >= 12 AND key LIKE '% % %'
            GROUP BY key HAVING count(*) BETWEEN 2 AND {args.max_block}
        )
        SELECT x.id AS a, y.id AS b, 'name' AS source, x.key AS key, 'n:' || x.key AS cluster
        FROM k x JOIN k y ON x.key = y.key AND x.id < y.id
        JOIN blocks ON blocks.key = x.key
    """)
    log(f"similar-name pairs: {con.execute('SELECT count(*) FROM cand_name').fetchone()[0]:,}")


def refused_pairs(con, args):
    """The 2019-2022 refusals, with the offers that carried each name and code when they can be found."""
    con.execute(f"""
        CREATE TEMP TABLE refused AS
        SELECT DISTINCT name_a, name_b, rule_value AS code FROM read_parquet('{args.refused}/*.parquet')
        WHERE name_a IS NOT NULL AND name_b IS NOT NULL
    """)
    con.execute(f"""
        CREATE TEMP TABLE refused_resolved AS
        WITH e AS (
            SELECT DISTINCT e.code, o.id, o.name FROM read_parquet('{args.data}/eans/*.parquet') e
            JOIN offers o ON o.id = e.product_id
            WHERE e.code IN (SELECT code FROM refused)
        )
        SELECT r.name_a, r.name_b, r.code, min(ea.id) AS a, min(eb.id) AS b
        FROM refused r
        LEFT JOIN e ea ON ea.code = r.code AND ea.name = r.name_a
        LEFT JOIN e eb ON eb.code = r.code AND eb.name = r.name_b
        GROUP BY ALL
    """)
    n, resolved = con.execute("SELECT count(*), count(a) FILTER (WHERE b IS NOT NULL) FROM refused_resolved").fetchone()
    log(f"refused pairs: {n:,} ({resolved:,} with both offers found)")


UNITS = r"(kg|kgs|g|gr|mg|ml|l|lt|litros?|v|w|kw|gb|tb|mb|mah|cm|mm|m|pol|polegadas?|btus?|un|und|unid|pcs|pecas?|mp|mpx|hz|rpm|a)"
MEASURE = re.compile(r"\b[0-9]+(?:[.,][0-9]+)?(?: ?x ?[0-9]+(?:[.,][0-9]+)?)* ?" + UNITS + r"\b")
DIMENSIONS = re.compile(r"\b[0-9]+(?:[.,][0-9]+)?(?: ?x ?[0-9]+(?:[.,][0-9]+)?)+\b")


def model_tokens(name: str) -> frozenset:
    """Tokens that look like model numbers: letters and digits mixed (TB125, E435, 510BT) or
    numbers of 3+ digits. Measures (500 ml), dimensions (140x200) and short numbers are removed first."""
    text = dk.normalize(name)
    text = MEASURE.sub(" ", text)
    text = DIMENSIONS.sub(" ", text)
    out = set()
    for t in text.split():
        if len(t) >= 3 and any("0" <= c <= "9" for c in t):
            out.add(t)
    return frozenset(out)


def compact(name: str) -> str:
    return dk.normalize(name).replace(" ", "")


def models_disagree(ma: frozenset, mb: frozenset, name_a: str, name_b: str) -> bool:
    """Both names state a model number and none of them appears in the other name
    (spaces and punctuation ignored, so SG-102 matches SG102 and X360 matches 360)."""
    if not ma or not mb or (ma & mb):
        return False
    ca, cb = compact(name_a), compact(name_b)
    if any(t in cb for t in ma) or any(t in ca for t in mb):
        return False
    return True


class Classifier:
    """DedupKit checks (shared word, attributes) plus a model-number check, with caches."""

    def __init__(self):
        self._attrs: dict = {}
        self._models: dict = {}

    def models(self, name: str) -> frozenset:
        m = self._models.get(name)
        if m is None:
            m = model_tokens(name)
            if len(self._models) < 2_000_000:
                self._models[name] = m
        return m

    def attrs(self, name: str):
        a = self._attrs.get(name)
        if a is None:
            a = dk.attributes(name)
            if len(self._attrs) < 2_000_000:
                self._attrs[name] = a
        return a

    def check(self, name_a: str, name_b: str):
        if not dk.shares_word(name_a, name_b):
            return "no_shared_word", "names share no word"
        why = conflict_between(self.attrs(name_a), self.attrs(name_b))
        if why:
            return "attribute_conflict", why
        ma, mb = self.models(name_a), self.models(name_b)
        if models_disagree(ma, mb, name_a, name_b):
            return "model_conflict", f"model: {'/'.join(sorted(ma))} vs {'/'.join(sorted(mb))}"
        return "consistent", ""


# (source, check) -> (pair_type, label). None: not used.
LABELS = {
    ("code", "consistent"): ("same_code", 1),
    ("code", "attribute_conflict"): ("same_code_attribute_conflict", 0),
    ("code", "no_shared_word"): ("same_code_no_shared_word", 0),
    ("group", "consistent"): ("same_group_name_rule", 1),
    ("group", "attribute_conflict"): ("same_group_attribute_conflict", 0),
    ("group", "no_shared_word"): None,
    ("image", "consistent"): ("same_image", 1),
    ("image", "attribute_conflict"): ("same_image_attribute_conflict", 0),
    ("image", "no_shared_word"): None,
    ("name", "consistent"): None,
    ("name", "attribute_conflict"): ("similar_name_attribute_conflict", 0),
    ("name", "no_shared_word"): None,
    # Same barcode, different model numbers: in the sample labelled one by one most were the same product
    # written with different reference numbers, so these pairs are left out instead of labelled 0.
    ("code", "model_conflict"): None,
    ("group", "model_conflict"): ("same_group_model_conflict", 0),
    ("image", "model_conflict"): ("same_image_model_conflict", 0),
    ("name", "model_conflict"): ("similar_name_model_conflict", 0),
}

SCHEMA = pa.schema([
    ("pair_type", pa.string()), ("label", pa.int8()), ("reason", pa.string()), ("key", pa.string()),
    ("cluster", pa.string()), ("offer_a", pa.int64()), ("offer_b", pa.int64()),
    ("name_a", pa.string()), ("name_b", pa.string()), ("brand_a", pa.string()), ("brand_b", pa.string()),
    ("store_a", pa.int64()), ("store_b", pa.int64()), ("price_a", pa.float64()), ("price_b", pa.float64()),
    ("image_hash_a", pa.string()), ("image_hash_b", pa.string()),
    ("group_a", pa.int64()), ("group_b", pa.int64()), ("group_rule_a", pa.string()), ("group_rule_b", pa.string()),
    ("name_similarity", pa.float32()),
])


def similarity(a: str, b: str) -> float:
    """Jaccard similarity of the two names' word sets (DedupKit token keys): 1 = same words."""
    ta, tb = set(dk.token_key(a).split()), set(dk.token_key(b).split())
    return round(len(ta & tb) / len(ta | tb), 3) if ta | tb else 0.0


SWAP = ["offer", "name", "brand", "store", "price", "image_hash", "group", "group_rule"]


def finalize(out: Path, sample_per_type: int, gold_per_type: int, stats: dict) -> None:
    """Clean pairs.parquet, then write pairs_sample.csv, gold_to_label.csv and build_stats.json.

    The 2019 refusals are kept as logged, so they need three fixes: offers ordered as a < b,
    a listing refused against itself removed, and a pair of offers that is also in another pair
    type kept only once (in the other type). Same-store refusals are kept: they happened.
    """
    con = duckdb.connect()
    src = (out / "pairs.parquet").as_posix()
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{src}')").fetchall()]
    swap = "offer_a > offer_b"
    select = []
    for c in cols:
        stem, _, side = c.rpartition("_")
        if side in ("a", "b") and stem in SWAP:
            other = f"{stem}_{'b' if side == 'a' else 'a'}"
            select.append(f"CASE WHEN {swap} THEN {other} ELSE {c} END AS {c}")
        else:
            select.append(c)
    tmp = (out / "pairs_clean.parquet").as_posix()
    con.execute(f"""
        COPY (
            WITH fixed AS (SELECT {', '.join(select)} FROM read_parquet('{src}'))
            SELECT * FROM fixed
            WHERE name_a <> name_b AND (offer_a IS NULL OR offer_b IS NULL OR offer_a <> offer_b)
            QUALIFY offer_a IS NULL OR offer_b IS NULL
                 OR row_number() OVER (PARTITION BY offer_a, offer_b ORDER BY pair_type = 'refused_2019', pair_id) = 1
            ORDER BY pair_id
        ) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)
    """)
    con.close()
    Path(tmp).replace(out / "pairs.parquet")
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT * FROM read_parquet('{src}')
            QUALIFY row_number() OVER (PARTITION BY pair_type ORDER BY hash(pair_id, 'sample')) <= {sample_per_type}
            ORDER BY pair_id
        ) TO '{(out / 'pairs_sample.csv').as_posix()}' (HEADER, DELIMITER ',')
    """)
    con.execute(f"""
        COPY (
            SELECT pair_id, pair_type, label, reason, name_a, name_b, brand_a, brand_b, price_a, price_b
            FROM read_parquet('{src}')
            WHERE split = 'test'
            QUALIFY row_number() OVER (PARTITION BY pair_type ORDER BY hash(pair_id, 'gold')) <= {gold_per_type}
            ORDER BY pair_type, pair_id
        ) TO '{(out / 'gold_to_label.csv').as_posix()}' (HEADER, DELIMITER ',')
    """)
    by_type = dict(con.execute(f"SELECT pair_type, count(*) FROM read_parquet('{src}') GROUP BY 1 ORDER BY 1").fetchall())
    con.close()
    stats = {"pairs": sum(by_type.values()), "by_type": by_type, **{k: v for k, v in stats.items() if k not in ("pairs", "by_type")},
             "duckdb": duckdb.__version__}
    (out / "build_stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    log(json.dumps(stats))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=False, help="folder with produtos/, eans/, grupos.parquet")
    ap.add_argument("--refused", required=False, help="folder with the refused-matches Parquet")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample-percent", type=int, default=10, help="share of codes/groups/images/names sampled (by hash)")
    ap.add_argument("--max-block", type=int, default=30, help="ignore keys shared by more offers than this")
    ap.add_argument("--max-per-type", type=int, default=200_000)
    ap.add_argument("--sample-per-type", type=int, default=1000, help="pairs per type in pairs_sample.csv")
    ap.add_argument("--gold-per-type", type=int, default=60, help="test pairs per type in gold_to_label.csv")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--finalize-only", action="store_true",
                    help="only clean an existing <out>/pairs.parquet and rewrite the small files")
    args = ap.parse_args()
    if args.finalize_only:
        out = Path(args.out)
        old = json.loads((out / "build_stats.json").read_text(encoding="utf-8")) if (out / "build_stats.json").exists() else {}
        finalize(out, args.sample_per_type, args.gold_per_type, old)
        return
    if not args.data or not args.refused:
        ap.error("--data and --refused are required (unless --finalize-only)")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    con = duckdb.connect(str(out / "work.duckdb"))
    if args.threads:
        con.execute(f"SET threads = {args.threads}")
    con.execute(f"SET temp_directory = '{(out / 'tmp').as_posix()}'")
    sql_candidates(con, args)
    refused_pairs(con, args)

    # Same-store pairs are dropped (stores repeat their own listings), cross-store pairs kept.
    con.execute(f"""
        CREATE TEMP TABLE cand AS
        WITH u AS (
            SELECT * FROM cand_code UNION ALL SELECT * FROM cand_group
            UNION ALL SELECT * FROM cand_image UNION ALL SELECT * FROM cand_name
        )
        SELECT u.*,
               x.name AS name_a, y.name AS name_b, x.brand AS brand_a, y.brand AS brand_b,
               x.store_id AS store_a, y.store_id AS store_b, x.price AS price_a, y.price AS price_b,
               x.image_hash AS image_hash_a, y.image_hash AS image_hash_b,
               x.group_id AS group_a, y.group_id AS group_b,
               x.group_rule_original AS group_rule_a, y.group_rule_original AS group_rule_b,
               hash(u.source, u.a, u.b) AS h
        FROM u JOIN offers x ON x.id = u.a JOIN offers y ON y.id = u.b
        WHERE x.store_id <> y.store_id AND x.name <> y.name
    """)
    total = con.execute("SELECT count(*) FROM cand").fetchone()[0]
    log(f"candidate pairs from different stores, different names: {total:,}")

    clf = Classifier()
    counts: dict = {}
    seen = set()
    writer = pq.ParquetWriter(out / "pairs_unsplit.parquet", SCHEMA)
    con.execute("CREATE TEMP TABLE cand_sorted AS SELECT row_number() OVER (ORDER BY h) AS rn, * FROM cand ORDER BY h")
    page = 200_000
    done = 0
    for start in range(1, total + 1, page):
        rows = rows_as_dicts(con, f"SELECT * FROM cand_sorted WHERE rn >= {start} AND rn < {start + page}")
        cols = {f.name: [] for f in SCHEMA}
        for r in rows:
            pair = (r["a"], r["b"])
            if pair in seen:
                continue
            check, reason = clf.check(r["name_a"], r["name_b"])
            target = LABELS[(r["source"], check)]
            if target is None:
                continue
            ptype, label = target
            if counts.get(ptype, 0) >= args.max_per_type:
                continue
            counts[ptype] = counts.get(ptype, 0) + 1
            seen.add(pair)
            for k, v in (("pair_type", ptype), ("label", label), ("reason", reason), ("key", r["key"]),
                         ("cluster", r["cluster"]), ("offer_a", r["a"]), ("offer_b", r["b"])):
                cols[k].append(v)
            for k in ("name_a", "name_b", "brand_a", "brand_b", "store_a", "store_b", "image_hash_a", "image_hash_b",
                      "group_a", "group_b", "group_rule_a", "group_rule_b"):
                cols[k].append(r[k])
            cols["price_a"].append(float(r["price_a"]) if r["price_a"] is not None else None)
            cols["price_b"].append(float(r["price_b"]) if r["price_b"] is not None else None)
            cols["name_similarity"].append(similarity(r["name_a"], r["name_b"]))
        writer.write_table(pa.table(cols, schema=SCHEMA))
        done += len(rows)
        log(f"classified {done:,} / {total:,}  {counts}")

    # Refused 2019-2022 pairs (label 0, the 2019 word check), capped like the others
    rows = rows_as_dicts(con, f"""
        SELECT r.*, x.brand AS brand_a, y.brand AS brand_b, x.store_id AS store_a, y.store_id AS store_b,
               x.price AS price_a, y.price AS price_b, x.image_hash AS image_hash_a, y.image_hash AS image_hash_b,
               x.group_id AS group_a, y.group_id AS group_b,
               x.group_rule_original AS group_rule_a, y.group_rule_original AS group_rule_b
        FROM refused_resolved r LEFT JOIN offers x ON x.id = r.a LEFT JOIN offers y ON y.id = r.b
        ORDER BY hash(r.code, r.name_a, r.name_b) LIMIT {args.max_per_type}
    """)
    cols = {f.name: [] for f in SCHEMA}
    for r in rows:
        cols["pair_type"].append("refused_2019")
        cols["label"].append(0)
        cols["reason"].append("2019: names share no word")
        cols["key"].append(r["code"])
        cols["cluster"].append("c:" + r["code"])
        cols["offer_a"].append(r["a"])
        cols["offer_b"].append(r["b"])
        for k in ("name_a", "name_b", "brand_a", "brand_b", "store_a", "store_b", "image_hash_a", "image_hash_b",
                  "group_a", "group_b", "group_rule_a", "group_rule_b"):
            cols[k].append(r[k])
        cols["price_a"].append(float(r["price_a"]) if r["price_a"] is not None else None)
        cols["price_b"].append(float(r["price_b"]) if r["price_b"] is not None else None)
        cols["name_similarity"].append(similarity(r["name_a"], r["name_b"]))
    writer.write_table(pa.table(cols, schema=SCHEMA))
    counts["refused_2019"] = len(rows)
    writer.close()

    # Split by cluster (a code, group, image or name key never crosses splits), then number the pairs
    con.execute(f"""
        COPY (
            SELECT row_number() OVER (ORDER BY pair_type, hash(cluster, offer_a, offer_b, name_a, name_b)) AS pair_id,
                   CASE WHEN hash(cluster) % 10 = 0 THEN 'test' WHEN hash(cluster) % 10 = 1 THEN 'valid' ELSE 'train' END AS split,
                   *
            FROM read_parquet('{(out / 'pairs_unsplit.parquet').as_posix()}')
        ) TO '{(out / 'pairs.parquet').as_posix()}' (FORMAT parquet, COMPRESSION zstd)
    """)
    con.close()
    (out / "pairs_unsplit.parquet").unlink()
    (out / "work.duckdb").unlink(missing_ok=True)
    stats = {
        "candidates": total, "sample_percent": args.sample_percent, "max_block": args.max_block,
        "max_per_type": args.max_per_type, "dedupkit": dk.__version__, "seconds": round(time.time() - t0),
    }
    finalize(out, args.sample_per_type, args.gold_per_type, stats)


if __name__ == "__main__":
    main()
