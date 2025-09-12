:: ==============================================
:: Qt Patch应用工具
:: Author: wanghao

:: 版本 1.0
:: 功能：按模块名精准应用patch文件
:: ==============================================

@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 输出颜色（支持ANSI的Windows 10+）
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

:: 检查是否可以使用颜色
ver | findstr /i "10\." >nul 2>&1
if !errorlevel! equ 0 (
    :: Enable ANSI colors on Windows 10+
    for /f "tokens=* usebackq" %%f in (`echo prompt $E^| cmd`) do @set "ESC=%%f"
    set "RED=!ESC![91m"
    set "GREEN=!ESC![92m"
    set "YELLOW=!ESC![93m"
    set "BLUE=!ESC![94m"
    set "NC=!ESC![0m"
) else (
    :: Fallback for older Windows
    set "RED="
    set "GREEN="
    set "YELLOW="
    set "BLUE="
    set "NC="
)

:: 主程序
:MAIN
set "repo_path="
set "patch_path="
set "target_module="
set "FAILED_COUNT=0"

:: 参数解析
:PARSE_LOOP
if "%~1"=="" goto PARSE_END

if /i "%~1"=="-h" goto HELP
if /i "%~1"=="--help" goto HELP
if /i "%~1"=="-r" set "repo_path=%~2" & shift
if /i "%~1"=="--repo" set "repo_path=%~2" & shift
if /i "%~1"=="-p" set "patch_path=%~2" & shift
if /i "%~1"=="--patch" set "patch_path=%~2" & shift
if /i "%~1"=="-m" set "target_module=%~2" & shift
if /i "%~1"=="--module" set "target_module=%~2" & shift

shift
goto PARSE_LOOP

:PARSE_END

:: 参数验证
if not defined repo_path (
    echo %RED%[错误]%NC% 必须指定Qt源码路径
	
    call :HELP
    exit /b 1
)

if not defined patch_path (
    echo %RED%[错误]%NC% 必须指定patch路径
	
    call :HELP
    exit /b 1
)

:: 环境检查
where git >nul 2>&1 || (
    echo %RED%[错误]%NC% Git未安装或未加入PATH
	
    call :FAIL "Git工具缺失"
)

if not exist "%repo_path%\.git" (
    echo %RED%[错误]%NC% 无效的Qt仓库：%repo_path%
	
    call :FAIL "Qt仓库验证失败"
	exit /b 1
)

:: 执行模式判断
for %%F in ("%patch_path%") do (
    if exist "%%~fF" (
        if "%%~aF" geq "d" (
            call :BATCH_APPLY
        ) else (
            call :SINGLE_APPLY "%patch_path%"
        )
    ) else (
		echo %RED%[错误]%NC% 路径不存在：%patch_path%		
        call :FAIL "无效路径"
		exit /b 1
    )
)

:: 拷贝ohextras模块

xcopy %patch_path%\qtohextras  %repo_path%\qtohextras /E /I /Y /Q

exit /b !MODULE_FAILED!

:: 添加结果汇总函数
:SHOW_RESULTS
echo.
echo ============================================
echo [%TIME%] 操作结果汇总
echo ============================================
echo 已处理仓库：%repo_path%
if defined target_module (
    echo 目标模块：%target_module%
)
echo.
echo 成功应用：%SUCCESS_COUNT%
echo 跳过处理：%SKIPPED_COUNT%
echo 失败次数：%FAILED_COUNT%
echo.

if %FAILED_COUNT% gtr 0 (
    echo %YELLOW%[警告]%NC% 完成 - 存在失败的patch应用
    exit /b 1
) else if %SUCCESS_COUNT% equ 0 (
    echo %YELLOW%[警告]%NC% 完成 - 没有成功应用的patch
    exit /b 1
) else (
    echo %GREEN%[√]%NC% 所有patch应用成功
    exit /b 0
)

:: 错误处理函数
:FAIL
echo.
echo ============================================
echo %RED%[%TIME%] 操作失败: 错误代码 %errorlevel%%NC%
if "%1" neq "" echo 失败原因：%1
if defined current_module echo 目标模块：!current_module!
echo ============================================
exit /b %errorlevel%

:: 帮助信息
:HELP
echo.
echo 使用方法：apply-patch.bat [选项]

echo.
echo 选项：

echo   -h, --help      显示本帮助信息

echo   -r, --repo      指定Qt源码根路径（必需）

echo   -p, --patch     指定patch文件/目录（必需）

echo   -m, --module    指定目标子模块（可选）
echo.
echo Patch文件命名规则：

echo   模块名.patch （如 qtbase.patch）

echo   特殊命名：

echo     root.patch    - 仅应用到主仓库

echo     common.patch  - 应用到所有模块

echo.
echo 示例：

echo   apply-patch.bat -r "C:\Qt\6.5.0\Src" -p "C:\patches\"
echo   apply-patch.bat -r "C:\Qt\6.5.0\Src" -p "qtbase.patch"
echo.
exit /b 0


:: 单个patch应用
:SINGLE_APPLY
set "patch_file=%~1"
set "module_name=%~n1"

echo.
echo %BLUE%[信息]%NC% 正在应用patch：%~nx1

if defined target_module (
    set "current_module=%target_module%"
    call :APPLY_TO_MODULE "%repo_path%\%target_module%" "%patch_file%"
    goto :EOF
)

:: 自动识别patch目标
if /i "%module_name%"=="root" (
    call :APPLY_TO_MODULE "%repo_path%" "%patch_file%"
) else if /i "%module_name%"=="common" (
    call :APPLY_TO_ALL "%patch_file%"
) else (
    set "current_module=%module_name%"
    call :APPLY_TO_MODULE "%repo_path%\%module_name%" "%patch_file%"
)
goto :EOF

:: 批量应用
:BATCH_APPLY
echo.
echo %BLUE%[信息]%NC% 扫描patch目录：%patch_path%

:: 重置计数器
set "MODULE_FAILED=0"
set "MODULE_SUCCESS=0"

:: 处理主仓库patch
if exist "%patch_path%\root.patch" (
    call :APPLY_TO_MODULE "%repo_path%" "%patch_path%\root.patch" && (
        set /a "SUCCESS_COUNT+=1"
        set /a "MODULE_SUCCESS+=1"
    ) || (
        set /a "FAILED_COUNT+=1"
        set /a "MODULE_FAILED+=1"
    )
)

:: 处理通用patch

if exist "%patch_path%\common.patch" (
    call :APPLY_TO_ALL "%patch_path%\common.patch" && (
        set /a "SUCCESS_COUNT+=1"
        set /a "MODULE_SUCCESS+=1"
    ) || (
        set /a "FAILED_COUNT+=1"
        set /a "MODULE_FAILED+=1"
    )
)

:: 处理子模块patch

if defined target_module (
    set "current_module=%target_module%"
    if exist "%patch_path%\%target_module%.patch" (
        call :APPLY_TO_MODULE "%repo_path%\%target_module%" "%patch_path%\%target_module%.patch" && (
			set /a "SUCCESS_COUNT+=1"
			set /a "MODULE_SUCCESS+=1"
		) || (
			set /a "FAILED_COUNT+=1"
			set /a "MODULE_FAILED+=1"
		)
    )
) else (
    for /f "delims=" %%m in ('git -C "%repo_path%" submodule --quiet foreach --recursive "echo $path"') do (
        set "current_module=%%m"
        if exist "%patch_path%\%%m.patch" (
            call :APPLY_TO_MODULE "%repo_path%\%%m" "%patch_path%\%%m.patch" && (
				set /a "SUCCESS_COUNT+=1"
				set /a "MODULE_SUCCESS+=1"
			) || (
				set /a "FAILED_COUNT+=1"
				set /a "MODULE_FAILED+=1"
			)
        )
    )
)

:: 显示批量处理结果
echo.
echo %BLUE%[信息]%NC% 批量处理完成：

echo       成功应用：!MODULE_SUCCESS!

echo       失败次数：!MODULE_FAILED!
goto :EOF

:: 应用到指定模块

:APPLY_TO_MODULE
set "module_path=%~1"
set "patch_file=%~2"

if not exist "%module_path%\.git" (
    echo %YELLOW%[警告]%NC% 跳过无效模块：%module_path%
	set /a "SKIPPED_COUNT+=1"
    goto :EOF
)

echo.
echo %BLUE%[信息]%NC% 应用到模块：%module_path%
echo        Patch文件：%~nx2

pushd "%module_path%"
git apply --check "%patch_file%" || (
    popd
    echo %YELLOW%[警告]%NC% 跳过不兼容patch：%~nx2
	set /a "SKIPPED_COUNT+=1"
    goto :EOF
)

git apply "%patch_file%" && (
    popd
    echo %GREEN%[√]%NC% 应用成功
    exit /b 0
) || (
    popd
    echo %RED%[错误]%NC% 应用失败
    exit /b 1
)

popd
goto :EOF

:: 应用到所有模块
:APPLY_TO_ALL
set "patch_file=%~1"

:: 主仓库

echo %BLUE%[信息]%NC% 应用到主仓库
call :APPLY_TO_MODULE "%repo_path%" "%patch_file%" || set /a "FAILED_COUNT+=1"

:: 子模块

for /f "delims=" %%m in ('git -C "%repo_path%" submodule --quiet foreach --recursive "echo $path"') do (
    set "current_module=%%m"
    call :APPLY_TO_MODULE "%repo_path%\%%m" "%patch_file%" || set /a "FAILED_COUNT+=1"
)
goto :EOF
