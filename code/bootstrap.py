"""Paired cluster bootstrap for differences in equal-corpus recovery (Section 3.4).

Related texts are resampled together: Bilara texts by discourse cluster, Mishnah
chapters by tractate and 84000 texts by work; Sanskrit chapters are resampled within
each epic. All systems are scored on the same resamples, so contrasts are paired.
10,000 replicates, seed 20260915, 95% percentile intervals.
"""
import numpy as np

CORPORA = ('bilara', 'itihasa', 'sefaria', '84000')


def compare(records, left, right, replicates=10000, seed=20260915, text_sensitivity=False):
    """records: [{'id', 'corpus', 'parent', 'cluster', 'eligible', 'scores': {system: count}}].

    Returns the equal-corpus difference left - right (proportion) with its 95% interval,
    and the same per corpus. text_sensitivity resamples Mishnah and 84000 texts singly."""
    rng = np.random.default_rng(seed)
    per_corpus, draws = {}, []
    for corpus in CORPORA:
        rows = sorted((r for r in records if r['corpus'] == corpus), key=lambda r: r['id'])
        strata = {}
        for r in rows:
            n, a, b = r['eligible'], r['scores'][left], r['scores'][right]
            stratum = r['parent'] if corpus == 'itihasa' else corpus
            cluster = (r['cluster'] if corpus == 'bilara' else
                       r['id'] if corpus == 'itihasa' or text_sensitivity else r['parent'])
            group = strata.setdefault(stratum, {}).setdefault(cluster, np.zeros(3))
            group += [a, b, n]
        total = np.zeros((replicates, 3))
        for stratum in sorted(strata):
            values = np.array([strata[stratum][c] for c in sorted(strata[stratum])])
            idx = rng.integers(0, len(values), size=(replicates, len(values)))
            total += values[idx].sum(axis=1)
        delta = (total[:, 0]-total[:, 1])/total[:, 2]
        denom = sum(r['eligible'] for r in rows)
        a = sum(r['scores'][left] for r in rows)/denom
        b = sum(r['scores'][right] for r in rows)/denom
        per_corpus[corpus] = {'difference': a-b, 'ci95': np.percentile(delta, [2.5, 97.5]).tolist()}
        draws.append(delta)
    return {'difference': float(np.mean([v['difference'] for v in per_corpus.values()])),
            'ci95': np.percentile(np.mean(draws, axis=0), [2.5, 97.5]).tolist(), 'corpora': per_corpus}
