# Dicionário de dados

[English](data-dictionary.md)

## pairs.parquet (Kaggle) e sample/pairs_sample.csv

Uma linha por par de ofertas. As colunas de oferta vêm em dupla, `_a` e `_b`, com `offer_a < offer_b` quando as duas são conhecidas.

| Coluna | Tipo | Descrição |
|---|---|---|
| pair_id | inteiro | Id do par (único) |
| split | texto | `train`, `valid` ou `test`, decidido pelo `cluster` (cerca de 80/10/10) |
| pair_type | texto | Como o par foi encontrado e o que as conferências disseram (veja a tabela no README) |
| label | inteiro | 1 = mesmo produto (mesmo SKU), 0 = diferente. Aproximado: vem de regras; o README mostra quantas vezes cada tipo acerta |
| reason | texto | Por que o par recebeu 0: o atributo que muda (`size: 38 vs 40`, `voltage_v: 127 vs 220`, `colour: preto vs branco`), os números de modelo (`model: tb125 vs tb112`), `names share no word` ou `2019: names share no word`. Vazio no rótulo 1 |
| key | texto | O valor de bloqueio que gerou o par: código de barras, id do grupo de 2019, assinatura de imagem ou nome sem números |
| cluster | texto | Fonte e chave (`c:` código, `g:` grupo, `i:` imagem, `n:` nome). Pares do mesmo cluster ficam sempre na mesma divisão |
| offer_a, offer_b | inteiro | Ids das ofertas no catálogo (`produtos.id`). Vazios nas recusas de 2019 que não puderam ser ligadas a uma oferta |
| name_a, name_b | texto | Nomes como as lojas escreveram |
| brand_a, brand_b | texto | Marca informada pela loja ou pelo feed (marketplaces costumam pôr o vendedor aqui) |
| store_a, store_b | inteiro | Ids das lojas (`lojas.id` do catálogo) |
| price_a, price_b | decimal | Preço em reais na coleta; vazio quando desconhecido |
| image_hash_a, image_hash_b | texto | Assinatura de imagem do catálogo (16×16 em cinza, SHA-256 em decimal). Valores iguais = mesmo arquivo de imagem |
| group_a, group_b | inteiro | Grupo de produto de 2019 de cada oferta (`grupos.id` do catálogo) |
| group_rule_a, group_rule_b | texto | Regra pela qual cada oferta entrou no grupo de 2019 (`group_rule_original` no catálogo) |
| name_similarity | decimal | Similaridade de Jaccard entre as palavras dos dois nomes (token keys do DedupKit), de 0 a 1 |

## gold/gold_pairs.csv

780 pares rotulados um a um (veja a metodologia).

| Coluna | Tipo | Descrição |
|---|---|---|
| gold_id | inteiro | Número da linha |
| source | texto | Como o candidato foi encontrado: `same_code`, `same_group`, `same_image`, `similar_name` ou `refused_2019` |
| pair_type | texto | O tipo que as regras de montagem dão ao par; vazio quando as regras o deixam de fora (mesmo código com números de modelo diferentes) |
| silver_label | inteiro | O rótulo que as regras dão (vazio quando deixado de fora) |
| reason | texto | Como em `pairs.parquet` |
| label | inteiro | **Rótulo manual**: 1 = mesmo SKU, 0 = diferente; vazio quando os nomes não dizem o suficiente |
| name_a, name_b, brand_a, brand_b, price_a, price_b | | Como em `pairs.parquet` |

## build_stats.json

Pares por tipo, número de candidatos, percentual amostrado, tamanho máximo de bloco, máximo de pares por tipo, versões do DedupKit e do DuckDB, tempo de montagem.
