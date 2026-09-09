"""Checks on the documentation itself.

Two things have gone wrong by hand and are cheap to stop by machine: football
terms translated literally into Japanese rather than written the way the sport
writes them, and Japanese prose drifting out of its です・ます register
mid-document. Both were fixed once each and both would come back.

Standard library only, like the rest of the test suite.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def _japanese_files():
    paths = [os.path.join(ROOT, "README.ja.md")]
    paths += [os.path.join(DOCS, name) for name in sorted(os.listdir(DOCS))
              if name.endswith(".ja.md")]
    return [p for p in paths if os.path.exists(p)]


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


#: Literal translations of football terms, and what the sport writes instead.
#: The spelling on the right is the one in the JFA Laws of the Game.
WRONG_TERMS = {
    "コーナー旗": "コーナーフラッグ",
    "コーナーの旗": "コーナーフラッグ",
    "角キック": "コーナーキック",
    "隅キック": "コーナーキック",
    "罰則エリア": "ペナルティエリア",
    "自由キック": "フリーキック",
    "投げ入れ": "スローイン",
    "接触線": "タッチライン",
    "得点線": "ゴールライン",
    "中央線": "ハーフウェーライン",
    "セットプレイ": "セットプレー",
    "シュートを撃": "シュートを打",
}


class FootballTerms(unittest.TestCase):
    """Terms translated word-for-word from English do not ship."""

    def test_no_literal_translations(self):
        for path in _japanese_files():
            text = _read(path)
            lines = text.splitlines()
            for wrong, right in WRONG_TERMS.items():
                # The table in this test file is the one place the wrong form
                # is allowed to appear, so report the location rather than the
                # offending text.
                hits = [n for n, line in enumerate(lines, 1) if wrong in line]
                self.assertEqual(
                    [], hits,
                    f"{os.path.relpath(path, ROOT)} lines {hits} translate a "
                    f"football term literally; write {right} instead")


POLITE = re.compile(
    r"(です|ます|ません|でした|ました|ませんでした|でしょう|ください|ましょう)$")

PLAIN = re.compile(
    r"(?:である|であった|だった|でない|ではない|ではなかった"
    r"|[ぁ-んァ-ヶ一-龥][うくぐすずつぬぶむる]"
    r"|[ぁ-んァ-ヶ一-龥]た"
    r"|しい|たい|ない|よい|多い|少ない|高い|低い|強い|弱い|大きい|小さい"
    r"|長い|短い|早い|速い|遅い|近い|遠い|重い|軽い|にくい|やすい|正しい|新しい"
    r")$")

#: Nouns ending in a character ``PLAIN`` would otherwise claim. 体言止め is
#: allowed in either register; only plain verbs and adjectives are a departure.
NOUN_TAIL = re.compile(
    r"(?:ひとつ|一つ|二つ|三つ|四つ|五つ|いくつ|[0-9０-９]つ"
    r"|こと|もの|ため|とおり|通り|はず|まま|うち|ほう|方)$")

SKIP_LINE = re.compile(r"^\s*(#|\||```|>|!\[|\*\[|---|\d+\.\s*$)")
TAIL = re.compile(r"(?:[（(][^）)]*[)）]|\[[^\]]*\]\([^)]*\)|\*+|`[^`]*`|\s)+$")


def _sentences(text):
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip() or SKIP_LINE.match(line):
            continue
        prose = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line.strip())
        prose = prose.replace("**", "").replace("`", "")
        for sentence in re.split(r"(?<=[。])", prose):
            sentence = sentence.strip()
            if sentence.endswith("。") and len(sentence) > 4:
                yield number, sentence


def _core(sentence):
    text = sentence.rstrip().rstrip("。．")
    previous = None
    while text != previous:
        previous = text
        text = TAIL.sub("", text)
    return text


class JapaneseRegister(unittest.TestCase):
    """Every ``*.ja.md`` holds です・ます from the first line to the last."""

    def test_no_plain_form_sentences(self):
        for path in _japanese_files():
            departures = []
            for number, sentence in _sentences(_read(path)):
                core = _core(sentence)
                if POLITE.search(core) or NOUN_TAIL.search(core):
                    continue
                if PLAIN.search(core):
                    departures.append(f"L{number}: {sentence[:60]}")
            self.assertEqual(
                [], departures,
                f"{os.path.relpath(path, ROOT)} drops out of です・ます")


class LanguagePairs(unittest.TestCase):
    """An English document and its translation are added and kept together."""

    def test_every_doc_has_both_languages(self):
        english = [name for name in os.listdir(DOCS)
                   if name.endswith(".md") and not name.endswith(".ja.md")]
        for name in sorted(english):
            japanese = name[:-3] + ".ja.md"
            self.assertTrue(
                os.path.exists(os.path.join(DOCS, japanese)),
                f"docs/{name} has no docs/{japanese}")

    def test_every_doc_links_to_its_counterpart(self):
        for name in sorted(os.listdir(DOCS)):
            if not name.endswith(".md"):
                continue
            other = (name[:-6] + ".md") if name.endswith(".ja.md") else (name[:-3] + ".ja.md")
            head = _read(os.path.join(DOCS, name)).splitlines()[0]
            self.assertIn(other, head,
                          f"docs/{name} does not link to docs/{other} on its first line")


class Links(unittest.TestCase):
    """Relative links in the documentation point at files that exist."""

    def test_relative_links_resolve(self):
        pages = [os.path.join(ROOT, name) for name in os.listdir(ROOT)
                 if name.endswith(".md")]
        pages += [os.path.join(DOCS, name) for name in os.listdir(DOCS)
                  if name.endswith(".md")]
        for path in sorted(pages):
            for href in re.findall(r"\]\(([^)]+)\)", _read(path)):
                if href.startswith(("http", "#", "mailto")):
                    continue
                target = os.path.join(os.path.dirname(path), href.split("#")[0])
                self.assertTrue(
                    os.path.exists(target),
                    f"{os.path.relpath(path, ROOT)} links to a missing {href}")


if __name__ == "__main__":
    unittest.main()
