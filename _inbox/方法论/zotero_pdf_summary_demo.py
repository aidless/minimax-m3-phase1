"""
zotero_pdf_summary_demo.py
==========================
模拟 Zotero + llm-for-zotero v3.8.25 + MiniMax M3 端到端调用流程:
  1. 读 PDF (用 pdfplumber 提取文本, 模拟 Zotero 把 PDF 内容喂给 LLM)
  2. 构造 prompt (参考 llm-for-zotero 内置 prompt 风格, 用中文)
  3. 调用 MiniMax M3 API (OpenAI 兼容协议, 国内 cn endpoint)
  4. 打印 LLM 输出 (含 <think> 标签剥离, 跟 Zotero 侧栏显示一致)

用法:
  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf
  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf --task summary
  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf --task methods
  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf --task critique

任务类型 (--task):
  summary     - 总结论文
  methods     - 提取方法
  experiments - 提取实验配置 (对 TMLR 复现最有用)
  critique    - 模拟 TMLR reviewer 视角审稿

位置: F:\\Research\\_inbox\\方法论\\zotero_pdf_summary_demo.py
"""
import os
import sys
import json
import re
import time
import argparse
import socket
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

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

# ── MiniMax API 配置 ──────────────────────────────────────────────
MM_KEY_SOURCES = [
    Path(os.environ.get('USERPROFILE', '')) / 'AppData' / 'Local' / 'hermes' / '.env',
]
MM_BASE = 'https://api.minimaxi.com/v1'
MM_BASE_GLOBAL = 'https://api.MiniMax.io/v1'
MM_ENDPOINTS = {
    'cn': 'https://api.minimaxi.com/v1',
    'global': 'https://api.MiniMax.io/v1',
}
MM_MODEL = 'MiniMax-M3'

def check_endpoint(base_url, dns_timeout=10, tcp_timeout=15):
    """[加固 1] 早期检测 endpoint 联通性.
    返回 (ok: bool, detail: str, ip: str|None).
    加固理由: urllib urlopen 的 timeout 不覆盖 DNS 解析.
    如果 DNS 系统级 hang, urlopen 会卡 6+ 分钟不退.
    """
    host = base_url.split('//')[1].split('/')[0]
    try:
        # Step A: DNS 解析 (早期检测)
        ip = socket.gethostbyname(host)
        # Step B: TCP 握手 (早期检测)
        sock = socket.create_connection((host, 443), timeout=tcp_timeout)
        sock.close()
        return True, f"{host} → {ip} (443 OK)", ip
    except socket.gaierror as e:
        return False, f"DNS 解析失败 ({host}): {e}", None
    except (socket.timeout, OSError) as e:
        return False, f"TCP 握手失败 ({host}:443): {e}", None
    except Exception as e:
        return False, f"未知错误 ({host}): {type(e).__name__}: {e}", None

def load_api_key():
    for env_path in MM_KEY_SOURCES:
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding='utf-8').splitlines():
                m = re.match(r'(MINIMAX_(?:CN_)?API_KEY|OPENAI_API_KEY)\s*=\s*(.+)', line.strip())
                if m:
                    val = m.group(2).strip().strip('"').strip("'")
                    if val.startswith('sk-'):
                        return val, str(env_path)
        except Exception:
            pass
    return None, None

# ── PDF 文本提取 ──────────────────────────────────────────────────
def extract_pdf_text(pdf_path, max_pages=None, max_chars=100000):
    """用 pdfplumber 提取 PDF 文本. max_chars 防超出 1M context."""
    try:
        import pdfplumber
    except ImportError:
        print(f'{C.R}需要 pdfplumber: pip install pdfplumber{C.END}')
        sys.exit(1)

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        if max_pages:
            n_pages = min(n_pages, max_pages)
        for i, page in enumerate(pdf.pages[:n_pages]):
            txt = page.extract_text() or ''
            pages_text.append(txt)
            total = sum(len(t) for t in pages_text)
            if total > max_chars:
                # 截断
                pages_text[-1] = pages_text[-1][:max_chars - (total - len(pages_text[-1]))]
                break

    full_text = '\n\n'.join(pages_text)
    return full_text, len(pages_text)

# ── MiniMax API 调用 ──────────────────────────────────────────────
def call_minimax(prompt, model=MM_MODEL, base_url=MM_BASE, api_key=None,
                 max_tokens=4096, temperature=0.3, system_prompt=None,
                 max_retries=1, retry_delay=0, endpoint_check=True):
    """调 MiniMax M3. 返回 (raw_response, clean_content, usage, elapsed).

    [加固 1] endpoint_check: 调用前先 socket 早期检测 DNS+TCP, 避免 urlopen 卡死
    [加固 2] max_retries + retry_delay: 网络抖动时自动恢复
    加固理由: Phase 2 batch 测试发现 Windows DNS resolver 系统级 hang,
              urllib urlopen 的 timeout=120 不覆盖 DNS, 会卡 6+ 分钟不退.
    """
    if not api_key:
        api_key, _ = load_api_key()
    if not api_key:
        raise RuntimeError('API key not found')

    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': prompt})

    body = json.dumps({
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }).encode('utf-8')

    last_error = None
    for attempt in range(max(1, max_retries)):
        # [加固 1] 调用前早期检测 endpoint
        if endpoint_check:
            ok, detail, ip = check_endpoint(base_url)
            if not ok:
                raise RuntimeError(f"[endpoint check] {detail}")
        try:
            req = urllib.request.Request(
                base_url + '/chat/completions',
                data=body, method='POST',
            )
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', f'Bearer {api_key}')

            t0 = time.time()
            r = urllib.request.urlopen(req, timeout=120)
            elapsed = time.time() - t0

            j = json.loads(r.read().decode())
            raw_content = j['choices'][0]['message']['content']
            clean_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()
            usage = j.get('usage', {})
            return j, clean_content, usage, elapsed

        except (socket.timeout, urllib.error.URLError, OSError) as e:
            last_error = e
            err_type = type(e).__name__
            err_msg = str(e)[:200]
            print(f'{C.Y}  ⚠ attempt {attempt+1}/{max_retries} 失败: {err_type}: {err_msg}{C.END}')
            if attempt + 1 < max_retries and retry_delay > 0:
                # [加固 2] 退避重试
                delay = retry_delay * (2 ** attempt)  # 30/60/120s
                print(f'{C.Y}  ⏳ 等待 {delay}s 后重试...{C.END}')
                time.sleep(delay)
            else:
                break

    raise RuntimeError(f"call_minimax 失败 (重试 {max_retries} 次后): {last_error}")

# ── llm-for-zotero 风格的任务 prompt ──────────────────────────────
TASK_TEMPLATES = {
    'summary': {
        'system': '你是一位严谨的学术助手,擅长用中文总结英文学术论文。回答要:1) 准确 2) 简洁 3) 突出核心贡献。',
        'user_template': '''请仔细阅读以下论文全文,然后用中文写一段 200-300 字的总结,涵盖以下三方面:

1. 核心问题: 这篇论文要解决什么问题? 跟现有方法相比,关键 gap 是什么?
2. 方法: 论文提出了什么方法? 用一两句话说明核心思路。
3. 主要结果: 论文报告了哪些关键实验结果? 最重要的数字是什么?

论文内容如下 (节选自 arXiv PDF):
---
{paper_text}
---

请用中文回答。格式: 不要 markdown 标题,直接用自然段。''',
    },
    'methods': {
        'system': '你是一位严谨的学术助手,擅长从论文中精确提取方法描述。回答要:1) 忠实于原文 2) 保留关键术语 3) 避免添加论文没有的内容。',
        'user_template': '''请从以下论文中提取方法部分,用中文输出,包含:
- 模型架构 (网络结构, 关键层)
- 训练目标 (loss function, 优化器, 超参数)
- 数据处理 pipeline
- 评估指标
- 跟 baseline 的关键差异

论文内容:
---
{paper_text}
---

用中文回答,可以用 markdown 标题分节。''',
    },
    'experiments': {
        'system': '你是一位严谨的学术助手,擅长提取学术论文的实验配置。回答要:1) 完整 2) 具体 3) 可复现。',
        'user_template': '''请从以下论文中提取所有实验配置,用 markdown 表格输出,覆盖:
- 数据集 (名称, 规模, 划分)
- baseline 模型 (名称, 出处)
- 评估指标 (公式或定义)
- 硬件环境
- 训练时长
- 关键超参数 (lr, batch_size, optimizer, epochs)

论文内容:
---
{paper_text}
---

这是 TMLR 投稿,复现性是审稿关键,所以请尽量精确。''',
    },
    'critique': {
        'system': '你是一位 TMLR (Transactions on Machine Learning Research) 的 reviewer。你严格但公平,关注方法学严谨性、实验充分性、复现性、和 novelty。',
        'user_template': '''请以 TMLR reviewer 的视角评估以下论文。给出:
1. Strengths (3 条以内,具体)
2. Weaknesses (3-5 条,具体)
3. Questions for authors (3 个,尖锐)
4. Score (1-10, 6 分以上考虑接受)

论文内容:
---
{paper_text}
---

请用中文回答,严格遵循 TMLR 评审标准。''',
    },
}

# ── 主入口 ────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description='Zotero + llm-for-zotero + MiniMax M3 端到端 PDF 总结模拟',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf\n'
               '  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf --task methods\n'
               '  python zotero_pdf_summary_demo.py F:\\Research\\arxiv\\main.pdf --task critique\n',
    )
    p.add_argument('pdf_path', help='PDF 文件路径')
    p.add_argument('--task', choices=list(TASK_TEMPLATES.keys()), default='summary',
                   help='任务类型: summary/methods/experiments/critique')
    p.add_argument('--max-pages', type=int, default=20, help='最多读多少页 (默认 20)')
    p.add_argument('--max-chars', type=int, default=80000, help='最多读多少字符 (默认 80K)')
    p.add_argument('--max-tokens', type=int, default=4096, help='LLM 响应最大 tokens')
    # [加固 3/4] endpoint 选择 + 退避重试
    p.add_argument('--endpoint', choices=list(MM_ENDPOINTS.keys()), default='cn',
                   help='API endpoint: cn (api.minimaxi.com) | global (api.MiniMax.io)')
    p.add_argument('--retry', type=int, default=1,
                   help='API 失败时最大重试次数 (默认 1 = 不重试, 推荐 3)')
    p.add_argument('--retry-delay', type=int, default=30,
                   help='重试基础延迟秒数 (默认 30, 退避 30/60/120s)')
    p.add_argument('--no-endpoint-check', action='store_true',
                   help='跳过调用前的 endpoint 联通性检查 (不推荐)')
    args = p.parse_args()

    enable_windows_ansi()
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.M}  Zotero + llm-for-zotero + MiniMax M3 端到端 PDF 总结{C.END}')
    print(f'{C.BOLD}{C.M}  时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}{C.END}')
    print(f'{C.BOLD}{C.M}{"="*70}{C.END}')

    # 1. 检查 PDF
    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f'{C.R}❌ PDF 不存在: {pdf_path}{C.END}')
        sys.exit(1)
    print(f'\n  PDF: {pdf_path}')
    print(f'  大小: {pdf_path.stat().st_size:,} bytes')
    print(f'  任务: {args.task}')

    # 2. 读 key
    api_key, key_source = load_api_key()
    if not api_key:
        print(f'{C.R}❌ 找不到 API key{C.END}')
        sys.exit(1)
    print(f'  Key 来源: {key_source}')

    # 3. 提取 PDF 文本
    print(f'\n{C.CY}▸ 步骤 1: 提取 PDF 文本...{C.END}')
    text, n_pages = extract_pdf_text(pdf_path, max_pages=args.max_pages, max_chars=args.max_chars)
    print(f'  读取了 {n_pages} 页,共 {len(text):,} 字符')
    print(f'  {C.DIM}前 300 字符预览: {text[:300]!r}...{C.END}')

    # 4. 构造 prompt
    template = TASK_TEMPLATES[args.task]
    prompt = template['user_template'].format(paper_text=text)
    print(f'\n{C.CY}▸ 步骤 2: 构造 prompt ({len(prompt):,} 字符)...{C.END}')

    # 5. 调 MiniMax M3
    base_url = MM_ENDPOINTS[args.endpoint]
    print(f'\n{C.CY}▸ 步骤 3: 调用 MiniMax M3...{C.END}')
    print(f'  Model: {MM_MODEL}')
    print(f'  Endpoint: {args.endpoint} ({base_url})')
    print(f'  重试策略: max_retries={args.retry}, retry_delay={args.retry_delay}s')
    print(f'  endpoint 早期检测: {"ON" if not args.no_endpoint_check else "OFF"}')
    try:
        raw, clean, usage, elapsed = call_minimax(
            prompt,
            api_key=api_key,
            max_tokens=args.max_tokens,
            system_prompt=template['system'],
            base_url=base_url,
            max_retries=args.retry,
            retry_delay=args.retry_delay,
            endpoint_check=not args.no_endpoint_check,
        )
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')[:300]
        print(f'{C.R}❌ HTTP {e.code}: {err_body}{C.END}')
        sys.exit(1)
    except Exception as e:
        print(f'{C.R}❌ {type(e).__name__}: {e}{C.END}')
        print(f'{C.DIM}💡 提示:')
        print(f'  1. 如果是 DNS/timeout 错误, 试 --endpoint global')
        print(f'  2. 加 --retry 3 --retry-delay 30 启用退避重试')
        print(f'  3. 临时跳过检测: --no-endpoint-check{C.END}')
        sys.exit(1)

    # 6. 报告
    print(f'\n  {C.G}✓ 调用成功{C.END}  ({elapsed:.1f}s)')
    print(f'  Token 用量:')
    print(f'    prompt:     {usage.get("prompt_tokens", "?")}')
    print(f'    completion: {usage.get("completion_tokens", "?")}')
    print(f'    reasoning:  {usage.get("completion_tokens_details", {}).get("reasoning_tokens", "?")}')
    print(f'    total:      {usage.get("total_tokens", "?")}')

    # 7. 输出 LLM 总结
    print(f'\n{C.BOLD}{C.G}{"="*70}{C.END}')
    print(f'{C.BOLD}{C.G}  MiniMax M3 输出 (任务: {args.task}){C.END}')
    print(f'{C.BOLD}{C.G}{"="*70}{C.END}')
    print()
    print(clean)
    print()
    print(f'{C.BOLD}{C.G}{"="*70}{C.END}')

    # 8. 保存结果
    out_dir = pdf_path.parent / 'llm_summaries'
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f'{pdf_path.stem}.{args.task}.mm3.md'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f'# {pdf_path.name} - {args.task}\n\n')
        f.write(f'**生成时间**: {datetime.now().isoformat()}\n')
        f.write(f'**模型**: {MM_MODEL}\n')
        f.write(f'**endpoint**: {MM_BASE}\n')
        f.write(f'**Token 用量**: prompt={usage.get("prompt_tokens")} '
                f'completion={usage.get("completion_tokens")} '
                f'reasoning={usage.get("completion_tokens_details", {}).get("reasoning_tokens")}\n')
        f.write(f'**耗时**: {elapsed:.1f}s\n\n')
        f.write('---\n\n')
        f.write(clean)
    print(f'\n{C.DIM}结果已保存到: {out_path}{C.END}')

if __name__ == '__main__':
    main()