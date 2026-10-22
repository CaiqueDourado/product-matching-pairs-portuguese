**2,062,205 labelled pairs of product offers from Brazilian online stores**, for training and testing product matching (entity resolution) in Portuguese. Most of them are **hard negatives**: two offers that share a barcode, a photo or almost the whole name, and are still different products (another size, voltage, colour, pack or model). **780 pairs were checked one by one**, so methods can be scored against a reference that does not come from the rules that built the rest.

Code, documentation and a sample: https://github.com/CaiqueDourado/pares-matching-produtos-ptbr

| Same barcode, same product | Same barcode, different product |
|---|---|
| Pilha de Zinco AAA Rayovac 4un. | Ferro a Vapor T-fal Fv1420 Rosa - 127v |
| Pilha Rayovac Amarelinha Palito com 4 | Ferro a Vapor T-Fal FV1420 Rosa - 220V |

## Pair types

| Pair type | Label | How it was made | Pairs | Label right in the checked pairs |
|---|:---:|---|---:|---:|
| `same_code` | 1 | same barcode, names share a word, no attribute or model conflict | 200,000 | 95% of 60 |
| `same_code_attribute_conflict` | 0 | same barcode, different size, voltage, colour, pack... | 116,752 | 74% of 43 |
| `same_code_no_shared_word` | 0 | same barcode, names share no word (a store reused the code) | 81,179 | 98% of 60 |
| `same_group_name_rule` | 1 | same 2019 product group (joined by a name or URL rule), no conflict | 200,000 | 66% of 44 |
| `same_group_attribute_conflict` | 0 | same 2019 group, different attributes | 200,000 | 99% of 76 |
| `same_group_model_conflict` | 0 | same 2019 group, different model numbers (TB125 vs TB112) | 200,000 | 89% of 47 |
| `same_image` | 1 | same image file, no conflict | 200,000 | 83% of 30 |
| `same_image_attribute_conflict` | 0 | same image file, different attributes (sizes of one shoe) | 200,000 | 99% of 96 |
| `same_image_model_conflict` | 0 | same image file, different model numbers | 84,702 | 95% of 44 |
| `similar_name_attribute_conflict` | 0 | same name without numbers and units, different measures | 200,000 | 100% of 67 |
| `similar_name_model_conflict` | 0 | same name without numbers, different model numbers or years | 200,000 | 97% of 39 |
| `refused_2019` | 0 | barcode match refused by the 2019 routine (names share no word) | 179,572 | 97% of 59 |

"Same product" means the same SKU: the same model in the same size, colour, voltage and pack. Labels in `pairs.parquet` are silver (from rules); the last column shows how often each rule was right on the checked pairs. Score models on `gold_pairs.csv`.

![Methods on the checked pairs](https://raw.githubusercontent.com/CaiqueDourado/pares-matching-produtos-ptbr/main/docs/img/gold-methods.png)

## How it was built

![How the pairs were built](https://raw.githubusercontent.com/CaiqueDourado/pares-matching-produtos-ptbr/main/docs/img/flow.png)

## Files

- `pairs.parquet`: every pair, with names, brands, stores, prices, image signatures, 2019 groups, `split` (train/valid/test by cluster: a barcode, group or image never crosses splits) and `name_similarity`.
- `gold_pairs.csv`: the 780 pairs checked one by one (label 1, 0 or empty when the names do not say enough).
- `build_stats.json`: counts and build parameters.

## Quick start

```python
import duckdb
duckdb.sql("""
    SELECT split, pair_type, label, count(*) AS pairs
    FROM '/kaggle/input/pares-matching-produtos-ptbr/pairs.parquet'
    GROUP BY ALL ORDER BY split, pair_type
""")
```

## Source

Offers from the Brazilian e-commerce product catalog (114.6 million offers, 2019-2024): https://www.kaggle.com/datasets/caiquedourado/catalogo-produtos-ecommerce-brasil. Pairs typed with DedupKit 0.2.0 (https://github.com/CaiqueDourado/DedupKit) plus a model-number check. Methodology: https://github.com/CaiqueDourado/pares-matching-produtos-ptbr/blob/main/docs/methodology.md

## License

CC BY 4.0. Product names, brands and prices are factual information from stores and public affiliate feeds. No images are distributed.
