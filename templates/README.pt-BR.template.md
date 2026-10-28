# Pares de produtos para matching (pt-BR)

[![validate](https://github.com/CaiqueDourado/product-matching-pairs-portuguese/actions/workflows/validate.yml/badge.svg)](https://github.com/CaiqueDourado/product-matching-pairs-portuguese/actions/workflows/validate.yml)
[![Dados: CC BY 4.0](https://img.shields.io/badge/dados-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA.md)
[![Código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-blue.svg)](LICENSE)
[![Kaggle](https://img.shields.io/badge/Kaggle-dataset%20completo-20BEFF.svg)](https://www.kaggle.com/datasets/caiquedourado/pares-matching-produtos-ptbr)

[Read in English](README.md)

**{TOTAL_PT} pares rotulados de ofertas de produtos de lojas brasileiras**, feitos para treinar e testar matching de
produtos (resolução de entidades) em português. Mais da metade são **negativos difíceis**: duas ofertas que dividem o código
de barras, a foto ou quase o nome inteiro e, mesmo assim, são produtos diferentes. **780 pares foram rotulados um a um**, para
que os métodos sejam avaliados contra uma referência que não vem das regras que montaram o resto.

| Mesmo EAN, mesmo produto | Mesmo EAN, produto diferente |
|---|---|
| Pilha de Zinco AAA Rayovac 4un. | Ferro a Vapor T-fal Fv1420 Rosa - **127v** |
| Pilha Rayovac Amarelinha Palito com 4 | Ferro a Vapor T-Fal FV1420 Rosa - **220V** |

| Mesma foto, produto diferente | Mesmo nome sem os números, produto diferente |
|---|---|
| Sapatilha com Fivela Usaflex - **35** - COCO | Shampoo Aussie Moist **865ML** |
| Sapatilha com Fivela Usaflex Coco - **34** - Coco | Shampoo Aussie Moist **180 Ml** |

As ofertas vêm do [catálogo de produtos do e-commerce brasileiro](https://github.com/CaiqueDourado/brazilian-ecommerce-products)
(114,6 milhões de ofertas, 2019–2024). Este repositório tem o script de montagem, a documentação, os 780 pares rotulados um a um e
uma amostra de {SAMPLE_PT} pares. **O dataset completo está no [Kaggle](https://www.kaggle.com/datasets/caiquedourado/pares-matching-produtos-ptbr).**

## O que é um par

Duas ofertas de **lojas diferentes** (com exceção de algumas recusas de 2019) e com **nomes diferentes**, que uma chave de
bloqueio colocou lado a lado: o mesmo código de barras, o mesmo grupo de produto de 2019, a mesma assinatura de imagem ou o
mesmo nome depois de tirar números e unidades. Cada candidato passa pelas conferências do
[DedupKit](https://github.com/CaiqueDourado/DedupKit) 0.2.0 (palavra em comum; tamanho, voltagem, cor, memória, tamanho de roupa,
quantidade, dimensões) e por uma conferência de número de modelo, e recebe um tipo e um rótulo:

| Tipo de par | Rótulo | Como foi feito | Pares | Rótulo certo nos pares conferidos |
|---|:---:|---|---:|---:|
{TYPE_TABLE_PT}

"Mesmo produto" quer dizer **o mesmo SKU**: o mesmo modelo no mesmo tamanho, cor, voltagem e embalagem. Dois tamanhos do
mesmo calçado são produtos diferentes aqui, porque têm códigos de barras diferentes.

Os rótulos de `pairs.parquet` são **aproximados (silver)**: vêm de regras. A última coluna diz quantas vezes cada regra acertou
nos pares rotulados um a um. Use os tipos com acerto alto para treinar como estão, pondere os outros e
**avalie os modelos nos pares rotulados um a um**.

## Os 780 pares rotulados um a um

[`gold/gold_pairs.csv`](gold/gold_pairs.csv): 60 pares de cada fonte de candidatos e resultado de regra de uma primeira
montagem (só da divisão de teste), lidos um a um e rotulados 1 (mesmo SKU), 0 (diferente) ou deixados em branco quando o
nome não diz o suficiente (65 pares). Os rótulos foram dados pelo Claude, um assistente de IA, seguindo regras escritas ([metodologia](docs/methodology.md#5-the-pairs-labelled-one-by-one)); não houve um segundo anotador. 164 são o mesmo produto e 551 não. A amostra foi estratificada por tipo, então tem mais
casos difíceis do que o normal: use-a para comparar métodos, não para estimar com que frequência as lojas reaproveitam códigos.

Como regras simples se saem neles ([`scripts/evaluate_gold.py`](scripts/evaluate_gold.py), [resultados](docs/gold-results.md)):

<p align="center"><img src="docs/img/gold-methods.pt-BR.png" alt="Precisão e cobertura nos pares rotulados um a um: catálogo de 2019 25%/99%, mesmo nome 100%/7%, mesmas palavras 94%/10%, sobreposição de palavras 26%/64%, conferências do DedupKit 47%/91%, mais número de modelo 83%/68%" width="820"></p>

- O catálogo de 2019 juntava quase todo candidato: achava os pares certos, mas **3 em cada 4 junções estavam erradas** no nível
  de SKU, quase sempre tamanhos e cores de um modelo deixados na mesma página.
- Nomes iguais quase sempre acertam, mas acham menos de 1 em cada 10 pares: cada loja escreve o nome do seu jeito.
- As conferências de palavra e atributos do DedupKit dobram a precisão sem perder muitos pares; somando a conferência de número
  de modelo (TB125 × TB112, PS3 × PS4, Civic 2010 × 2011), ela chega a 83%.

## Para começar

```python
import duckdb
pares = "/kaggle/input/pares-matching-produtos-ptbr/pairs.parquet"   # ou sample/pairs_sample.csv
duckdb.sql(f"""
    SELECT split, pair_type, label, count(*) AS pares
    FROM '{pares}' GROUP BY ALL ORDER BY split, pair_type
""")
treino = duckdb.sql(f"SELECT name_a, name_b, label FROM '{pares}' WHERE split = 'train'").df()
```

A divisão em treino, validação e teste é feita por **cluster** (o código, grupo, imagem ou chave de nome que gerou o par), então
o mesmo código de barras ou grupo nunca aparece em duas divisões.

## Arquivos

| Arquivo | Linhas | Conteúdo |
|---|---:|---|
| `pairs.parquet` (Kaggle) | {TOTAL_PT} | todos os pares, com nomes, marcas, lojas, preços, assinaturas de imagem, grupos de 2019 e divisão |
| `sample/pairs_sample.csv` | {SAMPLE_PT} | até 1.000 pares de cada tipo |
| `gold/gold_pairs.csv` | 780 | os pares rotulados um a um |
| `build_stats.json` | | contagens e parâmetros da montagem |

Cada coluna está no [dicionário de dados](docs/data-dictionary.pt-BR.md) ([English](docs/data-dictionary.md)).
Como os pares foram montados, passo a passo: [metodologia](docs/methodology.md) (em inglês).

## Limites

- Os rótulos aproximados vêm de regras sobre os nomes. Um par rotulado 1 ainda pode ser de dois produtos cujos nomes omitem o que muda.
- O nome só descreve o que a loja escreveu: um anúncio sem o tamanho casa com todos os tamanhos.
- Pares com nomes idênticos e pares da mesma loja ficaram de fora (são fáceis, ou o mesmo anúncio).
- As recusas de 2019 estão como a rotina antiga registrou. Cerca de metade pôde ser ligada às ofertas do catálogo; o resto tem só
  os nomes e o código.
- Preços e assinaturas de imagem estão como contexto. Não use a assinatura de imagem para prever os tipos `same_image*`: foi por
  ela que esses pares foram encontrados.

## Relacionados

- [brazilian-ecommerce-products](https://github.com/CaiqueDourado/brazilian-ecommerce-products): o catálogo de onde vêm as ofertas ([Kaggle](https://www.kaggle.com/datasets/caiquedourado/catalogo-produtos-ecommerce-brasil)).
- [DedupKit](https://github.com/CaiqueDourado/DedupKit): as regras de matching usadas para tipar os pares, em Python e .NET. A conferência de atributos da versão 0.2.0 foi escrita a partir dos erros encontrados ao rotular estes pares.
- [SimilarImageFinder](https://github.com/CaiqueDourado/SimilarImageFinder): hashes perceptuais de imagem, para casar pela foto.
- [taxonomia-google-produtos-ptbr](https://github.com/CaiqueDourado/taxonomia-google-produtos-ptbr): a taxonomia de produtos do Google em português.

## Licença

- **Dados:** CC BY 4.0 ([LICENSE-DATA.md](LICENSE-DATA.md)).
- **Código:** MIT.
- Nomes de produto, marcas e preços são informação factual coletada em lojas e em feeds públicos de afiliados. Nenhuma imagem é distribuída.
