"""Reference recovery for one alignment output (Section 3.4 of the paper).

A unit is a source segment whose source text and reference English are both nonempty.
It is recovered when the English its row returns equals its reference English after
normalization (strict exact). The primary measure additionally forgives punctuation
moved across a boundary with a neighbouring unit whose words also match
(local-punctuation-conservation-v1). Embedding rows may group up to three consecutive
segments and are credited only if the grouped English matches exactly.

Score a whole output file (e.g. a new system) against the released references:

    python code/score.py outputs/agent.jsonl --family llm
"""
import collections
import json
import unicodedata
from pathlib import Path

from normalize import normalize_text

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ('bilara', 'itihasa', 'sefaria', '84000')


def read_jsonl(path):
    with open(path, encoding='utf-8') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_dataset():
    """{text_id: {'task': ..., 'reference': ...}} from data/tasks.jsonl and data/references.jsonl."""
    tasks = {r['text_id']: r for r in read_jsonl(ROOT/'data'/'tasks.jsonl')}
    refs = {r['text_id']: r for r in read_jsonl(ROOT/'data'/'references.jsonl')}
    assert tasks.keys() == refs.keys()
    return {k: {'task': tasks[k]['task'], 'reference': refs[k]} for k in sorted(tasks)}


def _normalize(text, corpus):
    try:
        return normalize_text(text, corpus, 'translation')
    except ValueError:
        return None


def _edges(text):
    """(leading marks, lexical interior, trailing marks), or None if there is no interior."""
    def edge(c):
        return c.isspace() or unicodedata.category(c).startswith('P')
    a, b = 0, len(text)
    while a < b and edge(text[a]):
        a += 1
    while b > a and edge(text[b-1]):
        b -= 1
    if a == b:
        return None
    marks = lambda s: ''.join(c for c in s if not c.isspace())
    return marks(text[:a]), text[a:b], marks(text[b:])


def score(task, reference, result, family):
    """Return (eligible, strict, primary) sets of source IDs.

    task: the task object; reference: a record from data/references.jsonl;
    result: a system output; family: 'llm' (one segment per row) or 'embedding'."""
    corpus = reference['corpus']
    src = [s['id'] for s in task['source_segments']]
    stext = {s['id']: s['text'] for s in task['source_segments']}
    gold = {r['source_id']: r['english'] for r in reference['reference']}
    eligible = [s for s in src if stext[s] and gold[s]]
    E = task['english_text']
    if not isinstance(result, dict) or result.get('task_id') != task['id']:
        return eligible, set(), set()
    units, rows = result.get('english_units'), result.get('source_alignments')
    if not isinstance(units, list) or not isinstance(rows, list):
        return eligible, set(), set()
    idcount = collections.Counter(u.get('id') for u in units if isinstance(u, dict))
    good = []
    for u in units:
        if not (isinstance(u, dict) and isinstance(u.get('id'), str) and isinstance(u.get('text'), str)
                and u.get('status') in ('aligned', 'no_counterpart', 'unresolved')):
            continue
        if set(u)-{'id', 'text', 'status', 'note'} or ('note' in u and not isinstance(u['note'], str)):
            continue
        t = _normalize(u['text'], corpus)
        if t:
            good.append((u['id'], t, u['status']))
    order = {uid: i for i, (uid, _, _) in enumerate(good)}
    inventory = {uid: (t, st) for uid, t, st in good if idcount[uid] == 1}
    spans = None  # when the inventory reproduces the input, keep the input's own whitespace gaps
    if len(inventory) == len(units):
        pos, spans = 0, {}
        for uid, t, _ in good:
            while pos < len(E) and E[pos].isspace():
                pos += 1
            if not E.startswith(t, pos):
                spans = None
                break
            spans[uid] = (pos, pos+len(t))
            pos += len(t)
        if spans is not None and E[pos:].strip():
            spans = None
    srccount = collections.Counter(s for r in rows if isinstance(r, dict) and isinstance(r.get('source_ids'), list)
                                   for s in r['source_ids'] if isinstance(s, str))
    nonempty = [s for s in src if stext[s]]
    uses = collections.Counter(e for r in rows if isinstance(r, dict) and isinstance(r.get('english_ids'), list)
                               for e in r['english_ids'] if isinstance(e, str))
    scored = []
    for r in rows:
        if not isinstance(r, dict) or set(r)-{'source_ids', 'english_ids', 'status', 'note'}:
            continue
        ids, targets, status = r.get('source_ids'), r.get('english_ids'), r.get('status')
        if not (isinstance(ids, list) and ids and all(isinstance(x, str) for x in ids)):
            continue
        if not (isinstance(targets, list) and all(isinstance(x, str) for x in targets)):
            continue
        if 'note' in r and not isinstance(r['note'], str):
            continue
        if status != 'matched' or not targets or len(ids) != len(set(ids)) or len(targets) != len(set(targets)):
            continue
        if any(s not in stext or not stext[s] or srccount[s] != 1 for s in ids):
            continue
        if family == 'llm' and len(ids) != 1:
            continue
        if family == 'embedding' and (len(ids) > 3 or len(targets) > 12):
            continue
        k = [nonempty.index(s) for s in ids]
        if k != list(range(k[0], k[0]+len(k))):
            continue
        if any(e not in inventory for e in targets):
            continue
        if [order[e] for e in targets] != sorted(order[e] for e in targets):
            continue
        if any(inventory[e][1] != 'aligned' or inventory[e][0] not in E for e in targets):
            continue
        if spans is not None:
            parts, last = [], None
            for e in targets:
                a, b = spans[e]
                if last is not None:
                    gap = E[last:a]
                    parts.append(gap if not gap.strip() else ' ')
                parts.append(E[a:b])
                last = b
            actual = ''.join(parts)
        else:
            actual = ' '.join(inventory[e][0] for e in targets)
        scored.append({'ids': ids, 'targets': targets, 'actual': actual,
                       'expected': ' '.join(gold[s] for s in ids if gold[s]),
                       'pos': [order[e] for e in targets]})
    strict = set()
    for row in scored:
        if row['actual'] == row['expected']:
            strict.update(s for s in row['ids'] if gold[s])
    rank = {s: i for i, s in enumerate(src)}
    for row in scored:
        row['g'], row['a'] = _edges(row['expected']), _edges(row['actual'])
        row['movable'] = bool(row['g'] and row['a'] and row['g'][1] == row['a'][1]
                              and row['pos'] == list(range(row['pos'][0], row['pos'][-1]+1))
                              and all(uses[e] == 1 for e in row['targets']))
    scored.sort(key=lambda row: rank[row['ids'][0]])

    def adjacent(left, right):
        return (left['movable'] and right['movable'] and rank[left['ids'][-1]]+1 == rank[right['ids'][0]]
                and left['pos'][-1]+1 == right['pos'][0])

    primary = set(strict)
    for i, row in enumerate(scored):
        if not row['movable'] or row['actual'] == row['expected']:
            continue
        g, a = row['g'], row['a']
        left, right = g[0] == a[0], g[2] == a[2]
        if not left and i and adjacent(scored[i-1], row):
            p = scored[i-1]
            left = p['g'][2]+g[0] == p['a'][2]+a[0]
        if not right and i+1 < len(scored) and adjacent(row, scored[i+1]):
            n = scored[i+1]
            right = g[2]+n['g'][0] == a[2]+n['a'][0]
        if left and right:
            primary.update(s for s in row['ids'] if gold[s])
    return eligible, strict, primary


def score_file(path, family, data=None):
    """Per-text counts for one output file: {text_id: {'eligible', 'primary', 'strict', 'valid'}}."""
    from validate import validate
    data = data or load_dataset()
    out = {}
    for rec in read_jsonl(path):
        d = data[rec['text_id']]
        eligible, strict, primary = score(d['task'], d['reference'], rec['result'], family)
        valid = isinstance(rec['result'], dict) and not validate(d['task'], rec['result'], family)
        out[rec['text_id']] = {'corpus': d['reference']['corpus'], 'eligible': len(eligible),
                               'primary': len(primary), 'strict': len(strict), 'valid': valid}
    missing = set(data) - set(out)
    for t in missing:  # a missing output scores zero
        out[t] = {'corpus': data[t]['reference']['corpus'], 'eligible': sum(
            1 for s, r in zip(data[t]['task']['source_segments'], data[t]['reference']['reference'])
            if s['text'] and r['english']), 'primary': 0, 'strict': 0, 'valid': False}
    return out


def summarize(counts, key='primary'):
    """Per-corpus and equal-corpus recovery (%) from per-text counts."""
    by = {c: [0, 0] for c in CORPORA}
    for r in counts.values():
        v = r[key] if key != 'valid_output' else (r['primary'] if r['valid'] else 0)
        by[r['corpus']][0] += v
        by[r['corpus']][1] += r['eligible']
    rates = {c: 100*a/b for c, (a, b) in by.items()}
    return {**rates, 'equal_corpus': sum(rates.values())/4}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outputs', type=Path, help='JSONL with one {"text_id", "result"} per line')
    ap.add_argument('--family', choices=['llm', 'embedding'], default='llm')
    args = ap.parse_args()
    counts = score_file(args.outputs, args.family)
    for key in ('primary', 'strict', 'valid_output'):
        s = summarize(counts, key)
        print(f"{key:13}", '  '.join(f'{c}: {s[c]:.2f}' for c in (*CORPORA, 'equal_corpus')))
    print('valid outputs:', sum(r['valid'] for r in counts.values()), 'of', len(counts))
