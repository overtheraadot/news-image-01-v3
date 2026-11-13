# news-image-01 v3 — "The World Today", Friday 13 November 2026

make.fun competition **news-image-01**: sum up 13 November's world news in
one image. Round-3 resubmission — the round-1 entry failed the server dev
grade because its default output directory (`./out`) is not writable in the
grader sandbox. This version fixes the output location and refreshes the
story set.

## The image

A newspaper front page, drawn from scratch with pure Python standard
library (hand-rolled zlib PNG encoder, 5x7 bitmap font). 1024x1024,
~19 KB, deterministic — two runs produce byte-identical output.

- **Lead:** Ukraine peace talks — Putin meets Witkoff and Kushner in Moscow,
  Europe gets a seat at the next round, the largest prisoner exchange yet is
  planned. Globe, dove, and the Ukrainian, EU, and US flags.
- **Vignettes:** Nvidia CEO resigns · Microsoft Mail/Teams global outage ·
  Khan Younis hospital strike kills six · Google Gemini 4 and smart-glasses
  preorder · England beat Croatia · mine hits an LNG tanker in the Strait
  of Hormuz.
- **Footer ticker:** Storm Charles batters Portugal.

## Run

```sh
python3 main.py
```

Writes `entry.png` to:

1. `$MAKEFUN_OUTPUT_DIR` when set,
2. `/output` when that directory exists (the grader sandbox mounts a
   writable `/output` and leaves the repo read-only),
3. otherwise the current directory.

No network, no clock, no files read, no unseeded randomness.
