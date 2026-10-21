"""README figure: precision and recall of simple methods on the gold pairs (EN and PT).

    python scripts/make_figures.py        # after scripts/evaluate_gold.py
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
INK, MUTED, PRECISION, RECALL = "#1f1f1f", "#666666", "#2a78d6", "#eb6834"
for family in ("Inter", "DejaVu Sans"):
    try:
        matplotlib.font_manager.findfont(family, fallback_to_default=False)
        plt.rcParams["font.family"] = family
        break
    except ValueError:
        continue

spec = importlib.util.spec_from_file_location("evaluate_gold", ROOT / "scripts" / "evaluate_gold.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

LABELS = {
    "2019 catalog (merge every candidate except the refused ones)": ("2019 catalog: merge every candidate", "Catálogo de 2019: junta todo candidato"),
    "same normalized name": ("same normalized name", "mesmo nome normalizado"),
    "same token key (words, singular, no stopwords)": ("same words (token key)", "mesmas palavras (token key)"),
    "word overlap (Jaccard) >= 0.5": ("word overlap >= 0.5", "sobreposição de palavras >= 0,5"),
    "DedupKit 0.2.0 checks (shared word + attributes)": ("DedupKit 0.2.0: word + attribute check", "DedupKit 0.2.0: palavra + atributos"),
    "B2 build rules (DedupKit + model numbers; the silver labels)": ("+ model numbers (this dataset's labels)", "+ número de modelo (rótulos deste dataset)"),
}
TEXT = {
    "en": {"title": "How simple rules do on the pairs labelled one by one", "sub": "{n} candidate pairs labelled one by one · same SKU or not",
           "p": "precision", "r": "recall", "suffix": ""},
    "pt": {"title": "Como regras simples se saem nos pares conferidos um a um", "sub": "{n} pares candidatos rotulados um a um · mesmo SKU ou não",
           "p": "precisão", "r": "cobertura", "suffix": ".pt-BR"},
}


def main() -> None:
    rows = [r for r in csv.DictReader(open(ROOT / "gold" / "gold_pairs.csv", encoding="utf-8")) if r["label"] != ""]
    scores = [(name, ev.score(rows, fn)) for name, fn in ev.METHODS.items()]
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, t in TEXT.items():
        fig, ax = plt.subplots(figsize=(10, 5.0), dpi=110)
        fig.subplots_adjust(left=0.36, right=0.95, top=0.8, bottom=0.08)
        fig.text(0.02, 0.93, t["title"], fontsize=16, weight="bold", color=INK)
        fig.text(0.02, 0.87, t["sub"].format(n=len(rows)), fontsize=10.5, color=MUTED)
        ys = list(range(len(scores)))[::-1]
        h = 0.36
        for y, (name, (p, r, _f1, _acc)) in zip(ys, scores):
            ax.barh(y + h / 2, p * 100, height=h - 0.04, color=PRECISION, label=t["p"] if y == ys[0] else None)
            ax.barh(y - h / 2, r * 100, height=h - 0.04, color=RECALL, label=t["r"] if y == ys[0] else None)
            ax.text(p * 100 + 1, y + h / 2, f"{p:.0%}", va="center", fontsize=9.5, color=INK)
            ax.text(r * 100 + 1, y - h / 2, f"{r:.0%}", va="center", fontsize=9.5, color=INK)
        ax.set_yticks(ys)
        ax.set_yticklabels([LABELS[n][0 if lang == "en" else 1] for n, _ in scores], fontsize=10, color=INK)
        ax.set_xlim(0, 110)
        ax.set_xticks([])
        for s in ("top", "right", "bottom", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(left=False)
        ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.12), ncol=2, frameon=False, fontsize=10)
        fig.savefig(OUT / f"gold-methods{t['suffix']}.png", facecolor="white")
        plt.close(fig)
    print("figures written to", OUT)


if __name__ == "__main__":
    main()
