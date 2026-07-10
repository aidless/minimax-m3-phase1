@echo off
REM K 冲突决策树测试 - Windows 本地运行脚本
REM
REM 用法:
REM   run_k_conflict_tests.cmd         REM 跑 K 冲突测试
REM   run_k_conflict_tests.cmd --all   REM 跑 K 冲突 + 主测试套件

setlocal enabledelayedexpansion

echo ==========================================
echo K Conflict Decision Tree Tests
echo ==========================================

REM 1. K 冲突测试
echo.
echo Step 1: K Conflict Decision Tree
echo ------------------------------------------
python _k_conflict_decision_tree.py
set K_CONFLICT_EXIT=%ERRORLEVEL%

REM 2. 主测试套件 (15 case)
if "%1"=="--all" (
    echo.
    echo Step 2: Main Test Suite (15 cases^)
    echo ------------------------------------------
    python _test_granularity_suite.py
    set MAIN_EXIT=!ERRORLEVEL!
) else (
    set MAIN_EXIT=0
)

REM 3. 总结
echo.
echo ==========================================
echo Test Results
echo ==========================================
if !K_CONFLICT_EXIT! equ 0 (
    echo   PASS: K Conflict Tests
) else (
    echo   FAIL: K Conflict Tests ^(!K_CONFLICT_EXIT!^)
)
if "%1"=="--all" (
    if !MAIN_EXIT! equ 0 (
        echo   PASS: Main Test Suite
    ) else (
        echo   FAIL: Main Test Suite ^(!MAIN_EXIT!^)
    )
)
echo ==========================================

if !K_CONFLICT_EXIT! neq 0 exit /b 1
if "%1"=="--all" if !MAIN_EXIT! neq 0 exit /b 1
exit /b 0