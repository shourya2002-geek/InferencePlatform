"""Class labels.

Ships with a tiny built-in set and synthesizes the rest so the demo works
offline with a 1000-class head. In production you'd load the real ImageNet
`synset` mapping (or your domain's labels) from the model artifact bundle.
"""

from __future__ import annotations

# A handful of recognizable ImageNet labels for the low indices, so demo output
# looks plausible. Everything else falls back to a synthetic name.
_KNOWN: dict[int, str] = {
    0: "tench",
    1: "goldfish",
    2: "great_white_shark",
    3: "tiger_shark",
    4: "hammerhead",
    207: "golden_retriever",
    208: "labrador_retriever",
    281: "tabby_cat",
    285: "egyptian_cat",
    340: "zebra",
    386: "african_elephant",
    409: "analog_clock",
    504: "coffee_mug",
    817: "sports_car",
    954: "banana",
}


def label_for(index: int) -> str:
    return _KNOWN.get(index, f"class_{index}")
