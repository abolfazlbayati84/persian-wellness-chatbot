"""
bench_mteb_embedding.py
========================
Benchmark F — MTEB-style Embedding Quality Evaluation

Tests the multilingual-e5-base model used in embeddings.py using
MTEB-style Semantic Textual Similarity (STS) evaluation on Persian pairs.

Since downloading full MTEB Persian datasets may require internet access,
this script uses:
1. A curated Persian STS-style test set (hand-crafted, representative)
2. Cosine similarity via sentence-transformers (same model as the project)

Metrics:
  - Spearman correlation (ρ) between model similarity and human similarity
  - Precision@1 for wellness-topic clustering

Aligned with:
  - MTEB: Massive Text Embedding Benchmark (Muennighoff et al., EACL 2023)
  - STS Benchmark evaluation protocol

Run:
    python scripts/bench_mteb_embedding.py
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Persian STS-style pairs (MTEB evaluation protocol)
# Human similarity scores: 0.0 (unrelated) → 1.0 (identical meaning)
# ──────────────────────────────────────────────────────────────────────────────
# Format: (sentence_a, sentence_b, human_similarity_0_to_1, label)

STS_PAIRS = [
    # High similarity (0.8–1.0)
    ("خیلی اضطراب دارم", "خیلی مضطربم", 0.95, "anxiety_paraphrase"),
    ("نمی‌تونم بخوابم", "بی‌خوابی دارم", 0.90, "sleep_paraphrase"),
    ("افسرده‌ام", "حالم خوبه نیست، انگیزه ندارم", 0.82, "depression_paraphrase"),
    ("استرس کاری دارم", "فشار کاری روی دوشمه", 0.85, "stress_paraphrase"),
    ("با دوستم قهر کردم", "با دوستم دعوا کردیم", 0.88, "relationship_paraphrase"),

    # Moderate similarity (0.4–0.7)
    ("اضطراب دارم", "نمی‌تونم بخوابم", 0.55, "anxiety_sleep_related"),
    ("افسرده‌ام", "بی‌انگیزه‌ام", 0.65, "depression_burnout_related"),
    ("استرس دارم", "کلافه‌ام", 0.60, "stress_moderate"),
    ("خستگی دارم", "بی‌رمقم", 0.62, "fatigue_related"),
    ("نگران آینده‌ام", "دلشوره دارم", 0.70, "anxiety_worry_related"),

    # Low similarity (0.0–0.3)
    ("خوابم نمیاد", "امروز هوا آفتابیه", 0.05, "sleep_weather_unrelated"),
    ("اضطراب دارم", "یه رستوران خوب معرفی کن", 0.02, "anxiety_food_unrelated"),
    ("افسرده‌ام", "ورزش چقدر مفیده", 0.10, "depression_sport_unrelated"),
    ("با دوستم دعوا کردم", "قیمت بلیت هواپیما", 0.01, "rel_travel_unrelated"),
    ("استرس کاری", "فیلم جدید ببینم", 0.03, "stress_movie_unrelated"),
]

# ──────────────────────────────────────────────────────────────────────────────
# Clustering test — BEIR-style domain separation
# Groups of texts that should cluster together
# ──────────────────────────────────────────────────────────────────────────────
CLUSTER_GROUPS = {
    "anxiety": [
        "اضطراب شدیدی دارم",
        "خیلی مضطربم و قلبم تند می‌زنه",
        "دلشوره عجیبی دارم",
        "وحشت‌زده می‌شم بدون دلیل",
    ],
    "depression": [
        "افسرده‌ام و انگیزه ندارم",
        "همش احساس پوچی می‌کنم",
        "غمگینم بدون دلیل",
        "بی‌حوصله و بی‌انگیزه‌ام",
    ],
    "sleep": [
        "نمی‌تونم بخوابم",
        "بی‌خوابی دارم",
        "کابوس می‌بینم",
        "زود بیدار می‌شم و نمی‌تونم بخوابم",
    ],
    "off_topic": [
        "امروز هوا آفتابیه",
        "یه کتاب خوب معرفی کن",
        "فردا می‌رم خرید",
        "قیمت گوشی جدید چنده",
    ],
}


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def run_sts_benchmark(model):
    print("\n" + "=" * 70)
    print("BENCHMARK F — MTEB-style STS (Semantic Textual Similarity)")
    print("  Aligned with: MTEB (Muennighoff et al., EACL 2023)")
    print("  Model: multilingual-e5-base")
    print("=" * 70)

    human_scores = []
    model_scores = []

    for sent_a, sent_b, human_sim, label in STS_PAIRS:
        emb_a = model.encode(f"query: {sent_a}", normalize_embeddings=True)
        emb_b = model.encode(f"query: {sent_b}", normalize_embeddings=True)
        model_sim = cosine_sim(emb_a, emb_b)
        human_scores.append(human_sim)
        model_scores.append(model_sim)
        print(f"  [{label:30s}] human={human_sim:.2f} model={model_sim:.3f}")

    # Spearman correlation
    from scipy.stats import spearmanr
    rho, pval = spearmanr(human_scores, model_scores)
    print(f"\n  Spearman ρ : {rho:.4f}  (p={pval:.4f})")
    print(f"  Target     : ρ ≥ 0.80")
    print(f"  Status     : {'✅' if rho >= 0.80 else '❌'}")
    return rho


def run_clustering_benchmark(model):
    print("\n" + "=" * 70)
    print("BENCHMARK E (proxy) — Domain Clustering / BEIR-style")
    print("  Tests whether same-domain texts cluster closer than cross-domain")
    print("=" * 70)

    # Encode all texts
    all_texts = []
    all_labels = []
    embeddings_by_group = {}

    for group, texts in CLUSTER_GROUPS.items():
        embs = model.encode([f"query: {t}" for t in texts], normalize_embeddings=True)
        embeddings_by_group[group] = embs
        all_texts.extend(texts)
        all_labels.extend([group] * len(texts))

    # For each group: intra-group avg sim vs inter-group avg sim
    groups = list(CLUSTER_GROUPS.keys())
    intra_sims = {}
    inter_sims = {}

    for g in groups:
        embs = embeddings_by_group[g]
        sims = []
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                sims.append(cosine_sim(embs[i], embs[j]))
        intra_sims[g] = np.mean(sims) if sims else 0

        other_sims = []
        for g2 in groups:
            if g2 == g:
                continue
            for ea in embeddings_by_group[g]:
                for eb in embeddings_by_group[g2]:
                    other_sims.append(cosine_sim(ea, eb))
        inter_sims[g] = np.mean(other_sims) if other_sims else 0

        gap = intra_sims[g] - inter_sims[g]
        status = "✅" if gap > 0.05 else "⚠️ " if gap > 0 else "❌"
        print(f"  {status} [{g:12s}] intra={intra_sims[g]:.3f}  inter={inter_sims[g]:.3f}  gap=+{gap:.3f}")

    overall_intra = np.mean(list(intra_sims.values()))
    overall_inter = np.mean(list(inter_sims.values()))
    overall_gap = overall_intra - overall_inter

    print(f"\n  Overall intra-cluster sim : {overall_intra:.3f}")
    print(f"  Overall inter-cluster sim : {overall_inter:.3f}")
    print(f"  Separation gap            : +{overall_gap:.3f}  ← target ≥ +0.05")
    print(f"  Status                    : {'✅' if overall_gap >= 0.05 else '❌'}")
    return overall_gap


def print_summary(rho, gap):
    print("\n" + "=" * 70)
    print("PAPER-READY RESULTS — Embedding Benchmark (MTEB-aligned)")
    print("=" * 70)
    print(f"""
  Table Z: Embedding Evaluation Results (multilingual-e5-base)
  ┌────────────────────────────────────┬──────────┬──────────┬──────────┐
  │ Metric                             │  Value   │  Target  │  Status  │
  ├────────────────────────────────────┼──────────┼──────────┼──────────┤
  │ STS Spearman ρ (MTEB-style)        │  {rho:.4f}  │  ≥0.800  │  {"✅" if rho >= 0.8 else "❌"}       │
  │ Domain Separation Gap (BEIR proxy) │  +{gap:.4f} │  ≥0.050  │  {"✅" if gap >= 0.05 else "❌"}       │
  └────────────────────────────────────┴──────────┴──────────┴──────────┘
""")


if __name__ == "__main__":
    print("Loading multilingual-e5-base (same model as app/services/embeddings.py)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("intfloat/multilingual-e5-base")
    print("Model loaded.\n")

    try:
        from scipy.stats import spearmanr
    except ImportError:
        print("Installing scipy...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scipy", "-q"])
        from scipy.stats import spearmanr

    rho = run_sts_benchmark(model)
    gap = run_clustering_benchmark(model)
    print_summary(rho, gap)
