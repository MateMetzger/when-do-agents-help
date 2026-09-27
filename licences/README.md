# Licence evidence

Dated copies of the licence terms under which the four corpora were used, for the
reproducibility package. Each document is kept twice:

- `raw/`: the source file exactly as served (HTML, Markdown, JSON or text);
- `pdf/`: a print-to-PDF rendering of the page, for reading.

`manifest.json` records, for every document, its URL, retrieval time (UTC), SHA-256 hash,
size and, where available, a Wayback Machine snapshot as an independent timestamp.

| Corpus | Documents |
|---|---|
| Bilara (Pāli) | SuttaCentral licensing page (CC0; root texts in the public domain; request concerning generative AI), `bilara-data` LICENSE.md |
| Itihāsa (Sanskrit) | Authors' Hugging Face dataset card (Apache-2.0) |
| Sefaria (Hebrew) | Sefaria API listing of the Mishnah Ta'anit versions with their licences; the Sefaria export files for Kulp's *Mishnah Yomit* (`CC-BY`) and the Romm Vilna 1913 Mishnah (`Public Domain`); Sefaria's application code mapping `CC-BY` to CC BY 3.0; an audit of the licence field in all 126 export files used |
| 84000 (Tibetan) | 84000 Terms of Use granting CC BY 4.0 for the translation memory |
| Licence texts | CC0 1.0, Public Domain Mark 1.0, CC BY 3.0, CC BY 4.0, Apache 2.0 |

**Independent timestamps.** On 26 September 2026 the Wayback Machine saved 12 of the
submitted URLs, listed in the manifest. It repeatedly failed (HTTP 520 or 404) for the
Itihāsa dataset card page (its raw README was saved), the Kulp export file (the Romm
export and the Sefaria API listing with both licences were saved), the Public Domain Mark
page, and every 84000 address. For 84000 the manifest instead records the file's git
provenance: `Terms_of_Use.md` has a single commit in `84000/all-data`
(`61f55bfdc5f7c9f4949613b6f4b048fa8595d364`, 21 March 2024), and the archived copy is
byte-identical to the file at that commit. Two snapshots returned by the Wayback Machine
are earlier existing captures (SuttaCentral's licensing text file, May 2026; CC0,
24 September 2026), not new ones.
