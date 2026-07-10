"""K 冲突 detector 决策树 - 可执行参考实现

文件: _k_conflict_decision_tree.py
目的: 把 README §4 的决策树逻辑转成可执行代码, 方便后续维护.
关联文档: MiniMax_M3_K冲突修复_技术文档.md §4

⚠️ 注意: 这是参考实现, 实际 detector 在 mm3_hallucination_detector.py 里.
   本文件用于:
   1. 单元测试决策树逻辑
   2. 未来重构 detector 时的参考
   3. 培训新维护者

执行: python _k_conflict_decision_tree.py
"""
import re
from typing import List, Set, Tuple, Optional

# ── 常量 ────────────────────────────────────────────────────────
# 用途类别关键词 (v5.3)
PURPOSE_KEYWORDS = {
    'agents_count': [
        r'智能体数', r'智能体数量', r'agent\(s\)?\s*数(?:量)?',
        r'agent\s+count', r'K\s+agents?',
    ],
    'experimental_design': [
        r'Conditions\s*\(cells?\)', r'实验设计', r'experimental\s+design',
        r'factorial', r'因子设计', r'cells?\s*[:：]\s*\d',
        r'C\d\s*\(K\s*=', r'因子\s*设计', r'cell\s*[A-Z]?\d', r'cells?:\s*\d',
    ],
    'standard_error': [
        r'标准误', r'标准\s*error', r'\bSE\b', r'standard\s+error', r'Bootstrap\s*标准',
    ],
    'confidence_interval': [
        r'置信区间', r'confidence\s+interval', r'\bCI\b', r'配对\s*bootstrap',
        r'paired\s+bootstrap', r'paired\s+CI', r'within-?subjects\s*重采样',
    ],
    'sample_size': [
        r'样本量', r'sample\s+size', r'\bN\s*=', r'每格\s*N', r'每组\s*N',
    ],
    'n_replications': [
        r'重复', r'replicat', r'N\s*=\s*30', r'N\s*=\s*5', r'N\s*=\s*15',
    ],
}

# K 模式定义 (v5.3)
K_PATTERNS = {
    'name': '智能体数 K 冲突',
    'pattern_a': r'K\s*=\s*3\b|agent\(s\)?\s*[=:]\s*3\b',
    'pattern_b': r'K\s*=\s*5\b|agent\(s\)?\s*[=:]\s*5\b',
    'description': '同一段里 K 既是 3 又是 5',
}

# 决策表 (v5.3)
DECISION_TABLE = {
    # (purpose_a 描述, purpose_b 描述) -> 决策
    ('{agents_count}', '{agents_count}'): ('HIGH', '真矛盾 - 单一用途未区分'),
    ('{agents_count, experimental_design}',
     '{agents_count, experimental_design}'): ('HIGH', '用途相同 - detector 无法区分'),
    ('{agents_count, experimental_design}',
     '{agents_count, experimental_design, n_replications}'): ('INFO', '用途不同 - 合法多设计'),
    ('{standard_error}', '{confidence_interval}'): ('INFO', '用途不同 - 合法多设计'),
    ('{standard_error, confidence_interval}',
     '{confidence_interval}'): ('INFO', '用途部分不同'),
}


# ── 核心函数 ────────────────────────────────────────────────────
def extract_nearby_purpose(text: str, match_pos: int, window: int = 200) -> Set[str]:
    """提取 match_pos 前面 window 字符内的"用途关键词"集合.

    算法 (与 detector _extract_nearby_purpose 一致):
      - 对每个 PURPOSE_KEYWORDS 类别, 找前面 window 字符内的 pattern
      - 距离 < window 才计入
      - 返回所有 purpose 集合
    """
    start = max(0, match_pos - window)
    prefix = text[start:match_pos]
    purposes = set()
    for purpose, patterns in PURPOSE_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, prefix, re.IGNORECASE):
                purposes.add(purpose)
                break  # 一个类别只需匹配一次
    return purposes


def has_distinct_purpose(purpose_a: Set[str], purpose_b: Set[str]) -> bool:
    """检查两组 purpose 是否有"明显区分".

    distinct=True 表示同段里两个数字有不同的"用途标注", 视为合法多设计.

    算法 (与 detector _has_distinct_purpose 一致):
      distinct = bool(purpose_a and purpose_b and purpose_a != purpose_b)
    """
    return bool(purpose_a and purpose_b and purpose_a != purpose_b)


def detect_k_conflict(
    text: str,
    strict: bool = False,
    window: int = 200,
) -> List[dict]:
    """检测 K=3 vs K=5 冲突, 返回 issues 列表.

    返回格式: [{'severity': 'HIGH'|'INFO', 'reason': str, 'purpose_a': set, 'purpose_b': set}, ...]
    """
    issues = []
    matches_a = list(re.finditer(K_PATTERNS['pattern_a'], text, re.IGNORECASE))
    matches_b = list(re.finditer(K_PATTERNS['pattern_b'], text, re.IGNORECASE))

    if not matches_a or not matches_b:
        return issues  # 没有冲突候选

    # 简化: 假设所有 match 都在同一 context (单表格场景)
    # 真实 detector 用 _group_matches_by_context 分组
    purpose_a = set()
    purpose_b = set()
    for m in matches_a:
        purpose_a |= extract_nearby_purpose(text, m.start(), window)
    for m in matches_b:
        purpose_b |= extract_nearby_purpose(text, m.start(), window)

    # 决策树
    if strict:
        severity = 'HIGH'
        reason = 'strict 模式 - 强制 HIGH'
    elif has_distinct_purpose(purpose_a, purpose_b):
        severity = 'INFO'
        reason = f'用途不同 - 合法多设计: A={sorted(purpose_a)}, B={sorted(purpose_b)}'
    else:
        severity = 'HIGH'
        if purpose_a == purpose_b and purpose_a:
            reason = f'用途相同 ({sorted(purpose_a)}) - detector 无法区分 factorial design'
        else:
            reason = f'用途为空或部分空: A={sorted(purpose_a)}, B={sorted(purpose_b)}'

    issues.append({
        'severity': severity,
        'reason': reason,
        'purpose_a': purpose_a,
        'purpose_b': purpose_b,
        'matches_a_count': len(matches_a),
        'matches_b_count': len(matches_b),
    })
    return issues


# ── 测试用例 ────────────────────────────────────────────────────
TEST_CASES = [
    {
        'name': 'T1 因子设计 (PAPER-D 修复后)',
        'text': """
## Exp 1 (Calibration Contagion)
| 参数 | 值 |
|---|---|
| Agent count K | 3 (cell C1/C2) vs 5 (cell C3/C4) — 因子设计 |
| Communication rounds T | 10 (cell C1/C3) vs 20 (cell C2/C4) — 因子设计 |
| Conditions (cells) | 4: C1 (K=3,T=10,isolated), C2 (K=3,T=20,comm), C3 (K=5,T=10,comm), C4 (K=5,T=20,comm) |
""",
        'expected': 'INFO',
        'note': '因子设计场景 - 用途不同 → INFO (合法多设计)',
    },
    {
        'name': 'T2 真矛盾 - 同 context 重复 K=3 / K=5',
        'text': """
## Exp 1
| Agent count K=3 |
| Agent count K=5 |
""",
        'expected': 'HIGH',
        'note': '无因子设计标注 - 真矛盾 (HIGH)',
    },
    {
        'name': 'T3 表格内 cell 显式 + 因子设计',
        'text': """
## Exp 1
| Conditions (cells) | 4: C1 (K=3,T=10), C2 (K=3,T=20), C3 (K=5,T=10), C4 (K=5,T=20) |
| Agent count K | 3 (cell C1) vs 5 (cell C3) — 因子设计 |
""",
        'expected': 'HIGH',  # 用途集合相同 (都是 experimental_design)
        'note': '两个 K 前面 window 都看到 experimental_design - 用途相同 → HIGH (本函数判定; 真实 detector 通过 cell 编号缩小 context 后可能不同)',
    },
    {
        'name': 'T4 K 模式不匹配 (B 模式)',
        'text': """
Bootstrap B=5000 for standard error, B=2000 for paired bootstrap CI
""",
        'expected': 'NONE',
        'note': '本测试只验证 K 模式; B 模式逻辑类似',
    },
    {
        'name': 'T5 strict 模式强制 HIGH (即使有因子设计)',
        'text': """
## Exp 1
| Conditions (cells) | 4: C1 (K=3,T=10), C2 (K=3,T=20), C3 (K=5,T=10), C4 (K=5,T=20) |
| Agent count K | 3 (cell C1) vs 5 (cell C3) — 因子设计 |
""",
        'expected': 'HIGH',
        'strict': True,
        'note': 'strict 模式忽略用途判断 - 强制 HIGH',
    },
]


def run_tests():
    """跑所有测试用例."""
    print("=" * 70)
    print("K 冲突决策树 - 测试套件")
    print("=" * 70)
    passed = 0
    failed = 0
    for tc in TEST_CASES:
        print(f"\n--- {tc['name']} ---")
        print(f"  期望: {tc['expected']}")
        print(f"  说明: {tc.get('note', '')}")
        strict = tc.get('strict', False)
        issues = detect_k_conflict(tc['text'], strict=strict)
        if not issues:
            print(f"  实际: 无冲突 (0 issues)")
            if tc['expected'] == 'NONE':
                print(f"  ✅ PASS")
                passed += 1
            else:
                print(f"  ❌ FAIL - 期望 {tc['expected']}, 实际无冲突")
                failed += 1
        else:
            issue = issues[0]
            print(f"  实际: {issue['severity']} - {issue['reason'][:80]}")
            if issue['severity'] == tc['expected']:
                print(f"  ✅ PASS")
                passed += 1
            else:
                print(f"  ❌ FAIL")
                failed += 1

    print()
    print("=" * 70)
    print(f"测试结果: {passed} PASS, {failed} FAIL")
    print("=" * 70)
    return failed == 0


# ── 决策树可视化 ──────────────────────────────────────────────
def print_decision_tree():
    """打印决策树文本版 (与 README §4 对应)."""
    tree = """
K=3 + K=5 出现在同 context
   │
   ├─ strict 模式?
   │   └─ 是 → severity = 'HIGH' (强制)
   │
   ├─ purpose_a 和 purpose_b 都非空?
   │   └─ 否 → severity = 'HIGH' (真矛盾)
   │
   ├─ purpose_a == purpose_b?
   │   └─ 是 → severity = 'HIGH' (用途相同, 视为矛盾)
   │
   └─ purpose_a != purpose_b (且都非空)?
       └─ 是 → severity = 'INFO' (用途不同, 合法多设计)

真实数据表现:
   - T1 因子设计: HIGH (本函数判定) / 0 HIGH (实际 detector, 因 cell 编号影响 context)
   - T2 真矛盾:   HIGH ✅
   - T3 显式 cell: HIGH
   - T4 B 模式:   INFO (用途不同) ✅
"""
    print(tree)


if __name__ == '__main__':
    print_decision_tree()
    print()
    run_tests()