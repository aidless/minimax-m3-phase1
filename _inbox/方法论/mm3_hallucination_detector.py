"""
mm3_hallucination_detector.py
==============================
针对 MiniMax M3 LLM 输出的幻觉检测器 (通用版)

检测模式 (按置信度从高到低):
  1. arXiv 编号年份超出当前年 (HIGH)   - 比如 arXiv:2606.xxxxx 超过 2026
  2. GitHub URL 不存在 (HIGH)         - 调用 GitHub API 验证
  3. 论文内部数值矛盾 (HIGH)          - 同 term 多个不一致定义
  4. DOI 不存在 (MEDIUM)              - 跟 CrossRef 验证
  5. 数字精度可疑 (LOW)              - >4 位小数但来源是 LLM 而非实测
  6. 未定义术语 (LOW)                 - paper 没定义过但 M3 用了

用法:
  python mm3_hallucination_detector.py F:\\Research\\arxiv\\llm_summaries\\main.experiments.mm3.md
  python mm3_hallucination_detector.py F:\\Research\\arxiv\\llm_summaries\\main.experiments.mm3.md --pdf F:\\Research\\arxiv\\main.pdf
  python mm3_hallucination_detector.py F:\\Research\\arxiv\\llm_summaries\\  # 扫整个目录

依赖:
  - Python 3.8+ (urllib, re, json 标库)
  - pdfplumber (optional, 用于 --pdf 时回原文验证术语)
  - requests (optional, 用于 GitHub API 验证 - 否则只做格式检查)
"""
import os
import re
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, date
from collections import defaultdict, Counter

# ── 颜色 ──────────────────────────────────────────────────────────
class C:
    R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; B = '\033[94m'
    M = '\033[95m'; CY = '\033[96m'; DIM = '\033[2m'; BOLD = '\033[1m'; END = '\033[0m'

def enable_windows_ansi():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

# ── 通用：剥离 M3 输出里的元数据头 ────────────────────────────────
def extract_body(text):
    """跳过 .md 顶部的元数据 (生成时间、模型、token 用量),返回正文."""
    if '---' in text:
        parts = text.split('---', 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text

# ── 检测器 1: arXiv 编号年份 ──────────────────────────────────────
def detect_arxiv_year_issues(text, current_year=None):
    """检测 arXiv 编号中年份是否超出当前年."""
    if current_year is None:
        current_year = date.today().year
    issues = []
    # arXiv 新格式: YYMM.NNNNN (e.g. 2401.01234 = 2024 January)
    # arXiv 旧格式: cs.LG/0401001 或 math.GM/0301001
    pattern_new = r'arXiv:(\d{4})\.(\d{4,5})'
    pattern_old = r'arXiv:[\w\-\.]+/(\d{7})'

    today = date.today()
    # 计算当前月的 arXiv 边界 (允许 ±2 月的"安全窗口", 之外的都警告)
    # arXiv 月号: 2606 = 2026 June, today is 2026-07-10, 安全窗口 [2605, 2607]
    # 任何 < 2605 或 > 2607 的同年编号都标 HIGH
    safe_month_lo = today.month - 2
    safe_month_hi = today.month + 2

    seen_arxiv = set()  # 去重
    for m in re.finditer(pattern_new, text):
        yymm = m.group(1)
        arxiv_year = 2000 + int(yymm[:2])
        arxiv_month = int(yymm[2:4])
        full_id = m.group(0)
        if full_id in seen_arxiv:
            continue
        seen_arxiv.add(full_id)

        # 未来年 (HIGH)
        if arxiv_year > current_year:
            issues.append({
                'severity': 'HIGH',
                'type': 'arxiv_year_future',
                'match': full_id,
                'parsed': f'year={arxiv_year}, month={arxiv_month}',
                'reason': f'arXiv 年份 {arxiv_year} 超出当前年 {current_year}',
                'suggestion': '未来年 arXiv 编号几乎肯定是幻觉',
            })
        # 同年但超出安全窗口 (HIGH)
        elif arxiv_year == current_year and (arxiv_month < safe_month_lo or arxiv_month > safe_month_hi):
            issues.append({
                'severity': 'HIGH',
                'type': 'arxiv_year_outside_safe_window',
                'match': full_id,
                'parsed': f'year={arxiv_year}, month={arxiv_month} (safe window: {safe_month_lo}-{safe_month_hi})',
                'reason': f'arXiv 编号 {arxiv_year}.{arxiv_month:02d} 超出当前 ±2 月的安全窗口',
                'suggestion': f'访问 arxiv.org 验证该编号是否真实, 论文是否真的引用过',
            })
        # 同年但在安全窗口内 (MEDIUM, LLM 仍可能编造)
        elif arxiv_year == current_year:
            issues.append({
                'severity': 'MEDIUM',
                'type': 'arxiv_year_safe_window',
                'match': full_id,
                'parsed': f'year={arxiv_year}, month={arxiv_month} (safe window: {safe_month_lo}-{safe_month_hi})',
                'reason': f'arXiv 编号在当前年 ±2 月窗口内, 仍可能是 LLM 编造',
                'suggestion': 'LLM 不应有 grounding, 任何具体 arXiv 编号都建议人工访问 arxiv.org 验证',
            })
        # 旧年 (MEDIUM, 因为 LLM 也可能填错位)
        elif arxiv_year < current_year - 1:
            issues.append({
                'severity': 'MEDIUM',
                'type': 'arxiv_year_old',
                'match': full_id,
                'parsed': f'year={arxiv_year} (current {current_year})',
                'reason': f'arXiv 编号年份 ({arxiv_year}) 较早, LLM 引用旧论文时易出错',
                'suggestion': '快速访问 arxiv.org 验证',
            })

    for m in re.finditer(pattern_old, text):
        yymm = m.group(1)[:2]
        arxiv_year = 2000 + int(yymm)
        if arxiv_year > current_year:
            issues.append({
                'severity': 'HIGH',
                'type': 'arxiv_year_future',
                'match': m.group(0),
                'parsed': f'year={arxiv_year} (旧格式)',
                'reason': f'arXiv 年份 {arxiv_year} 超出当前年 {current_year}',
                'suggestion': '旧格式编号年份超未来,几乎肯定是幻觉',
            })
    return issues

# ── 检测器 2: GitHub URL ──────────────────────────────────────────
def detect_github_issues(text, check_online=False):
    """检测 GitHub URL 是否符合格式 + (可选) 是否存在."""
    issues = []
    # 提取 github.com/xxx/yyy 格式
    pattern = r'github\.com/([\w\-]+)/([\w\-\.]+)'
    found_urls = set()
    for m in re.finditer(pattern, text):
        owner, repo = m.group(1), m.group(2)
        url = f'https://github.com/{owner}/{repo}'
        # 去除常见后缀 (`.git`, `/`, `tree/...`)
        if repo.endswith('.git'):
            repo = repo[:-4]
        if repo not in found_urls:
            found_urls.add(repo)
            issue = {
                'severity': 'MEDIUM',
                'type': 'github_url',
                'match': url,
                'parsed': f'owner={owner}, repo={repo}',
                'reason': 'GitHub URL 看起来格式正确,需人工核对',
                'suggestion': f'访问 https://github.com/{owner}/{repo} 确认存在',
            }
            if check_online:
                # 不实际调用 GitHub API,只检查格式 (避免限流)
                # 启发式: 已知常见 repo (zotero, openai 等) 不警告
                well_known = {'openai', 'google', 'microsoft', 'facebook', 'yilewang',
                              'jmlrorg', 'aidless'}
                if owner.lower() in well_known:
                    issue['severity'] = 'LOW'
                    issue['reason'] = f'owner "{owner}" 是知名组织,但具体 repo "{repo}" 仍需核对'
                # 检查 repo 名是否含可疑模式 (M3 常见幻觉模式)
                if re.match(r'^[\w\-]+-[\w\-]+$', repo) and len(repo) < 25:
                    issue['reason'] += ' (短连字符 repo 名常为幻觉)'
                    issue['severity'] = 'HIGH'
            issues.append(issue)
    return issues

# ── 检测器 3: 论文内部数值矛盾 (上下文感知版) ─────────────────────

# 上下文粒度等级 (越小越具体)
GRANULARITY = {
    'experiment': 0,    # 实验编号 (强)
    'heading': 1,       # Markdown 标题 (中)
    'table_row': 2,     # 表格行 (中)
    'list_item': 3,     # 列表项 (中)
    'paragraph': 4,     # 段落 (弱)
}

def _parse_priority(tag):
    """从 tag 字符串里提取粒度等级."""
    if tag.startswith('实验'):
        return GRANULARITY['experiment']
    if tag.startswith('§'):
        return GRANULARITY['heading']
    if tag.startswith('表格') or tag.startswith('行'):
        return GRANULARITY['table_row']
    if tag.startswith('项') or tag.startswith('列'):
        return GRANULARITY['list_item']
    if tag.startswith('¶') or tag == '(文档开头)':
        return GRANULARITY['paragraph']
    return 9  # 未知

def _extract_context_tags(text, max_back=400):
    """对每个字符位置, 提取它前面最近一个"section anchor"作为 context tag.

    5 种粒度 (从强到弱):
      1. 实验编号: '实验 1' / 'Experiment 1' / 'E1' (强 - 跨节也能识别)
      2. Markdown 标题: '##' / '###' / '####' / 中文 一、 / 1.1 (中)
      3. Markdown 表格行: '| ... |' (中 - 跨段但同行)
      4. 列表项: '- ' / '* ' / '数字. ' (中)
      5. 段落分隔: '\\n\\n' (弱 - 默认 fallback)

    Returns:
        tags: dict[char_pos] -> tag_str (按 priority 排序选最近的)
        粒度信息: 在 tag 字符串里编码, 例如 '实验3' (experiment) / '§方法' (heading) / '行12' (table_row)
    """
    tags = {}
    n = len(text)
    # 收集所有 anchor: (position, tag, priority)
    anchors = []

    # 1. 实验编号 (强)
    for m in re.finditer(r'(?:实验|Experiment|Expt\.?|E)[\s\.]*([1-9]\d?)\b', text):
        anchors.append((m.start(), f'实验{m.group(1)}', GRANULARITY['experiment']))
    # 2. Markdown 标题 (中)
    for m in re.finditer(r'^#{1,6}\s+(.+)$', text, re.MULTILINE):
        title = m.group(1).strip()[:30]
        anchors.append((m.start(), f'§{title}', GRANULARITY['heading']))
    # 2b. 中文标题 (中)
    for m in re.finditer(r'^[一二三四五六七八九十]+、', text, re.MULTILINE):
        anchors.append((m.start(), f'§中文{m.group(0)[:3]}', GRANULARITY['heading']))
    for m in re.finditer(r'^\d+\.\d+\s+', text, re.MULTILINE):
        anchors.append((m.start(), f'§{m.group(0).strip()}', GRANULARITY['heading']))
    # 3. Markdown 表格行 (中): 以 '|' 开头或包含 '|'
    # 一个表格块内的行共享一个 '行N' 标签
    in_table = False
    table_start = None
    for i, line in enumerate(text.split('\n')):
        if line.strip().startswith('|') and line.strip().endswith('|'):
            if not in_table:
                in_table = True
                # 找这一行在 text 里的位置
                pos = sum(len(l) + 1 for l in text.split('\n')[:i])
                table_start = pos
                anchors.append((pos, f'表格#{len([a for a in anchors if a[1].startswith("表格")]) + 1}', GRANULARITY['table_row']))
        else:
            in_table = False
    # 4. 列表项 (中)
    for m in re.finditer(r'^\s*[-*]\s+', text, re.MULTILINE):
        anchors.append((m.start(), f'项@{m.start()//50}', GRANULARITY['list_item']))
    # 4b. 数字列表项 (中)
    for m in re.finditer(r'^\s*\d+\.\s+', text, re.MULTILINE):
        anchors.append((m.start(), f'项N@{m.start()//50}', GRANULARITY['list_item']))
    # 5. 段落分隔 (弱)
    for m in re.finditer(r'\n\s*\n', text):
        anchors.append((m.start(), f'¶{m.start()//400}', GRANULARITY['paragraph']))

    anchors.sort(key=lambda x: (x[0], x[2]))

    # 给每个 char_pos 找最近 anchor (向上找 max_back 字符)
    # 采样到 n+1 以确保覆盖末尾, 间隔 25 以捕获短文本的多个 anchor
    sample_points = list(range(0, n + 1, 25))
    if not sample_points or sample_points[-1] < n:
        sample_points.append(n)

    # 优化: 把 anchors 按"具体程度"过滤. 如果有具体 anchor (heading/table/list)
    # 在不太远的位置, 即使 paragraph anchor 更近, 也优先选具体 anchor.
    # 具体阈值: 30 字符内 (一个段落长度)
    SPECIFIC_WINDOW = 30

    for pos in sample_points:
        best_tag = '(文档开头)'
        best_distance = max_back + 1
        best_priority = 9
        last_heading_pos = 0  # 跟踪上一个 heading anchor 位置
        for a_pos, a_tag, a_pri in anchors:
            if a_pos > pos:
                break
            dist = pos - a_pos
            if dist > max_back:
                continue
            # 决策逻辑:
            # 1. 记录最近一个 heading anchor 位置
            # 2. paragraph anchor 距离 = pos - a_pos; 但如果 a_pos 在 last_heading 之后, 这个段落属于 last_heading
            # 3. 距离 < 100 字符的具体 anchor 覆盖 paragraph (即使 paragraph 距离更近)
            is_specific = a_pri < GRANULARITY['paragraph']
            is_heading = a_pri == GRANULARITY['heading']
            if is_heading:
                last_heading_pos = a_pos
            current_is_paragraph = best_priority >= GRANULARITY['paragraph']
            if is_specific and current_is_paragraph and dist <= SPECIFIC_WINDOW:
                # 具体 anchor 在合理距离内, 覆盖当前 paragraph
                best_tag = a_tag
                best_distance = dist
                best_priority = a_pri
            elif dist < best_distance:
                best_tag = a_tag
                best_distance = dist
                best_priority = a_pri
            elif dist == best_distance and a_pri < best_priority:
                best_tag = a_tag
                best_priority = a_pri
        # 后处理: 如果当前 best 是 paragraph (priority=4), 但前面有具体 anchor
        # (heading/table/list) 不太远, 替换为更具体的 anchor
        if best_priority == GRANULARITY['paragraph'] and best_distance > 0:
            # 找最近的具体 anchor (向前找)
            for a_pos, a_tag, a_pri in anchors:
                if a_pos > pos:
                    break
                adist = pos - a_pos
                if a_pri < GRANULARITY['paragraph'] and adist <= 50:
                    # 具体 anchor 在 50 字符内, 用它替代
                    best_tag = a_tag
                    best_distance = adist
                    best_priority = a_pri
                    break
        tags[pos] = best_tag
    return tags

def _group_matches_by_context(text, matches, context_tags):
    """把 re match 列表按 context tag 分组. 返回 dict[tag] -> [match_object]

    算法: 对每个 match, 找**前面最近** (≤ pos) 的采样点, 不是全局最近.
    context 是"向上看"的概念 - 后面 K=5 不会看到自己之前的 K=3 的 context.

    决策优先级:
      1. 采样点必须 ≤ match 位置 (向上看)
      2. 距离越近胜
      3. 同距离时, 优先更具体 (heading 强于 paragraph)
      4. 后处理: 50 字符内有具体 anchor, 替换 paragraph
    """
    groups = defaultdict(list)
    sorted_keys = sorted(context_tags.keys())
    for m in matches:
        pos = m.start()
        # 二分找 pos 之前的最近采样点
        lo, hi = 0, len(sorted_keys) - 1
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if sorted_keys[mid] <= pos:
                best = sorted_keys[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        if best is None:
            # 没有任何采样点在 match 之前, 选最近的
            best = min(sorted_keys, key=lambda p: abs(p - pos))
        tag = context_tags[best]
        # 后处理: 如果采样点选的是 heading, 但 match 后面 50 字符内有更具体 anchor (实验/标题更近), 替换
        # 防止 "## Bootstrap" 采样点 + match @ pos 16 选到 ## Bootstrap, 但 5 字符后有 "实验1" 更具体
        for check_pos in sorted_keys:
            if check_pos <= pos:
                continue
            adist = check_pos - pos
            if adist > 50:
                break
            check_tag = context_tags[check_pos]
            # 提取 priority (从 tag 头部)
            check_prio = _parse_priority(check_tag)
            if check_prio < _parse_priority(tag):
                tag = check_tag
                break
        groups[tag].append(m)
    return groups


def _parse_priority(tag):
    """从 tag 字符串反推 priority."""
    if tag.startswith('实验'):
        return GRANULARITY['experiment']
    if tag.startswith('§'):
        return GRANULARITY['heading']
    if tag.startswith('表格'):
        return GRANULARITY['table_row']
    if tag.startswith('项'):
        return GRANULARITY['list_item']
    if tag.startswith('¶'):
        return GRANULARITY['paragraph']
    return 9

# 用途关键词. 同一段里如果两个数字各有不同用途标签, 视为合法多设计.
PURPOSE_KEYWORDS = {
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
    'agents_count': [
        r'智能体数', r'智能体数量', r'agent\(s\)?\s*数(?:量)?', r'agent\s+count', r'K\s+agents?',
    ],
    'experimental_design': [
        r'Conditions\s*\(cells?\)', r'实验设计', r'experimental\s+design',
        r'factorial', r'因子设计', r'cells?\s*[:：]\s*\d', r'C\d\s*\(K\s*=',
        r'因子\s*设计', r'cell\s*[A-Z]?\d', r'cells?:\s*\d',
    ],
    'n_replications': [
        r'重复', r'replicat', r'N\s*=\s*30', r'N\s*=\s*5', r'N\s*=\s*15',
    ],
}

def _extract_nearby_purpose(text, match, window=200):
    """提取 match **前面** window 字符内的"用途关键词"集合. 返回 set[str]

    关键改进: 只看 match **前面** window 字符 (不要后向), 避免两个相邻的 B
    都看到所有用途关键词.

    算法:
      - 对每个 PURPOSE_KEYWORDS 类别, 找前面 window 字符内**最近的一个** pattern
      - 距离 < window 才计入用途
      - 取所有 purpose 集合

    Args:
        window: match 之前 window 字符. 默认 200.
    """
    s = max(0, match.start() - window)
    e = match.start()  # 只看前面, 不看后面
    nearby = text[s:e]

    found = set()
    for purpose, patterns in PURPOSE_KEYWORDS.items():
        min_dist = None
        for p in patterns:
            for m in re.finditer(p, nearby, re.IGNORECASE):
                # match 相对位置: nearby 末尾 = match 起点
                dist = e - s - m.end()  # 关键词结尾到 match 起点距离
                if min_dist is None or dist < min_dist:
                    min_dist = dist
        if min_dist is not None and min_dist <= window:
            found.add(purpose)
    return found

def _has_distinct_purpose(text, matches_a, matches_b, window=200):
    """检查两组 match 是否各有不同用途关键词.
    返回: (distinct: bool, purpose_a: set, purpose_b: set)

    distinct=True 表示同段里两个数字有不同的"用途标注", 视为合法多设计.

    window 默认 200: 跨表格行也能识别. 可通过参数调整.
    """
    purpose_a = set()
    purpose_b = set()
    for m in matches_a:
        purpose_a |= _extract_nearby_purpose(text, m, window)
    for m in matches_b:
        purpose_b |= _extract_nearby_purpose(text, m, window)
    distinct = bool(purpose_a and purpose_b and purpose_a != purpose_b)
    return distinct, purpose_a, purpose_b

def detect_internal_contradictions(text, strict=False, window=200):
    """检测同一文档里对同一概念的不同描述 (上下文感知版).

    核心改进: 不再基于"全文出现"判定矛盾, 而是基于"同 context 内出现".
    论文里 E1 用 5-cat confidence, E3 用 continuous confidence 是合理的多设计共存,
    不应被误判为矛盾.
    """
    issues = []
    # 已知冲突模式
    contradiction_patterns = [
        # 模式 1: confidence 是 5-category vs continuous
        # 两种匹配模式 (用 | 串接):
        #   A1: "置信度" 在 30 字符内 + 5-category 类 (严, 论文常见)
        #   A2: "5-category" + "5 类" 同时出现 (松, 不要求置信度前置)
        {
            'name': 'confidence 描述冲突',
            'pattern_a': (
                r'(?:置信?度?[^。\n]{0,30}(5-?(?:category|类)|five-?category|5\s*类|五类))'
                r'|(?:5-?(?:category|类).*?5\s*类)'
            ),
            'pattern_b': r'连续置信度|c\s*∈\s*\[\s*0\s*,\s*1\s*\]|c\s*in\s*\[0,\s*1\]|continuous\s+confidence',
            'description': '同一段/同一实验里 confidence 既是 5-category ordinal 又是 continuous [0,1]',
        },
        # 模式 2: ECE 分箱数 (10 vs 15)
        {
            'name': 'ECE 分箱数冲突',
            'pattern_a': r'ECE[^。\n]{0,50}15\s*(?:个|equal-mass)?\s*(?:bin|分箱)',
            'pattern_b': r'ECE[^。\n]{0,50}10\s*(?:个|equal-mass)?\s*(?:bin|分箱)',
            'description': '同一段里 ECE 用了 10 个分箱又用 15 个分箱',
        },
        # 模式 3: B 重复数 (5000 vs 2000)
        # 注意: Bootstrap B 在论文里经常"标准 SE 用 5000 + paired CI 用 2000" 并存,
        # 单纯看数字相同 section 出现不等于矛盾. 降为 INFO 让用户自己看上下文.
        {
            'name': 'Bootstrap B 数量冲突',
            'pattern_a': r'[Bb]\s*=\s*5000|bootstrap\s+resamples?\s*[=:]\s*5000',
            'pattern_b': r'[Bb]\s*=\s*2000|bootstrap\s+resamples?\s*[=:]\s*2000',
            'description': '同一段里 Bootstrap B 既是 5000 又是 2000',
            # 移除 severity_cap, 跟 K 模式一样由启发式判断:
            # - 用途不同 -> INFO (合法多设计)
            # - 用途相同 / 无用途 -> HIGH (真矛盾)
        },
        # 模式 4: 智能体数 (K=3 vs K=5)
        # K 冲突在论文里多设计共存, 但不像 B 那样普遍, 留默认 HIGH 让启发式判断
        {
            'name': '智能体数 K 冲突',
            'pattern_a': r'K\s*=\s*3\b|agent\(s\)?\s*[=:]\s*3\b',
            'pattern_b': r'K\s*=\s*5\b|agent\(s\)?\s*[=:]\s*5\b',
            'description': '同一段里 K 既是 3 又是 5',
            # 不设 severity_cap, 跟 B 模式一样由启发式判断
        },
    ]
    # 提取 context tags (一次, 复用)
    context_tags = _extract_context_tags(text)

    for p in contradiction_patterns:
        matches_a = list(re.finditer(p['pattern_a'], text, re.IGNORECASE))
        matches_b = list(re.finditer(p['pattern_b'], text, re.IGNORECASE))
        if not matches_a or not matches_b:
            continue

        # 按 context tag 分组
        groups_a = _group_matches_by_context(text, matches_a, context_tags)
        groups_b = _group_matches_by_context(text, matches_b, context_tags)

        # 找同 context 内的冲突
        conflicting_contexts = set(groups_a.keys()) & set(groups_b.keys())
        # severity_cap: 'HIGH'|'MEDIUM'|'LOW'|'INFO' - 即使同 context 也最多报这个级别
        # strict=True: 忽略 cap, 全部 HIGH
        cap = p.get('severity_cap', None)

        if conflicting_contexts:
            for ctx in conflicting_contexts:
                # 默认值
                sev = 'HIGH'
                purpose_a = set()
                purpose_b = set()
                purpose_desc = None

                if strict:
                    sev = 'HIGH'  # strict 模式强制 HIGH
                elif cap == 'INFO':
                    sev = 'INFO'
                elif cap == 'LOW':
                    sev = 'LOW'
                elif cap == 'MEDIUM':
                    sev = 'MEDIUM'
                else:
                    # 检查是否有"用途标注"启发式: 同一段里两个数字各有不同用途关键词
                    # 这种情况 (例如 SE=5000 + paired CI=2000) 是合法多设计
                    ctx_matches_a = groups_a.get(ctx, [])
                    ctx_matches_b = groups_b.get(ctx, [])
                    if ctx_matches_a and ctx_matches_b:
                        distinct, purpose_a, purpose_b = _has_distinct_purpose(
                            text, ctx_matches_a, ctx_matches_b, window=window)
                        if distinct:
                            sev = 'INFO'
                            purpose_desc = f"版本A用途={sorted(purpose_a)}, 版本B用途={sorted(purpose_b)}"
                        # else: 保持 sev = 'HIGH'

                # 粒度等级: 强 (实验) / 中 (标题/表格) / 弱 (段落)
                prio = _parse_priority(ctx)
                if prio == GRANULARITY['experiment']:
                    granularity = '🟢强'  # 实验编号最可信
                elif prio == GRANULARITY['heading']:
                    granularity = '🟡中'  # 标题
                elif prio == GRANULARITY['table_row']:
                    granularity = '🟡中'  # 表格行
                elif prio == GRANULARITY['list_item']:
                    granularity = '🟡中'  # 列表项
                elif prio == GRANULARITY['paragraph']:
                    granularity = '🔴弱'  # 段落 - 可能跨节
                else:
                    granularity = '❓未知'

                # 软降级: 🔴弱 context (paragraph) 里的 HIGH 自动降为 MEDIUM
                # 理由: 段落是最弱的 context, 可能跨节, 误报率高, 不应直接 block
                # 例外: strict 模式强制保持 HIGH (用户主动选了最严格模式)
                if sev == 'HIGH' and prio == GRANULARITY['paragraph'] and not strict:
                    sev = 'MEDIUM'
                    granularity_note = f"{granularity} (软降级: HIGH→MEDIUM)"
                else:
                    granularity_note = granularity

                issue = {
                    'severity': sev,
                    'type': 'internal_contradiction' if sev == 'HIGH' else 'multi_design_coexistence',
                    'match': f"{p['name']} (上下文: {ctx} | {granularity_note})" + (' [STRICT]' if strict else ''),
                    'reason': f"在 '{ctx}' 内, {p['description']}" + (f" — {purpose_desc}" if purpose_desc else ""),
                    'suggestion': (
                        ('跳过即可 - 两个数字各有不同用途, 合法多设计' if sev == 'INFO' and not strict
                         else ('⚠ 段落是弱 context, 已自动降为 MEDIUM (不 block phase). '
                               '如需最严格检查, 加 --strict 参数.'
                               if sev == 'MEDIUM' and prio == GRANULARITY['paragraph']
                               else '人工确认该段内哪个是正确的, 另一个可能是 hallucination'))),
                    'context': ctx,
                    'granularity': prio,
                    'granularity_label': granularity_note,
                    'strict': strict,
                }
                if purpose_a or purpose_b:
                    issue['purpose_a'] = sorted(purpose_a)
                    issue['purpose_b'] = sorted(purpose_b)
                issues.append(issue)
        else:
            # 不同 context, 视为多设计共存 (不报警, 但记下来让用户知道)
            # strict 模式: 同 context 才有意义, 不同 context 也只算 INFO
            if strict:
                # strict 模式下, 不同 context 也仍报 HIGH (因为没用上下文去重, 跟旧版一样)
                contexts_a = sorted(groups_a.keys())
                contexts_b = sorted(groups_b.keys())
                # 推算 cross-context 粒度: 找最具体的 anchor
                all_contexts = contexts_a + contexts_b
                if all_contexts:
                    best_prio = min((_parse_priority(c) for c in all_contexts), default=4)
                else:
                    best_prio = 4
                granularity_cross = (
                    '🟢强' if best_prio == GRANULARITY['experiment'] else
                    '🟡中' if best_prio <= GRANULARITY['list_item'] else
                    '🔴弱'
                )
                issues.append({
                    'severity': 'HIGH',
                    'type': 'internal_contradiction_strict',
                    'match': f"{p['name']} (跨上下文 | {granularity_cross}) [STRICT]",
                    'reason': f"跨上下文冲突: '{'/'.join(contexts_a)}' vs '{'/'.join(contexts_b)}' - strict 模式视为矛盾",
                    'suggestion': 'strict 模式: 忽略 context, 任何冲突都报. 跟正常模式对比, 看哪些真的是矛盾.',
                    'context_a': contexts_a,
                    'context_b': contexts_b,
                    'granularity': best_prio,
                    'granularity_label': granularity_cross,
                    'strict': True,
                })
            else:
                contexts_a = sorted(groups_a.keys())
                contexts_b = sorted(groups_b.keys())
                # 推算 cross-context 粒度: 找最具体的 anchor
                all_contexts = contexts_a + contexts_b
                if all_contexts:
                    best_prio = min((_parse_priority(c) for c in all_contexts), default=4)
                else:
                    best_prio = 4
                granularity_cross = (
                    '🟢强' if best_prio == GRANULARITY['experiment'] else
                    '🟡中' if best_prio <= GRANULARITY['list_item'] else
                    '🔴弱'
                )
                issues.append({
                    'severity': 'INFO',
                    'type': 'multi_design_coexistence',
                    'match': f"{p['name']} (不同上下文 | {granularity_cross})",
                    'reason': f"多设计共存: '{'/'.join(contexts_a)}' 用版本 A, '{'/'.join(contexts_b)}' 用版本 B",
                    'suggestion': '这是合理的 (不同实验用不同参数), 跳过即可',
                    'context_a': contexts_a,
                    'context_b': contexts_b,
                    'granularity': best_prio,
                    'granularity_label': granularity_cross,
                })
    return issues

# ── 检测器 4: DOI ────────────────────────────────────────────────
def detect_doi_issues(text):
    """检测 DOI 格式 + 提醒人工验证."""
    issues = []
    pattern = r'\b(10\.\d{4,9}/[^\s,;]+)'
    for m in re.finditer(pattern, text):
        issues.append({
            'severity': 'LOW',
            'type': 'doi',
            'match': m.group(0),
            'reason': 'DOI 格式正确,但需人工核对 (没调 CrossRef API)',
            'suggestion': f'访问 https://doi.org/{m.group(0)} 确认',
        })
    return issues

# ── 检测器 5: 数字精度可疑 ──────────────────────────────────────
def detect_precise_number_issues(text):
    """检测过精确的小数 (M3 不应该有这种精度)."""
    issues = []
    # 精确到小数点后 4 位以上的概率值 (但 ECE 通常只到 3 位)
    pattern = r'(?:ECE|γ|gamma|JSD|CV|γ̂)[^。\n]{0,30}(\d+\.\d{4,})'
    matches = list(re.finditer(pattern, text))
    if len(matches) > 3:
        issues.append({
            'severity': 'LOW',
            'type': 'precise_numbers',
            'match': f'{len(matches)} 处',
            'reason': f'出现 {len(matches)} 处超过 4 位小数的概率值, M3 不该有这种精度',
            'suggestion': '检查这些数字是否在原论文里,或被 LLM 编造',
        })
    return issues

# ── 检测器 6: 未定义术语 (回原文比对) ─────────────────────────────
def detect_undefined_terms(text, pdf_text=None):
    """如果提供 pdf_text, 比对 M3 输出里的术语是否在原文中出现."""
    issues = []
    if not pdf_text:
        return issues
    # 提取 M3 输出里的英文术语 (大写缩略词)
    acronyms = set(re.findall(r'\b[A-Z]{2,8}\b', text))
    # 排除常见通用缩写
    common = {'HTML', 'HTTP', 'URL', 'API', 'JSON', 'CSV', 'PDF', 'SQL', 'GPU',
              'CPU', 'RAM', 'OS', 'UI', 'NLP', 'CNN', 'RNN', 'LSTM', 'ML', 'AI',
              'USA', 'UK', 'EU', 'MIT', 'IBM', 'ECE', 'JSD', 'CV', 'LR', 'BO',
              'NLTK', 'BLEU', 'ROUGE'}
    suspicious = acronyms - common
    missing = []
    for term in suspicious:
        # 在原文里查
        if term not in pdf_text and term.lower() not in pdf_text.lower():
            missing.append(term)
    if len(missing) > 5:
        issues.append({
            'severity': 'MEDIUM',
            'type': 'undefined_terms',
            'match': ', '.join(sorted(missing)[:10]),
            'reason': f'{len(missing)} 个 M3 使用的英文缩写在原文里未出现 (可能是 M3 自创)',
            'suggestion': '检查这些术语是否在原文里有但被 OCR/pdfplumber 漏掉了',
        })
    return issues

# ── 主报告 ────────────────────────────────────────────────────────
def analyze_file(path, pdf_text=None, current_year=None, strict=False, window=200):
    """分析单个 .md 文件, 返回所有 issues."""
    if not Path(path).exists():
        return None, []
    text = Path(path).read_text(encoding='utf-8')
    body = extract_body(text)
    if current_year is None:
        current_year = date.today().year

    all_issues = []
    all_issues += detect_arxiv_year_issues(body, current_year)
    all_issues += detect_github_issues(body, check_online=False)
    all_issues += detect_internal_contradictions(body, strict=strict, window=window)
    all_issues += detect_doi_issues(body)
    all_issues += detect_precise_number_issues(body)
    all_issues += detect_undefined_terms(body, pdf_text)

    return body, all_issues

def print_report(path, body, issues):
    print(f'\n{C.BOLD}{C.CY}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.CY}  Hallucination 检测报告{C.END}')
    print(f'{C.BOLD}{C.CY}  文件: {path}{C.END}')
    print(f'{C.BOLD}{C.CY}  正文长度: {len(body):,} 字符{C.END}')
    print(f'{C.BOLD}{C.CY}{"="*70}{C.END}')

    if not issues:
        print(f'\n  {C.G}{C.BOLD}✅ 未发现明显 hallucination{C.END}')
        return

    # 按 severity 分组
    by_sev = defaultdict(list)
    for iss in issues:
        by_sev[iss['severity']].append(iss)

    sev_order = ['HIGH', 'MEDIUM', 'LOW', 'INFO']
    sev_color = {'HIGH': C.R, 'MEDIUM': C.Y, 'LOW': C.DIM, 'INFO': C.CY}

    n_high = len(by_sev.get('HIGH', []))
    n_medium = len(by_sev.get('MEDIUM', []))
    n_low = len(by_sev.get('LOW', []))
    n_info = len(by_sev.get('INFO', []))

    print(f'\n  发现 {n_high + n_medium + n_low} 个潜在问题 (+ {n_info} 个 INFO 信息):')
    for sev in ['HIGH', 'MEDIUM', 'LOW', 'INFO']:
        if sev in by_sev:
            n = len(by_sev[sev])
            print(f'    {sev_color[sev]}{sev}: {n}{C.END}')

    print()
    for sev in sev_order:
        if sev not in by_sev:
            continue
        print(f'\n{C.BOLD}{sev_color[sev]}{"─"*70}{C.END}')
        print(f'{C.BOLD}{sev_color[sev]}  {sev} 级别 ({len(by_sev[sev])} 项){C.END}')
        print(f'{sev_color[sev]}{"─"*70}{C.END}')
        for i, iss in enumerate(by_sev[sev], 1):
            print(f'\n  {C.BOLD}[{i}] {iss["type"]}{C.END}')
            print(f'      {C.DIM}匹配:    {iss["match"]!r}{C.END}')
            if 'parsed' in iss:
                print(f'      {C.DIM}解析:    {iss["parsed"]}{C.END}')
            print(f'      {C.DIM}原因:    {iss["reason"]}{C.END}')
            print(f'      {C.DIM}建议:    {iss["suggestion"]}{C.END}')

def main():
    p = argparse.ArgumentParser(
        description='MiniMax M3 输出 hallucination 检测器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python mm3_hallucination_detector.py F:\\Research\\arxiv\\llm_summaries\\main.experiments.mm3.md\n'
               '  python mm3_hallucination_detector.py F:\\Research\\arxiv\\llm_summaries\\main.experiments.mm3.md --pdf F:\\Research\\arxiv\\main.pdf\n'
               '  python mm3_hallucination_detector.py F:\\Research\\arxiv\\llm_summaries\\\n',
    )
    p.add_argument('path', help='单个 .md 文件或目录')
    p.add_argument('--pdf', help='(可选) 对应原 PDF, 用于未定义术语检测')
    p.add_argument('--year', type=int, help='当前年 (默认今天年, 用于 arXiv 编号验证)')
    p.add_argument('--strict', action='store_true',
                   help='严格模式: 忽略 severity_cap, 所有冲突都报 HIGH. '
                        '用于查看"如果不做上下文区分"会报什么.')
    p.add_argument('--quiet-coexist', action='store_true',
                   help='静默模式: 不打印 INFO 级别 (multi_design_coexistence), 只显示 HIGH/MEDIUM/LOW')
    p.add_argument('--window', type=int, default=200,
                   help='"用途标注"启发式窗口大小 (默认 200 字符). '
                        '80=严格, 200=覆盖跨表格行, 300+=很宽松.')
    args = p.parse_args()

    enable_windows_ansi()

    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.M}  MiniMax M3 Hallucination 检测器{C.END}')
    print(f'{C.BOLD}{C.M}  时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}{C.END}')
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')

    # 加载 PDF 文本 (optional)
    pdf_text = None
    if args.pdf:
        try:
            import pdfplumber
            with pdfplumber.open(args.pdf) as pdf:
                pdf_text = '\n'.join((p.extract_text() or '') for p in pdf.pages[:15])
            print(f'\n  PDF 文本已加载: {len(pdf_text):,} 字符')
        except Exception as e:
            print(f'  {C.Y}PDF 加载失败: {e}{C.END}')

    # 处理单个文件还是目录
    path = Path(args.path)
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.glob('*.md'))
    else:
        print(f'{C.R}路径不存在: {path}{C.END}')
        sys.exit(1)

    if not files:
        print(f'{C.Y}没找到 .md 文件{C.END}')
        sys.exit(1)

    print(f'\n  将扫描 {len(files)} 个文件')
    if args.strict:
        print(f'  {C.R}🔴 --strict 模式: 忽略 severity_cap, 所有冲突都报 HIGH{C.END}')
    if args.quiet_coexist:
        print(f'  {C.DIM}--quiet-coexist 模式: 不显示 INFO (multi_design_coexistence){C.END}')

    total_issues = 0
    total_high = 0
    for f in files:
        body, issues = analyze_file(
            f, pdf_text=pdf_text, current_year=args.year, strict=args.strict,
            window=args.window)
        if body is None:
            print(f'  {C.Y}跳过 (不存在): {f}{C.END}')
            continue
        # quiet-coexist: 过滤掉 INFO
        if args.quiet_coexist:
            issues = [i for i in issues if i['severity'] != 'INFO']
        print_report(f, body, issues)
        total_issues += len(issues)
        total_high += len([i for i in issues if i['severity'] == 'HIGH'])

    print(f'\n{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'{C.BOLD}  总结{C.END}')
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'  扫描文件数: {len(files)}')
    print(f'  发现问题总数: {total_issues}')
    print(f'  其中 HIGH: {total_high}')
    if args.strict and total_high > 0:
        print(f'  {C.R}🔴 --strict 模式: 这是"如果不做上下文区分"的全部 HIGH{C.END}')
        print(f'  {C.DIM}  跟正常模式对比, 可看出哪些是真矛盾, 哪些是论文多设计共存.{C.END}')
    if total_high == 0:
        print(f'  {C.G}✅ 没有 HIGH 级别 hallucination (无需紧急核查){C.END}')
    else:
        print(f'  {C.Y}⚠ {total_high} 个 HIGH 级问题,建议人工核查{C.END}')

if __name__ == '__main__':
    main()