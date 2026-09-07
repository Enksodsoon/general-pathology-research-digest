from __future__ import annotations

import fresh_visual_preview as base
from fresh_visual_preview import *  # noqa: F401,F403

_ORIGINAL_EXTRACT_HIGHLIGHTS = base.extract_highlights


def extract_highlights(abstract: str) -> dict[str, str]:
    highlights = _ORIGINAL_EXTRACT_HIGHLIGHTS(abstract)
    sentences = base._sentences(abstract)
    auc_sentence = next((sentence for sentence in sentences if "auc" in sentence.lower()), "")
    if auc_sentence:
        highlights["result_secondary"] = auc_sentence
    return highlights


base.extract_highlights = extract_highlights


def main() -> int:
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
