#!/usr/bin/env bash
# K 冲突决策树测试 - 本地运行脚本
#
# 用法:
#   bash run_k_conflict_tests.sh         # 跑 K 冲突测试
#   bash run_k_conflict_tests.sh --all   # 跑 K 冲突 + 主测试套件
#
# 平台: Linux / macOS / Git Bash on Windows

set -e

echo "=========================================="
echo "K Conflict Decision Tree Tests"
echo "=========================================="

# 1. K 冲突测试
echo ""
echo "▶ Step 1: K Conflict Decision Tree"
echo "------------------------------------------"
python _k_conflict_decision_tree.py
K_CONFLICT_EXIT=$?

# 2. 主测试套件 (15 case)
if [ "$1" = "--all" ]; then
    echo ""
    echo "▶ Step 2: Main Test Suite (15 cases)"
    echo "------------------------------------------"
    python _test_granularity_suite.py
    MAIN_EXIT=$?
else
    MAIN_EXIT=0
fi

# 3. 总结
echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
if [ $K_CONFLICT_EXIT -eq 0 ]; then
    echo "  ✅ K Conflict Tests: PASS"
else
    echo "  ❌ K Conflict Tests: FAIL (exit $K_CONFLICT_EXIT)"
fi
if [ "$1" = "--all" ]; then
    if [ $MAIN_EXIT -eq 0 ]; then
        echo "  ✅ Main Test Suite: PASS"
    else
        echo "  ❌ Main Test Suite: FAIL (exit $MAIN_EXIT)"
    fi
fi
echo "=========================================="

# 退出码
if [ $K_CONFLICT_EXIT -ne 0 ] || [ $MAIN_EXIT -ne 0 ]; then
    exit 1
fi
exit 0