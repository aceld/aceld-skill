# -*- coding: utf-8 -*-
"""把讲稿里的阿拉伯数字转成中文读法，避免 TTS 把「2.0」读成乱码"""
import re

D = "零一二三四五六七八九"


def _int4(n):
    """0-9999 的中文读法"""
    if n == 0:
        return "零"
    units = ["", "十", "百", "千"]
    s = ""
    digits = [int(c) for c in str(n)]
    L = len(digits)
    zero = False
    for i, d in enumerate(digits):
        u = L - i - 1
        if d == 0:
            zero = True
            continue
        if zero and s:
            s += "零"
        zero = False
        if u == 1 and d == 1 and not s:
            s += "十"
        else:
            s += D[d] + units[u]
    return s


def _int(n):
    if n < 10000:
        return _int4(n)
    if n < 100000000:
        return _int4(n // 10000) + "万" + (_int4(n % 10000) if n % 10000 else "")
    return str(n)


def _year(n):
    return "".join(D[int(c)] for c in str(n))


def _dec(s):
    """小数：整数部分用普通读法，小数点后逐位读"""
    a, b = s.split(".")
    return _int(int(a)) + "点" + "".join(D[int(c)] for c in b)


def num2cn(text):
    # 4位年份（1900-2099）逐位读
    def y(m):
        return _year(int(m.group(0)))
    text = re.sub(r"(?<![0-9.])(19|20)\d{2}(?=年)", y, text)

    # 小数
    def d(m):
        return _dec(m.group(0))
    text = re.sub(r"(?<![0-9.])\d+\.\d+(?![0-9])", d, text)

    # 普通整数
    def i(m):
        return _int(int(m.group(0)))
    text = re.sub(r"(?<![0-9.])\d+(?![0-9.])", i, text)
    return text


if __name__ == "__main__":
    tests = [
        "从1950年代到1980年代", "从2010年代到2020年代", "如果温度大于30度，就开空调",
        "可能被算成2.0、6.0、10.0、128.0、6.0", "你好，请问夏天37度",
        "一万二千二百八十八维", "置信度百分之八十五", "2026年8月",
    ]
    for t in tests:
        print(f"{t}\n  -> {num2cn(t)}")
