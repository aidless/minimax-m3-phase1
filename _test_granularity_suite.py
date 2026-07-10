"""
test_granularity_suite.py
==========================
M3 Hallucination Detector — 粒度降级测试套件

15 个测试场景, 覆盖:
  - 5 种 context 粒度 (强/中/中/中/弱)
  - K 模式 / B 模式 / confidence 模式
  - 跨上下文 (multi_design_coexistence)
  - 严格模式 (强制 HIGH)
  - 软降级 (段落 HIGH→MEDIUM)
  - 边界情况: 多 match, 同一句, 跨 H2/H3, 列表, strict

运行:
    python _test_granularity_suite.py

退出码:
    0 = 全部通过
    1 = 有失败
"""
import sys
from pathlib import Path
from collections import Counter

# 让 detector 可被 import
sys.path.insert(0, r'F:\Research\_inbox\方法论')
from mm3_hallucination_detector import detect_internal_contradictions


# ── 测试用例定义 ──────────────────────────────────────────────────
# 每个 case dict 支持字段:
#   name, text, expected, strict (False 默认), filter (str, default 'K|B')
#
# expected: list of (severity, granularity_prefix) - 按 issue 顺序匹配
# filter: 匹配哪个 type, default 'K|B' (K 冲突或 B 数量)

TEST_CASES = [
    # ─────────────────────────────────────────────────────────────
    # Case 1: 强粒度 (实验编号) - K 冲突, 不软降
    # 注意: 没有 ## 标题, 让"实验 1"成为最近 anchor
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C1_强粒度_K冲突_保持HIGH',
        'text': """实验 1: K = 3
实验 1: K = 5
""",
        'expected': [
            ('HIGH', '🟢强'),
        ],
        'description': 'K=3 + K=5 在"实验 1"上下文. 真矛盾, 强粒度, 保持 HIGH.',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 2: 中粒度 (标题) - B 冲突, 有不同用途 -> INFO
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C2_中粒度_标题_B冲突_不同用途',
        'text': """# 统计方法

## Bootstrap

Bootstrap 标准误: B = 5000
配对 Bootstrap 置信区间: B = 2000
""",
        'expected': [
            ('INFO', '🟡中'),
        ],
        'description': 'B=5000 + B=2000 在 ## Bootstrap 标题下, 用途不同 (SE vs CI), 合法多设计 -> INFO.',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 3: 中粒度 (表格) - K 冲突, 无不同用途 -> HIGH (不软降)
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C3_中粒度_表格_K冲突_保持HIGH',
        'text': """## 实验参数

| 步骤 | K 值 |
|------|------|
| Step 1 | K = 3 |
| Step 2 | K = 5 |
""",
        'expected': [
            ('HIGH', '🟡中'),
        ],
        'description': 'K=3 + K=5 在 ## 表格行. 真矛盾, 保持 HIGH (中粒度不降).',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 4: 中粒度 (列表) - B 冲突, 软降不在这里
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C4_中粒度_列表_B冲突_保持HIGH',
        'text': """## 参数列表

- 第一项: 一些描述
- 第二项: B = 5000
- 第三项: B = 2000
""",
        'expected': [
            ('HIGH', '🟡中'),  # 列表项中粒度, 不软降
        ],
        'description': 'B=5000 + B=2000 在 ## 列表项. 中粒度, 不降 HIGH.',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 5: 弱粒度 (段落) - B 冲突, 软降 HIGH -> MEDIUM
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C5_弱粒度_段落_K冲突_软降MEDIUM',
        'text': """这是一段普通文本, 没有 ## 标题, 也没有"实验 N"编号.
两个 K 值同时出现, 但上下文只是段落.

K = 3
K = 5
""",
        'expected': [
            ('MEDIUM', '🔴弱'),  # 段落弱粒度, 软降 HIGH -> MEDIUM
        ],
        'description': 'K=3 + K=5 在段落 (无标题无实验号). 软降 HIGH -> MEDIUM, 不 block phase.',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 6: 中粒度 (标题) - confidence 5-cat vs continuous, 默认 HIGH
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C6_中粒度_标题_confidence冲突_默认HIGH',
        'text': """## 置信度输出

置信度使用 5-category 分类 (5 类有序量表).
在某些部分, 也提到 c ∈ [0,1] 连续置信度.
""",
        'expected': [
            ('HIGH', '🟡中'),
        ],
        'description': '5-cat + continuous 在 ## 标题下, 无不同用途标注, 真矛盾, 保持 HIGH.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 7: 跨上下文 - E1 confidence 5-cat vs E3 continuous (不同实验, 合法多设计)
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C7_跨上下文_conflict不同实验_合法多设计',
        'text': """## 置信度输出

对 E1, 置信度是 5-category 分类 (5 类有序量表).
对 E3, 置信度是 c ∈ [0,1] 连续置信度.
""",
        'expected': [
            ('INFO', '🟢强'),  # 跨上下文, 取最具体 anchor (实验1, 实验3) = 强粒度
        ],
        'description': '5-cat (实验1) + continuous (实验3) 跨上下文, 标注不同实验, 合法多设计 -> INFO, 粒度=🟢强.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 8: 弱粒度 (段落) - confidence 冲突, 软降 HIGH -> MEDIUM
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C8_弱粒度_段落_confidence冲突_软降MEDIUM',
        'text': """这是一段普通文本, 没有 ## 标题. 同时出现了 5-category 和 continuous confidence.

置信度用 5-category 分类
置信度用 c ∈ [0,1] 连续
""",
        'expected': [
            ('MEDIUM', '🔴弱'),
        ],
        'description': 'confidence 5-cat + continuous 在段落, 无用途标注, 软降 HIGH -> MEDIUM.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 9: 严格模式 + 段落 - K 冲突, strict 强制 HIGH
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C9_严格模式_段落_K冲突_强制HIGH',
        'strict': True,
        'text': """普通段落, 无标题, 无实验号.

K = 3
K = 5
""",
        'expected': [
            ('HIGH', '🔴弱'),
        ],
        'description': '段落 K 冲突在 strict 模式: 强制保持 HIGH, 不软降. 粒度标签仍是 🔴弱.',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 10: 严格模式 + 列表 - B 冲突, strict 强制 HIGH
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C10_严格模式_列表_B冲突_强制HIGH',
        'strict': True,
        'text': """## 参数

- 第一个 B = 5000
- 第二个 B = 2000
""",
        'expected': [
            ('HIGH', '🟡中'),
        ],
        'description': '列表 B 冲突在 strict 模式: 强制保持 HIGH (不降到 INFO).',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 11: 中粒度 (标题) - confidence 5-cat 出现 3 次 + continuous 1 次
    #         测试 detector 是否能处理多 match 的情况 (都在同实验下)
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C11_中粒度_标题_confidence多次出现_同实验',
        'text': """## 实验 1

实验 1 置信度使用 5-category 分类 (5 类有序量表).
第二次测量置信度是 5-category 分类 (5 类).
第三次测量置信度是 5-category 分类 (5 类).
最终输出 c ∈ [0,1] 连续置信度.
""",
        'expected': [
            ('HIGH', '🟢强'),
        ],
        'description': '5-cat 出现 3 次 + continuous 1 次, 都在"实验 1"上下文. 真矛盾, HIGH, 强粒度.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 12: 中粒度 (标题) - confidence 5-cat + continuous 在同一段
    #         测试 detector 能否识别"同一段里的真矛盾"
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C12_中粒度_标题_confidence同一段',
        'text': """## 置信度

本系统同时支持 5-category 分类 (5 类有序量表) 一种表示.
也支持 c ∈ [0,1] 连续置信度另一种表示.
""",
        'expected': [
            ('HIGH', '🟡中'),
        ],
        'description': '5-cat + continuous 在同一段, ## 标题下. 真矛盾, HIGH.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 13: 跨粒度 - 5-cat + continuous 在 ## 标题下, 但中间有 ### 子标题
    #         测试 detector 能否处理 H2 + H3 + 同一 H2 包含不同 H3
    #         期望: 跨 ### 子节 → 跨上下文 → INFO (合法多设计)
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C13_同H2跨H3_conflict',
        'text': """## 实验 A

### 子节 1

实验 A 子节 1 置信度是 5-category 分类 (5 类有序量表).

### 子节 2

实验 A 子节 2 置信度是 c ∈ [0,1] 连续置信度.
""",
        'expected': [
            ('INFO', '🟡中'),  # 跨 ### 子节 → 跨上下文 → INFO
        ],
        'description': '5-cat 在 ### 子节1下, continuous 在 ### 子节2下, 跨 H3 子节 → 跨上下文 → INFO.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 14: 列表 - confidence 冲突 (无 ## 标题, 只有列表项, 无实验号)
    #         测试 detector 能否处理纯列表项中的 confidence 冲突
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C14_列表_confidence冲突_无标题无实验号',
        'text': """置信度设计:

- 设计 1: 5-category 分类 (5 类有序量表)
- 设计 2: c ∈ [0,1] 连续
""",
        'expected': [
            ('HIGH', '🟡中'),
        ],
        'description': '5-cat + continuous 在列表项 (无 ## 标题, 无实验号). 中粒度列表, 真矛盾, HIGH.',
        'filter': 'confidence',
    },

    # ─────────────────────────────────────────────────────────────
    # Case 15: 严格模式 + 段落 - confidence 冲突
    #         测试 strict 模式对 confidence 同样强制 HIGH
    # ─────────────────────────────────────────────────────────────
    {
        'name': 'C15_严格模式_段落_confidence冲突_强制HIGH',
        'strict': True,
        'text': """普通段落, 无标题, 无实验号.

置信度用 5-category 分类 (5 类有序量表).
置信度用 c ∈ [0,1] 连续.
""",
        'expected': [
            ('HIGH', '🔴弱'),
        ],
        'description': '段落 confidence 冲突在 strict 模式: 强制保持 HIGH, 粒度=🔴弱.',
        'filter': 'confidence',
    },
]


# ── 测试运行器 ────────────────────────────────────────────────────
def run_tests():
    """运行所有测试, 返回 (n_pass, n_fail, results)."""
    n_pass = 0
    n_fail = 0
    results = []

    for case in TEST_CASES:
        name = case['name']
        text = case['text']
        expected = case['expected']
        desc = case['description']
        strict = case.get('strict', False)
        filter_type = case.get('filter', 'K|B')

        issues = detect_internal_contradictions(text, strict=strict)
        # 过滤: K 冲突 / B 数量 / confidence 模式
        if filter_type == 'K|B':
            issues = [i for i in issues if 'K 冲突' in i['match'] or 'B 数量' in i['match']]
        elif filter_type == 'confidence':
            issues = [i for i in issues if 'confidence' in i['match'].lower() or '置信度' in i['match']]
        else:
            issues = [i for i in issues if filter_type in i['match']]

        # 简化 granularity 标签 (去除"软降级"后缀)
        def simplify_gran(g):
            if '🟢强' in g: return '🟢强'
            if '🟡中' in g: return '🟡中'
            if '🔴弱' in g: return '🔴弱'
            if '❓' in g: return '❓未知'
            return g

        # 检查每个 issue 是否匹配一个 expected
        # 容错: 跨上下文 strict issue 可能没有 granularity_label
        actual = []
        for i in issues:
            sev = i['severity']
            gran = simplify_gran(i.get('granularity_label', '❓未知'))
            actual.append((sev, gran))

        # 对比
        passed = (sorted(actual) == sorted(expected))
        result = {
            'name': name,
            'description': desc,
            'expected': expected,
            'actual': actual,
            'passed': passed,
            'issues_count': len(issues),
        }
        results.append(result)
        if passed:
            n_pass += 1
        else:
            n_fail += 1

    return n_pass, n_fail, results


def print_results(n_pass, n_fail, results):
    print('=' * 70)
    print(f'  M3 Hallucination Detector — 粒度降级测试套件')
    print(f'  时间: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    print()
    print(f'  共 {len(TEST_CASES)} 个测试, 通过 {n_pass}, 失败 {n_fail}')
    print()

    for r in results:
        icon = '✅' if r['passed'] else '❌'
        print(f'  {icon} {r["name"]}')
        print(f'    {C.DIM if r["passed"] else C.Y}{r["description"]}{C.END}')
        print(f'    {C.DIM}expected: {r["expected"]}{C.END}')
        print(f'    {C.DIM}actual:   {r["actual"]}{C.END}')
        print()

    print('=' * 70)
    if n_fail == 0:
        print(f'  {C.G}✅ 全部测试通过! 软降级逻辑生效正确.{C.END}')
    else:
        print(f'  {C.R}❌ {n_fail} 个测试失败{C.END}')
    print('=' * 70)


# ── 颜色 ──────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'
    DIM = '\033[2m'; END = '\033[0m'

def enable_ansi():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


if __name__ == '__main__':
    enable_ansi()
    n_pass, n_fail, results = run_tests()
    print_results(n_pass, n_fail, results)
    sys.exit(0 if n_fail == 0 else 1)