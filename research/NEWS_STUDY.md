# NEWS_STUDY (N-5) — does a news gate improve expectancy, or just cut trades?

_Generated 2026-10-02 19:44 UTC. Standing rule D-021 §6._
- Gated cells with n>=100 (MTC N): **23** -> Bonferroni p < 0.002174; DSR benchmark SR*=0.171 (>0.95).
- A gate can only reduce trades; the question is whether the kept trades are better, net of cost.

| class | tf | hz | rule + gate | base n | base expR | gated n | gated expR | p | verdict |
|---|---|---|---|--:|--:|--:|--:|--:|:--|
| oil | 1h | swing | bb_breakout+post_event | 121 | 0.0719 | 33 | 0.3974 | 0.0662 | thin-gated |
| oil | 1h | swing | roc_mom+post_event | 190 | 0.0468 | 44 | 0.3528 | 0.0580 | thin-gated |
| oil | 1h | swing | zscore_rev+post_event | 104 | 0.2894 | 15 | 0.3247 | 0.2080 | thin-gated |
| oil | 1h | swing | zscore_rev+surp_pos | 104 | 0.2894 | 63 | 0.3198 | 0.0440 | thin-gated |
| oil | 1h | intraday | zscore_rev+post_event | 118 | 0.0555 | 15 | 0.2942 | 0.1452 | thin-gated |
| oil | 1h | swing | zscore_rev+avoid_pre | 104 | 0.2894 | 104 | 0.2894 | 0.0223 | just-cuts-trades |
| oil | 1h | swing | zscore_rev+quiet | 104 | 0.2894 | 89 | 0.2843 | 0.0336 | thin-gated |
| oil | 1h | swing | donch_brk+post_event | 140 | -0.0452 | 37 | 0.2434 | 0.1622 | thin-gated |
| oil | 1h | swing | roc_mom+surp_pos | 190 | 0.0468 | 121 | 0.2046 | 0.0645 | IMPROVES |
| oil | 1h | intraday | donch_brk+surp_neg | 165 | -0.0893 | 56 | 0.1851 | 0.1324 | thin-gated |
| oil | 1h | swing | zscore_rev+surp_neg | 104 | 0.2894 | 43 | 0.1817 | 0.2062 | thin-gated |
| oil | 1h | swing | bb_breakout+surp_neg | 121 | 0.0719 | 47 | 0.1675 | 0.2172 | thin-gated |
| oil | 1h | intraday | bb_breakout+quiet | 147 | 0.0106 | 105 | 0.1391 | 0.1019 | IMPROVES |
| oil | 1h | intraday | zscore_rev+surp_pos | 118 | 0.0555 | 67 | 0.0924 | 0.2257 | thin-gated |
| oil | 1h | intraday | donch_brk+post_event | 165 | -0.0893 | 40 | 0.0853 | 0.3267 | thin-gated |
| oil | 1h | swing | bb_breakout+avoid_pre | 121 | 0.0719 | 121 | 0.0719 | 0.2912 | just-cuts-trades |
| oil | 1h | swing | bb_breakout+surp_pos | 121 | 0.0719 | 76 | 0.0619 | 0.3539 | thin-gated |
| oil | 1h | swing | bb_breakout+quiet | 121 | 0.0719 | 89 | 0.0602 | 0.3495 | thin-gated |
| oil | 1h | intraday | zscore_rev+avoid_pre | 118 | 0.0555 | 118 | 0.0555 | 0.2608 | just-cuts-trades |
| oil | 1day | intraday | roc_mom+avoid_pre | 146 | 0.0522 | 146 | 0.0522 | 0.0431 | just-cuts-trades |
| oil | 1day | intraday | roc_mom+quiet | 146 | 0.0522 | 146 | 0.0522 | 0.0431 | just-cuts-trades |
| oil | 1h | swing | donch_brk+surp_neg | 140 | -0.0452 | 51 | 0.0483 | 0.4068 | thin-gated |
| oil | 1h | intraday | roc_mom+post_event | 288 | -0.0125 | 59 | 0.0483 | 0.3648 | thin-gated |
| oil | 1h | swing | roc_mom+avoid_pre | 190 | 0.0468 | 190 | 0.0468 | 0.3296 | just-cuts-trades |
| oil | 1h | intraday | roc_mom+surp_pos | 288 | -0.0125 | 177 | 0.0456 | 0.3019 | IMPROVES |
| oil | 1h | intraday | bb_breakout+surp_neg | 147 | 0.0106 | 58 | 0.0401 | 0.3891 | thin-gated |
| oil | 1day | swing | roc_mom+avoid_pre | 113 | 0.0359 | 113 | 0.0359 | 0.3353 | just-cuts-trades |
| oil | 1day | swing | roc_mom+quiet | 113 | 0.0359 | 113 | 0.0359 | 0.3353 | just-cuts-trades |
| oil | 1h | intraday | zscore_rev+quiet | 118 | 0.0555 | 100 | 0.0239 | 0.3936 | hurts |
| oil | 1h | intraday | bb_breakout+surp_pos | 147 | 0.0106 | 91 | 0.0138 | 0.4507 | thin-gated |
| oil | 1h | intraday | bb_breakout+avoid_pre | 147 | 0.0106 | 147 | 0.0106 | 0.4517 | just-cuts-trades |
| oil | 1h | intraday | zscore_rev+surp_neg | 118 | 0.0555 | 51 | 0.0071 | 0.4772 | thin-gated |
| oil | 1day | intraday | donch_brk+avoid_pre | 149 | 0.0048 | 149 | 0.0048 | 0.4322 | just-cuts-trades |
| oil | 1day | intraday | donch_brk+quiet | 149 | 0.0048 | 149 | 0.0048 | 0.4322 | just-cuts-trades |
| oil | 1h | intraday | roc_mom+avoid_pre | 288 | -0.0125 | 288 | -0.0125 | 0.5740 | just-cuts-trades |
| oil | 1h | swing | roc_mom+quiet | 190 | 0.0468 | 162 | -0.0158 | 0.5557 | hurts |
| oil | 1h | intraday | bb_breakout+post_event | 147 | 0.0106 | 36 | -0.0235 | 0.5525 | thin-gated |
| oil | 1h | swing | donch_brk+avoid_pre | 140 | -0.0452 | 140 | -0.0452 | 0.6475 | just-cuts-trades |
| oil | 1h | intraday | roc_mom+quiet | 288 | -0.0125 | 240 | -0.0474 | 0.7424 | hurts |
| oil | 1h | intraday | donch_brk+avoid_pre | 165 | -0.0893 | 165 | -0.0893 | 0.8387 | just-cuts-trades |
| oil | 1h | intraday | donch_brk+quiet | 165 | -0.0893 | 117 | -0.1050 | 0.8402 | just-cuts-trades |
| oil | 1h | intraday | roc_mom+surp_neg | 288 | -0.0125 | 118 | -0.1082 | 0.8589 | hurts |
| oil | 1h | swing | donch_brk+surp_pos | 140 | -0.0452 | 92 | -0.1311 | 0.8164 | thin-gated |
| oil | 1h | swing | donch_brk+quiet | 140 | -0.0452 | 98 | -0.1649 | 0.8826 | thin-gated |
| oil | 1h | intraday | donch_brk+surp_pos | 165 | -0.0893 | 110 | -0.1978 | 0.9698 | hurts |
| oil | 1h | swing | roc_mom+surp_neg | 190 | 0.0468 | 79 | -0.2394 | 0.9452 | thin-gated |
| oil | 1day | intraday | donch_brk+post_event | 149 | 0.0048 | 0 | n/a | n/a | thin-gated |
| oil | 1day | intraday | donch_brk+surp_pos | 149 | 0.0048 | 0 | n/a | n/a | thin-gated |
| oil | 1day | intraday | donch_brk+surp_neg | 149 | 0.0048 | 0 | n/a | n/a | thin-gated |
| oil | 1day | swing | roc_mom+post_event | 113 | 0.0359 | 0 | n/a | n/a | thin-gated |
| oil | 1day | swing | roc_mom+surp_pos | 113 | 0.0359 | 0 | n/a | n/a | thin-gated |
| oil | 1day | swing | roc_mom+surp_neg | 113 | 0.0359 | 0 | n/a | n/a | thin-gated |
| oil | 1day | intraday | roc_mom+post_event | 146 | 0.0522 | 0 | n/a | n/a | thin-gated |
| oil | 1day | intraday | roc_mom+surp_pos | 146 | 0.0522 | 0 | n/a | n/a | thin-gated |
| oil | 1day | intraday | roc_mom+surp_neg | 146 | 0.0522 | 0 | n/a | n/a | thin-gated |

## Summary

- 55 gated cells judged against their base. 3 show improved expectancy.
- 'just-cuts-trades' = the filter removed trades without raising expectancy (a valid, common result).
- A gate is only a real edge if it also clears the MTC bar (✓MTC) — none unless marked.
