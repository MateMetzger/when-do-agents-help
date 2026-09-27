"""Text normalization profile `alignment-text-v1`, applied to system output before scoring.

It changes representation only (Unicode NFC, curly quotes and the ellipsis character to
ASCII, whitespace runs, three spaced dots) and never wording, spelling or diacritics.
The released task and reference texts are already normalized with the same profile.
"""
import re
import unicodedata

QUOTE_MAP = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'", '…': '...'})
SPACE_RUN = re.compile(r'[ \t\r\n  ]+')
DOT_RUN = re.compile(r'\.(?: *\.)+')


def normalize_text(text, corpus, side):
    """Normalize one string. corpus: bilara | itihasa | sefaria | 84000; side: source | translation.

    Raises ValueError for character contexts the profile does not cover."""
    if text is None:
        return None
    text = unicodedata.normalize('NFC', text)
    if corpus == '84000' and side == 'translation':
        text = text.replace('­', '')
        text = re.sub(r'(?<=[A-Za-z])‌(?=[ ,])', '', text)
        if '‌' in text:
            raise ValueError('Unreviewed non-joiner context')
    if corpus == '84000' and side == 'source':
        text = re.sub(r'(?<=།)​(?=།)', '', text)
        if '​' in text:
            raise ValueError('Unreviewed Tibetan zero-width-space context')
    if side == 'translation' or corpus == 'bilara':
        text = text.translate(QUOTE_MAP)
    text = SPACE_RUN.sub(' ', text).strip(' ')
    if side == 'translation' or corpus == 'bilara':
        text = DOT_RUN.sub(lambda m: '...' if m[0].count('.') == 3 else m[0], text)
    return text
