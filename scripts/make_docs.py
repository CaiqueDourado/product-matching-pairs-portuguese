"""Fill the README templates and the Kaggle description/metadata with the numbers of a build.

    python scripts/make_docs.py --stats build_stats.json      # after scripts/evaluate_gold.py
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TYPES = [
    ("same_code", 1, "same barcode, names share a word, no attribute or model conflict",
     "mesmo código de barras, nomes com palavra em comum, sem conflito de atributo ou modelo"),
    ("same_code_attribute_conflict", 0, "same barcode, different size, voltage, colour, pack...",
     "mesmo código de barras, tamanho, voltagem, cor, quantidade... diferentes"),
    ("same_code_no_shared_word", 0, "same barcode, names share no word (a store reused the code)",
     "mesmo código de barras, nomes sem palavra em comum (a loja reaproveitou o código)"),
    ("same_group_name_rule", 1, "same 2019 product group (joined by a name or URL rule), no conflict",
     "mesmo grupo de produto de 2019 (por regra de nome ou URL), sem conflito"),
    ("same_group_attribute_conflict", 0, "same 2019 group, different attributes",
     "mesmo grupo de 2019, atributos diferentes"),
    ("same_group_model_conflict", 0, "same 2019 group, different model numbers (TB125 vs TB112)",
     "mesmo grupo de 2019, números de modelo diferentes (TB125 × TB112)"),
    ("same_image", 1, "same image file, no conflict", "mesmo arquivo de imagem, sem conflito"),
    ("same_image_attribute_conflict", 0, "same image file, different attributes (sizes of one shoe)",
     "mesmo arquivo de imagem, atributos diferentes (tamanhos de um calçado)"),
    ("same_image_model_conflict", 0, "same image file, different model numbers",
     "mesmo arquivo de imagem, números de modelo diferentes"),
    ("similar_name_attribute_conflict", 0, "same name without numbers and units, different measures",
     "mesmo nome sem números e unidades, medidas diferentes"),
    ("similar_name_model_conflict", 0, "same name without numbers, different model numbers or years",
     "mesmo nome sem números, modelos ou anos diferentes"),
    ("refused_2019", 0, "barcode match refused by the 2019 routine (names share no word)",
     "casamento por código recusado pela rotina de 2019 (nomes sem palavra em comum)"),
]


def agreement() -> dict:
    out = {}
    for r in csv.DictReader(open(ROOT / "gold" / "gold_pairs.csv", encoding="utf-8")):
        if r["label"] == "" or not r["pair_type"]:
            continue
        out.setdefault(r["pair_type"], []).append(r["silver_label"] == r["label"])
    return {t: (sum(v) / len(v), len(v)) for t, v in out.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default=ROOT / "build_stats.json", type=Path)
    ap.add_argument("--sample", default=ROOT / "sample" / "pairs_sample.csv", type=Path)
    args = ap.parse_args()
    stats = json.loads(args.stats.read_text(encoding="utf-8"))
    sample = sum(1 for _ in open(args.sample, encoding="utf-8")) - 1
    agree = agreement()
    en_rows, pt_rows = [], []
    for t, lab, en, pt in TYPES:
        n = stats["by_type"].get(t, 0)
        a, k = agree.get(t, (None, 0))
        cell_en = f"{a:.0%} of {k}" if a is not None else ""
        cell_pt = f"{a:.0%} de {k}" if a is not None else ""
        en_rows.append(f"| `{t}` | {lab} | {en} | {n:,} | {cell_en} |")
        n_pt = f"{n:,}".replace(",", ".")
        pt_rows.append(f"| `{t}` | {lab} | {pt} | {n_pt} | {cell_pt} |")
    total = stats["pairs"]
    fill = {
        "{TOTAL}": f"{total:,}", "{TOTAL_PT}": f"{total:,}".replace(",", "."),
        "{SAMPLE}": f"{sample:,}", "{SAMPLE_PT}": f"{sample:,}".replace(",", "."),
        "{TYPE_TABLE}": "\n".join(en_rows), "{TYPE_TABLE_PT}": "\n".join(pt_rows),
    }
    for src, dst in (("README.template.md", "README.md"), ("README.pt-BR.template.md", "README.pt-BR.md"),
                     ("kaggle-description.template.md", "docs/kaggle-description.md")):
        text = (ROOT / "templates" / src).read_text(encoding="utf-8")
        for k, v in fill.items():
            text = text.replace(k, v)
        (ROOT / dst).write_text(text, encoding="utf-8")

    pair_cols = {
        "pair_id": ("integer", "Pair id"), "split": ("string", "train, valid or test, by cluster"),
        "pair_type": ("string", "How the pair was found and what the checks said"),
        "label": ("integer", "1 same product (same SKU), 0 different. Silver label from rules"),
        "reason": ("string", "Why the pair is 0: attribute, model numbers or no shared word"),
        "key": ("string", "Blocking value: barcode, 2019 group, image signature or name without numbers"),
        "cluster": ("string", "Source and key. The same cluster is always in the same split"),
        "offer_a": ("integer", "Offer id in the catalog"), "offer_b": ("integer", "Offer id in the catalog"),
        "name_a": ("string", "Product name as the store wrote it"), "name_b": ("string", "Product name as the store wrote it"),
        "brand_a": ("string", "Brand from the store or feed"), "brand_b": ("string", "Brand from the store or feed"),
        "store_a": ("integer", "Store id in the catalog"), "store_b": ("integer", "Store id in the catalog"),
        "price_a": ("number", "Price in BRL"), "price_b": ("number", "Price in BRL"),
        "image_hash_a": ("string", "Image signature of the catalog"), "image_hash_b": ("string", "Image signature of the catalog"),
        "group_a": ("integer", "2019 product group"), "group_b": ("integer", "2019 product group"),
        "group_rule_a": ("string", "Rule that put the offer in its 2019 group"),
        "group_rule_b": ("string", "Rule that put the offer in its 2019 group"),
        "name_similarity": ("number", "Jaccard similarity of the names' word sets, 0 to 1"),
    }
    gold_cols = {
        "gold_id": ("integer", "Row number"), "source": ("string", "How the candidate was found"),
        "pair_type": ("string", "Type the build rules give the pair; empty when left out"),
        "silver_label": ("integer", "Label the build rules give"), "reason": ("string", "As in pairs.parquet"),
        "label": ("integer", "Label checked one by one: 1 same SKU, 0 different, empty when unsure"),
        "name_a": ("string", "Product name"), "name_b": ("string", "Product name"),
        "brand_a": ("string", "Brand"), "brand_b": ("string", "Brand"),
        "price_a": ("number", "Price in BRL"), "price_b": ("number", "Price in BRL"),
    }
    fields = lambda cols: [{"name": k, "description": d, "type": t} for k, (t, d) in cols.items()]  # noqa: E731
    meta = {
        "title": "Pares de Produtos para Matching (pt-BR)",
        "subtitle": f"{total / 1e6:.1f}M labelled pairs of Brazilian product offers, hard negatives, 780 checked",
        "description": (ROOT / "docs" / "kaggle-description.md").read_text(encoding="utf-8"),
        "id": "caiquedourado/pares-matching-produtos-ptbr",
        "licenses": [{"name": "Attribution 4.0 International (CC BY 4.0)"}],
        "keywords": ["brazil", "nlp", "tabular", "retail and shopping", "e-commerce services"],
        "isPrivate": False,
        "resources": [
            {"path": "pairs.parquet", "description": "Every pair of offers with type, silver label, split and context columns.",
             "schema": {"fields": fields(pair_cols)}},
            {"path": "gold_pairs.csv", "description": "780 pairs checked one by one, with the label the rules give and the checked label.",
             "schema": {"fields": fields(gold_cols)}},
            {"path": "build_stats.json", "description": "Pairs per type and build parameters."},
        ],
    }
    (ROOT / "kaggle").mkdir(exist_ok=True)
    (ROOT / "kaggle" / "dataset-metadata.json").write_text(json.dumps(meta, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print("README.md, README.pt-BR.md, docs/kaggle-description.md and kaggle/dataset-metadata.json written")


if __name__ == "__main__":
    main()
