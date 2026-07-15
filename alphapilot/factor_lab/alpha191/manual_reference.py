"""Concise manual-derived formula metadata; no long source passages are copied."""

from __future__ import annotations


MANUAL_SHA256 = "45511E1C3F15EE2A5218DADA230243202A5401921F37AE686C2815822AB906A9"

REVIEWED_FORMULAS = {
    14: {
        "page": 9,
        "category": "动量反转/均值回复",
        "manual": "CLOSE-DELAY(CLOSE,5)",
        "canonical": "close - delay(close, 5)",
        "columns": ("close",),
        "operators": ("delay",),
        "windows": (5,),
    },
    15: {
        "page": 10,
        "category": "动量反转/均值回复",
        "manual": "OPEN/DELAY(CLOSE,1)-1",
        "canonical": "safe_div(open, delay(close, 1)) - 1",
        "columns": ("open", "close"),
        "operators": ("safe_div", "delay"),
        "windows": (1,),
    },
    18: {
        "page": 11,
        "category": "动量反转/均值回复",
        "manual": "CLOSE/DELAY(CLOSE,5)",
        "canonical": "safe_div(close, delay(close, 5))",
        "columns": ("close",),
        "operators": ("safe_div", "delay"),
        "windows": (5,),
    },
    20: {
        "page": 11,
        "category": "动量反转/均值回复",
        "manual": "(CLOSE-DELAY(CLOSE,6))/DELAY(CLOSE,6)*100",
        "canonical": "safe_div(close - delay(close, 6), delay(close, 6)) * 100",
        "columns": ("close",),
        "operators": ("safe_div", "delay"),
        "windows": (6,),
    },
    58: {
        "page": 24,
        "category": "动量反转/均值回复",
        "manual": "COUNT(CLOSE>DELAY(CLOSE,1),20)/20*100",
        "canonical": "safe_div(count(close > delay(close, 1), 20, 20), 20) * 100",
        "columns": ("close",),
        "operators": ("safe_div", "count", "delay"),
        "windows": (1, 20),
    },
    88: {
        "page": 34,
        "category": "动量反转/均值回复",
        "manual": "(CLOSE-DELAY(CLOSE,20))/DELAY(CLOSE,20)*100",
        "canonical": "safe_div(close - delay(close, 20), delay(close, 20)) * 100",
        "columns": ("close",),
        "operators": ("safe_div", "delay"),
        "windows": (20,),
    },
    145: {
        "page": 55,
        "category": "成交量/资金活跃",
        "manual": "(MEAN(VOLUME,9)-MEAN(VOLUME,26))/MEAN(VOLUME,12)*100",
        "canonical": "safe_div(ts_mean(volume, 9, 9) - ts_mean(volume, 26, 26), ts_mean(volume, 12, 12)) * 100",
        "columns": ("volume",),
        "operators": ("safe_div", "ts_mean"),
        "windows": (9, 12, 26),
    },
    191: {
        "page": 70,
        "category": "量价相关/协同",
        "manual": "CORR(MEAN(VOLUME,20),LOW,5)+(HIGH+LOW)/2-CLOSE",
        "canonical": "ts_corr(ts_mean(volume, 20, 20), low, 5, 5) + (high + low) / 2 - close",
        "columns": ("volume", "low", "high", "close"),
        "operators": ("ts_corr", "ts_mean"),
        "windows": (5, 20),
    },
}
