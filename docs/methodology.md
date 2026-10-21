# Methodology

How `pairs.parquet` was built from the [catalog](https://github.com/CaiqueDourado/catalogo-produtos-ecommerce-brasil).
Script: [`scripts/build_pairs.py`](../scripts/build_pairs.py) (DuckDB + [DedupKit](https://github.com/CaiqueDourado/DedupKit) 0.2.0),
about 20 minutes on a desktop over the 114.6 million offers.

## 1. Candidates

Four blocking keys, each on a 10% sample chosen by hash of the key (so the same input gives the same pairs). Keys shared by
more than 30 offers are ignored (placeholders and generic codes).

| Source | Key | Candidate pairs |
|---|---|---:|
| `code` | a code of 8+ characters not blacklisted by the catalog (`eans.ignored_in_grouping`) | 5,986,116 |
| `group` | the 2019 product group, for offers that joined it through a name or URL rule, in groups flagged `ok` | 14,584,554 |
| `image` | the image signature, when not flagged as generic (placeholder, store logo) | 9,549,208 |
| `name` | the name in lower case without accents, numbers and units (`squeeze termico acte sports` for both 500 ml and 700 ml) | 8,396,126 |

Pairs from the same store and pairs with identical names are dropped, leaving 12,897,193 candidates.

The fifth source is the table where the 2019–2022 routine logged the barcode matches it refused because the names shared
no word: 951,000 rows, 313,934 distinct pairs. Each name is linked back to an offer through the barcode and the exact
name; 157,398 pairs were linked on both sides.

## 2. Checks

Each candidate goes through three checks, in order:

1. **Shared word** (DedupKit `shares_word`): the names share a word or one contains the other (3+ letters), ignoring stopwords.
2. **Attributes** (DedupKit `attributes` / `conflict`): weight, volume, voltage (110/115/120/127 V are the same network),
   power, memory, battery, length, screen, BTU, colour (inox = prata = cromado), gender, clothing and shoe size
   (`- 38 -`, `Tamanho 40`, `(M)`), pack quantity (`Kit 3 Pares`, `c/ 50`) and dimension lists (`20x30`, `160x80 cm`).
   Two names conflict when both state an attribute and share no value.
3. **Model numbers** (in this script): tokens that mix letters and digits or have 3+ digits, after measures and
   dimensions are removed (`TB125`, `E435`, `2014`). Two names conflict when both have such tokens and none of them appears
   in the other name, spaces and punctuation ignored (`SG-102` matches `SG102`).

## 3. Types and labels

| Source | All checks pass | Attribute conflict | Model conflict | No shared word |
|---|---|---|---|---|
| code | `same_code` (1) | `same_code_attribute_conflict` (0) | left out | `same_code_no_shared_word` (0) |
| group | `same_group_name_rule` (1) | `same_group_attribute_conflict` (0) | `same_group_model_conflict` (0) | left out |
| image | `same_image` (1) | `same_image_attribute_conflict` (0) | `same_image_model_conflict` (0) | left out |
| name | left out | `similar_name_attribute_conflict` (0) | `similar_name_model_conflict` (0) | left out |
| 2019 refusals | | | | `refused_2019` (0) |

"Left out" means the rule is not reliable enough for a label:

- same barcode with different model numbers: in the pairs labelled one by one, most were the same product written with
  different reference numbers (44% right as 0);
- same name without numbers and no conflict: the names already agree, nothing new;
- same group or image with no shared word: too few to matter.

Each type is capped at 200,000 pairs, taken in hash order (a deterministic random sample). A pair of offers appears once,
under the first source that reached it.

## 4. Final cleaning and splits

The 2019 refusals are kept as the old routine logged them, so the last step orders the two offers (`offer_a < offer_b`),
drops a listing refused against itself, and keeps a pair of offers that is also in another type only once, in the other
type. Same-store refusals are kept: they happened.

`split` is decided by a hash of `cluster` (the source plus the key): 10% test, 10% valid, 80% train. All pairs found
through the same barcode, group, image or name key fall in the same split, so a model cannot see a barcode in training and
again in testing.

## 5. The pairs labelled one by one

After a first build, 60 test pairs of each type were read one by one and labelled at SKU level: 1 when the two names
describe the same model in the same size, colour, voltage and pack, 0 when they do not, empty when the names do not say
enough. Reading them showed where the rules failed: 110 V against 127 V, inox against prata, dimension lists, clothing
sizes and pack quantities. Those became DedupKit 0.2.0, and the dataset was built again with it. `gold/gold_pairs.csv`
keeps the 780 pairs with the type and silver label the current rules give them, so the agreement table in the README
measures the rules that built the published data.

The labels were assigned by Claude (Anthropic's AI assistant), reading each pair of names and applying the rule above,
during the work with the dataset's author. There was no second annotator. Where a name could be read both ways, the pair
was left unlabelled rather than guessed. Corrections are welcome as issues.
