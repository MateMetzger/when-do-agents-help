"""Embedding representability ceiling (Section 3.5.1).

For each text, an exact dynamic program finds the most units that any monotone
alignment over the Punkt sentence candidates could recover under strict scoring,
linking 1-3 consecutive nonempty source segments to 1-12 consecutive sentences.
It uses the reference and is a diagnostic, not a system. The sentence candidates
are the English fragments of the released LaBSE output (Punkt, NLTK 3.9.2).
"""
NEG = -10**9


def punkt_spans(task, labse_result):
    """Character spans of the Punkt sentences in the supplied English."""
    E, pos, spans = task['english_text'], 0, []
    for u in labse_result['english_units']:
        while pos < len(E) and E[pos].isspace():
            pos += 1
        assert E.startswith(u['text'], pos)
        spans.append((pos, pos+len(u['text'])))
        pos += len(u['text'])
    return spans


def ceiling(gold, english, spans, max_source=3, max_english=12):
    """gold: reference English per nonempty source segment, in order ('' if none)."""
    m, n = len(gold), len(spans)
    expected = {}
    for i in range(m):
        for a in range(1, max_source+1):
            if i+a <= m:
                members = [g for g in gold[i:i+a] if g]
                expected[i, a] = (' '.join(members), len(members))
    actual = {(j, b): english[spans[j][0]:spans[j+b-1][1]]
              for j in range(n) for b in range(1, max_english+1) if j+b <= n}
    dp = [[NEG]*(n+1) for _ in range(m+1)]
    dp[0][0] = 0
    for i in range(m+1):
        row = dp[i]
        for j in range(n+1):
            v = row[j]
            if v == NEG:
                continue
            if i < m and dp[i+1][j] < v:
                dp[i+1][j] = v
            if j < n and row[j+1] < v:
                row[j+1] = v
            for a in range(1, max_source+1):
                if i+a > m:
                    break
                text, weight = expected[i, a]
                for b in range(1, max_english+1):
                    if j+b > n:
                        break
                    s = v+(weight if weight and text == actual[j, b] else 0)
                    if dp[i+a][j+b] < s:
                        dp[i+a][j+b] = s
    return dp[m][n]


def text_ceiling(task, reference, labse_result, max_source=3, max_english=12):
    gold = [r['english'] for s, r in zip(task['source_segments'], reference['reference']) if s['text']]
    return ceiling(gold, task['english_text'], punkt_spans(task, labse_result), max_source, max_english)
