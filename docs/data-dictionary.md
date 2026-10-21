# Data dictionary

[Português](data-dictionary.pt-BR.md)

## pairs.parquet (Kaggle) and sample/pairs_sample.csv

One row per pair of offers. Offer columns come in pairs: `_a` and `_b`, with `offer_a < offer_b` when both are known.

| Column | Type | Description |
|---|---|---|
| pair_id | int | Pair id (unique) |
| split | text | `train`, `valid` or `test`, decided by `cluster` (about 80/10/10) |
| pair_type | text | How the pair was found and what the checks said (see the table in the README) |
| label | int | 1 = same product (same SKU), 0 = different. Silver: comes from rules; see how often each type is right in the README |
| reason | text | Why a pair was labelled 0: the attribute that differs (`size: 38 vs 40`, `voltage_v: 127 vs 220`, `colour: preto vs branco`), the model numbers (`model: tb125 vs tb112`), `names share no word`, or `2019: names share no word`. Empty for label 1 |
| key | text | The blocking value that produced the pair: barcode, 2019 group id, image signature or name without numbers |
| cluster | text | Source and key (`c:` barcode, `g:` group, `i:` image, `n:` name). Pairs with the same cluster are always in the same split |
| offer_a, offer_b | int | Offer ids in the catalog (`produtos.id`). Empty for 2019 refusals that could not be linked back to an offer |
| name_a, name_b | text | Product names as the stores wrote them |
| brand_a, brand_b | text | Brand given by the store or feed (marketplaces often put the seller here) |
| store_a, store_b | int | Store ids (catalog `lojas.id`) |
| price_a, price_b | decimal | Price in BRL at collection time; empty when unknown |
| image_hash_a, image_hash_b | text | Image signature of the catalog (16×16 grayscale, SHA-256 in decimal). Equal values mean the same image file |
| group_a, group_b | int | 2019 product group of each offer (catalog `grupos.id`) |
| group_rule_a, group_rule_b | text | Rule through which each offer joined its 2019 group (`group_rule_original` in the catalog) |
| name_similarity | float | Jaccard similarity of the two names' word sets (DedupKit token keys), 0 to 1 |

## gold/gold_pairs.csv

780 pairs labelled one by one (see the methodology).

| Column | Type | Description |
|---|---|---|
| gold_id | int | Row number |
| source | text | How the candidate was found: `same_code`, `same_group`, `same_image`, `similar_name` or `refused_2019` |
| pair_type | text | The type the build rules give this pair; empty when the rules leave it out (same barcode with different model numbers) |
| silver_label | int | The label the build rules give (empty when left out) |
| reason | text | As in `pairs.parquet` |
| label | int | **Hand label**: 1 = same SKU, 0 = different; empty when the names do not say enough |
| name_a, name_b, brand_a, brand_b, price_a, price_b | | As in `pairs.parquet` |

## build_stats.json

Pairs per type, number of candidates, sampling percent, maximum block size, maximum pairs per type, DedupKit and DuckDB versions, build time.
