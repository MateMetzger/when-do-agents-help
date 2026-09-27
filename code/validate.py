"""Reference-free output validation.

Validation sees only the method input. Private reference diagnostics live in
evaluation.py and must not be included in the method workspace.
"""
import collections
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def strict_json(text):
    """Reject duplicate keys and nonfinite numbers, as well as invalid syntax."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (ValueError, TypeError):
        return None


def validate_audit(envelope, response):
    schema = json.loads((HERE/'schemas/audit.schema.json').read_text())
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(response)]
    if errors:
        return errors
    if (response['task_id'], response['candidate_sha256'], response['round']) != (
            envelope['task']['id'], envelope['candidate_sha256'], envelope['round']):
        errors.append('Audit does not identify this task, candidate and round')
    if response['verdict'] == 'clear' and response['issues']:
        errors.append('Clear verdict must have no outstanding issues')
    if response['verdict'] == 'revise' and not response['issues']:
        errors.append('Revise verdict must identify an actionable issue')
    if len({i['id'] for i in response['issues']}) != len(response['issues']):
        errors.append('Audit issue IDs must be unique')
    return errors


def validate(task, result, family='llm'):
    """Return structural issues; never inspect a reference alignment."""
    if family not in ('llm', 'embedding'):
        raise ValueError('Unknown method family')
    schema = json.loads((HERE/'schemas/result.schema.json').read_text())
    errors = [f'{list(e.path)}: {e.message}' for e in Draft202012Validator(schema).iter_errors(result)]
    if errors:
        return errors
    if result['task_id'] != task['id']:
        errors.append('Wrong task_id')
    source = {s['id']: s['text'] for s in task['source_segments']}
    expected_ids = list(source)
    ranks = {s: i for i, s in enumerate(expected_ids)}
    nonempty = [s for s in expected_ids if source[s]]
    english = {u['id']: u for u in result['english_units']}
    if len(english) != len(result['english_units']):
        errors.append('Duplicate English unit IDs')
    eranks = {s: i for i, s in enumerate(english)}
    covered = []; used = set()
    # English fragments form a complete ordered inventory. Only whitespace gaps
    # may occur between them. No positions are requested from the method.
    cursor = 0
    for unit in result['english_units']:
        text = unit['text']
        while cursor < len(task['english_text']) and task['english_text'][cursor].isspace():
            cursor += 1
        if not text.strip() or text != text.strip():
            errors.append(f"English {unit['id']} must contain text without outer whitespace")
        if not task['english_text'].startswith(text, cursor):
            errors.append(f"English inventory differs from input at {unit['id']}")
            break
        cursor += len(text)
    if task['english_text'][cursor:].strip():
        errors.append('English inventory does not account for the complete input')
    row_starts = []
    for row in result['source_alignments']:
        ids = row['source_ids']; targets = row['english_ids']; status = row['status']
        covered.extend(ids); used.update(targets)
        if not set(ids) <= source.keys() or not set(targets) <= english.keys():
            errors.append('Unknown source or English ID')
            continue
        row_starts.append(min(ranks[s] for s in ids))
        if family == 'llm' and len(ids) != 1:
            errors.append('LLM methods require a separate row for each source segment')
        if targets != sorted(targets, key=eranks.get):
            errors.append('English IDs within a row must follow English order')
        if family == 'embedding' and len(targets)>12:
            errors.append('Embedding baseline permits at most twelve English candidates')
        if status == 'matched':
            if not targets or any(not source[s] for s in ids):
                errors.append('Matched rows need source text and English counterparts')
            indices = [nonempty.index(s) for s in ids if source[s]]
            if indices and indices != list(range(indices[0], indices[0]+len(indices))):
                errors.append('Grouped source units must be consecutive nonempty segments')
        elif targets:
            errors.append('Only matched rows may contain English IDs')
        if status != 'matched' and len(ids) != 1:
            errors.append('Unmatched, unresolved and empty source rows are individual')
        if status == 'empty_source' and any(source[s] for s in ids):
            errors.append('Nonempty source marked empty')
        if status != 'empty_source' and any(not source[s] for s in ids):
            errors.append('Empty source slots must be marked empty_source')
    if collections.Counter(covered) != collections.Counter(expected_ids):
        errors.append('Each supplied source ID must occur exactly once')
    if row_starts != sorted(row_starts):
        errors.append('Source rows must follow source order')
    for unit in result['english_units']:
        if (unit['id'] in used) != (unit['status'] == 'aligned'):
            errors.append(f"English disposition/reference mismatch: {unit['id']}")
    return errors



if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Validate a result without reference data')
    parser.add_argument('task', type=Path); parser.add_argument('result', type=Path)
    parser.add_argument('--family', choices=['llm', 'embedding'], default='llm')
    parser.add_argument('--audit', action='store_true', help='Validate audit report against envelope')
    args = parser.parse_args()
    payload = strict_json(args.result.read_text())
    task = json.loads(args.task.read_text())
    issues = validate_audit(task, payload) if args.audit else validate(task, payload, args.family)
    print(json.dumps({'valid': not issues, 'issues': issues}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(issues))
