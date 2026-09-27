"""Reproduce the paper's main quantitative results from the released data and outputs.

    python code/reproduce.py              # recovery, validity, contrasts, judge panel, agreement
    python code/reproduce.py --ceiling    # also the embedding ceiling

Every value is compared with code/expected.json (the frozen results reported in the
paper); the script ends with a summary of matches and exits with 1 on any mismatch.
"""
import argparse
import collections
import itertools
import json
from pathlib import Path

from bootstrap import compare
from score import CORPORA, ROOT, load_dataset, read_jsonl, score_file, summarize

SYSTEMS = {'labse': ('LaBSE', 'embedding'), 'f2llm-v2-1.7b': ('F2LLM-v2-1.7B', 'embedding'),
           'qwen3-embedding-8b': ('Qwen3-Embedding-8B', 'embedding'), 'mitra-e': ('MITRA-E', 'embedding'),
           'direct': ('Direct LLM', 'llm'), 'agent': ('Agent', 'llm'), 'agent-auditor': ('Agent + auditor', 'llm')}
CONTRASTS = [('agent', 'direct'), ('agent-auditor', 'agent'), ('direct', 'mitra-e')]
TOL = 1e-9
JUDGES = ('mimo', 'glm', 'luna')
LABELS = ('defensible_variation', 'minor_error', 'major_error')


def fleiss(items):
    """Fleiss' kappa for items rated by the same number of raters."""
    n, raters = len(items), len(items[0])
    share = collections.Counter(label for item in items for label in item)
    expected = sum((share[c]/(n*raters))**2 for c in LABELS)
    observed = sum(sum(v*v for v in collections.Counter(item).values()) - raters for item in items) / (n*raters*(raters-1))
    return (observed - expected)/(1 - expected)


def cohen(a, b, weighted=False):
    """Cohen's kappa; weighted uses linear weights over defensible < minor < major."""
    idx = {c: i for i, c in enumerate(LABELS)}
    w = [[abs(i-j)/2 if weighted else float(i != j) for j in range(3)] for i in range(3)]
    n, ca, cb = len(a), collections.Counter(a), collections.Counter(b)
    observed = sum(w[idx[x]][idx[y]] for x, y in zip(a, b))/n
    expected = sum(w[idx[x]][idx[y]]*ca[x]*cb[y] for x in LABELS for y in LABELS)/n**2
    return 1 - observed/expected


class Check:
    def __init__(self, expected):
        self.expected, self.n, self.bad = expected, 0, []

    def __call__(self, key, value):
        self.n += 1
        want = self.expected.get(key)
        if want is None or abs(want - value) > TOL:
            self.bad.append((key, value, want))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--ceiling', action='store_true')
    args = ap.parse_args()
    expected = json.loads((Path(__file__).parent/'expected.json').read_text(encoding='utf-8'))
    check = Check(expected)
    data = load_dataset()
    counts = {s: score_file(ROOT/'outputs'/f'{s}.jsonl', fam, data) for s, (_, fam) in SYSTEMS.items()}

    print('Reference recovery by corpus (%), primary measure; valid outputs')
    print(f"{'System':22}" + ''.join(f'{c:>10}' for c in (*CORPORA, 'equal')) + '     valid')
    for s, (name, _) in SYSTEMS.items():
        r = summarize(counts[s])
        valid = sum(v['valid'] for v in counts[s].values())
        print(f'{name:22}' + ''.join(f'{r[c]:10.2f}' for c in CORPORA) + f"{r['equal_corpus']:10.2f}{valid:6d}/452")
        for c in (*CORPORA, 'equal_corpus'):
            check(f'recovery/{s}/{c}', r[c])
        check(f'valid/{s}', valid)

    print('\nGenerative workflows under three measures (equal-corpus %)')
    for s in ('direct', 'agent', 'agent-auditor'):
        vals = {k: summarize(counts[s], k)['equal_corpus'] for k in ('primary', 'strict', 'valid_output')}
        print(f'{SYSTEMS[s][0]:22}' + '  '.join(f'{k} {v:.2f}' for k, v in vals.items()))
        for k, v in vals.items():
            check(f'measure/{s}/{k}', v)

    print('\nPaired cluster-bootstrap contrasts (points, 95% interval)')
    refs = {t: d['reference'] for t, d in data.items()}
    for measure in ('primary', 'strict', 'valid_output'):
        records = [{'id': t, 'corpus': refs[t]['corpus'], 'parent': refs[t]['parent_work'],
                    'cluster': refs[t]['bootstrap_cluster'], 'eligible': counts['direct'][t]['eligible'],
                    'scores': {s: (counts[s][t]['primary'] if counts[s][t]['valid'] else 0) if measure == 'valid_output'
                               else counts[s][t][measure] for s in SYSTEMS}} for t in data]
        for left, right in CONTRASTS:
            if measure != 'primary' and 'mitra-e' in (left, right):
                continue
            res = compare(records, left, right)
            lo, hi = (100*x for x in res['ci95'])
            print(f'{measure:12} {SYSTEMS[left][0]} - {SYSTEMS[right][0]}: {100*res["difference"]:+.2f} [{lo:+.2f}, {hi:+.2f}]')
            key = f'contrast/{measure}/{left}-{right}'
            check(key + '/difference', 100*res['difference'])
            check(key + '/low', lo)
            check(key + '/high', hi)

    print('\nJudge panel: consensus labels and defect rate (% of all units, equal-corpus)')
    labels = read_jsonl(ROOT/'outputs'/'judge_labels.jsonl')
    eligible = {c: sum(counts['direct'][t]['eligible'] for t in data if refs[t]['corpus'] == c) for c in CORPORA}
    for s in ('direct', 'agent', 'agent-auditor'):
        rows = [x for x in labels if x['workflow'] == s]
        n = {k: sum(x['consensus'] == k for x in rows) for k in ('major_error', 'minor_error', 'defensible_variation', 'unresolved')}
        rate = sum(sum(x['consensus'] in ('major_error', 'minor_error') for x in rows if refs[x['text_id']]['corpus'] == c)
                   / eligible[c] for c in CORPORA) / 4 * 100
        print(f"{SYSTEMS[s][0]:22} judged {len(rows)}  major {n['major_error']}  minor {n['minor_error']}  "
              f"defensible {n['defensible_variation']}  unresolved {n['unresolved']}  defect rate {rate:.2f}")
        for k, v in n.items():
            check(f'judge/{s}/{k}', v)
        check(f'judge/{s}/defect_rate', rate)

    print('\nJudge-defect contrasts (points of all units, 95% interval; Table G11)')
    severities = {'combined': ('major_error', 'minor_error'), 'major': ('major_error',)}
    for judge in ('consensus', *JUDGES):
        for severity, kinds in severities.items():
            defects = collections.Counter((x['text_id'], x['workflow']) for x in labels if x[judge] in kinds)
            records = [{'id': t, 'corpus': refs[t]['corpus'], 'parent': refs[t]['parent_work'],
                        'cluster': refs[t]['bootstrap_cluster'], 'eligible': counts['direct'][t]['eligible'],
                        'scores': {s: defects[(t, s)] for s in ('direct', 'agent', 'agent-auditor')}} for t in data]
            for left, right in (('direct', 'agent'), ('agent', 'agent-auditor')):
                res = compare(records, left, right)
                lo, hi = (100*x for x in res['ci95'])
                print(f'{judge:9} {severity:8} {SYSTEMS[left][0]} - {SYSTEMS[right][0]}: '
                      f'{100*res["difference"]:+.2f} [{lo:+.2f}, {hi:+.2f}]')
                key = f'judge_contrast/{judge}/{severity}/{left}-{right}'
                check(key + '/difference', 100*res['difference'])
                check(key + '/low', lo)
                check(key + '/high', hi)

    # Workflows whose input to the judges was identical were judged once (same judge_item).
    items = {(x['judge_item'], x['source_id']): tuple(x[j] for j in JUDGES) for x in labels}
    items = list(items.values())
    print(f'\nAgreement between judges over {len(items)} unique judged items (Table G12)')
    value = fleiss(items)
    print(f"Fleiss' kappa {value:.3f}")
    check('agreement/all/fleiss_kappa_nominal', value)
    for (i, a), (k, b) in itertools.combinations(enumerate(JUDGES), 2):
        x, y = [it[i] for it in items], [it[k] for it in items]
        vals = {'raw_agreement': sum(p == q for p, q in zip(x, y))/len(items),
                'cohen_kappa': cohen(x, y), 'cohen_kappa_linear_weighted': cohen(x, y, weighted=True)}
        print(f'{a}/{b}: ' + '  '.join(f'{m} {v:.3f}' for m, v in vals.items()))
        for m, v in vals.items():
            check(f'agreement/{a}-{b}/{m}', v)

    if args.ceiling:
        from ceiling import text_ceiling
        labse = {r['text_id']: r['result'] for r in read_jsonl(ROOT/'outputs'/'labse.jsonl')}
        tot = {c: [0, 0] for c in CORPORA}
        for t, d in data.items():
            tot[refs[t]['corpus']][0] += text_ceiling(d['task'], d['reference'], labse[t])
            tot[refs[t]['corpus']][1] += counts['direct'][t]['eligible']
        rates = {c: 100*a/b for c, (a, b) in tot.items()}
        rates['equal_corpus'] = sum(rates.values())/4
        print('\nEmbedding ceiling (%): ' + '  '.join(f'{c} {v:.2f}' for c, v in rates.items()))
        for c, v in rates.items():
            check(f'ceiling/{c}', v)

    print(f'\n{check.n - len(check.bad)} of {check.n} values match the paper.')
    for key, got, want in check.bad:
        print(f'  MISMATCH {key}: got {got}, expected {want}')
    raise SystemExit(1 if check.bad else 0)


if __name__ == '__main__':
    main()
