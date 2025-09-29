@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ==============================================
:: OpenHarmony Qt 交叉编译脚本
:: Author: wanghao

:: 版本: 1.2
:: 修改说明: 增加工具自动下载功能，优化错误处理

:: 版本: 1.1
:: 修改说明: 修复配置文件加载问题，优化路径处理
:: ==============================================

:: 默认的工作根目录
set "OHOS_API=18"
set "ROOT_DIR=%cd%\Work"
set "QT_GIT_URL=https://gitcode.com/qtforohos/qt5.git"
set "QT_GIT_PATCH_URL=https://gitcode.com/openharmony-sig/qt.git"
set "BASE_URL_OHOS=https://repo.harmonyos.com/sdkmanager/v5/ohos/getSdkList"
REM set "TARGET_SDK=https://cidownload.openharmony.cn/version/Master_Version/OpenHarmony_5.1.0.101/20250327_020249/version-Master_Version-OpenHarmony_5.1.0.101-20250327_020249-ohos-sdk-full_5.1.0-Release.tar.gz"

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

:: 错误处理宏

set "ERROR=|| call :FAIL"

:: 初始化Qt编译参数默认值
set DEFAULT_SKIP_PARAM=-skip qtsystems -skip qtvirtualkeyboard ^
-skip qtnetworkauth -skip qtsensors -skip qtwebview -skip qtlocation ^
-skip webengine -skip qtgamepad -skip qtpim -skip qtscript ^
-skip qtdoc -skip qttools

:: 脚本不需要解析的跳过模块
:: -skip qtconnectivity

:: 显示帮助信息
if "%~1" == "-h" goto HELP
if "%~1" == "--help" goto HELP
if "%~1" == "-clean" goto CLEAN
if "%~1" == "-config" goto CONFIG
if "%~1" == "-l" goto LIST_COMPONENTS
if "%~1" == "-list" goto LIST_COMPONENTS
if "%~1" == "-version" goto SHOW_VERSION

:: 主程序入口
goto MAIN

:: ============================================================================
:: 工具函数
:: ============================================================================

:LOG_INFO
echo %GREEN%[信息]%NC% %~1
goto :eof

:LOG_WARN
echo %YELLOW%[警告]%NC% %~1 >&2
goto :eof

:LOG_ERROR
echo %RED%[错误]%NC% %~1 >&2
goto :eof

:LOG_DEBUG
if "%VERBOSE%"=="true" (
    echo %BLUE%[调试]%NC% %~1 >&2
)
goto :eof

:DETECT_PLATFORM
set "os_type=windows"
set "os_arch=unknown"

:: Detect architecture
if "%PROCESSOR_ARCHITECTURE%"=="x86" set "os_arch=x64"
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" set "os_arch=x64"
if "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "os_arch=arm64"

set "platform=%os_type%-%os_arch%"
exit /b 0

:GET_SDK_COMPONENTS
set "platform=%~1"
set "temp_file=%TEMP_DIR%\components.json"
set "post_data_file=%TEMP_DIR%\post_data.json"

:: 解析平台
for /f "tokens=1,2 delims=-" %%a in ("%platform%") do (
    set "os_type=%%a"
    set "os_arch=%%b"
)

:: 准备POST数据
(
echo {
echo   "osType": "!os_type!",
echo   "osArch": "!os_arch!",
echo   "supportVersion": "5.1-ohos-single-2"
echo }
) > "%post_data_file%"

:: 使用PowerShell发出API请求
powershell -Command "$body = Get-Content '%post_data_file%' -Raw; $response = Invoke-RestMethod -Uri '%BASE_URL_OHOS%' -Method Post -Headers @{'Content-Type'='application/json'} -Body $body; $response | ConvertTo-Json -Depth 10 | Out-File -FilePath '%temp_file%' -Encoding UTF8"

if !errorlevel! neq 0 (
    call :LOG_ERROR "Failed to fetch SDK components"
    exit /b 1
)
exit /b 0

:SHOW_VERSION
echo.
call :DETECT_PLATFORM
if !errorlevel! equ 0 (
    echo 平台: !platform!	
    echo 仓库地址: repo.harmonyos.com
	
    echo.    
    echo 正在从服务器获取实时API数据…	
	
    call :GET_SDK_COMPONENTS "!platform!" >nul 2>&1
    
    if !errorlevel! equ 0 (
        set "components_file=%TEMP_DIR%\components.json"
        if exist "!components_file!" (
            echo API连接成功
            
            :: 创建PowerShell解析脚本			
            set "ps_version_script=%TEMP_DIR%\get_version_info.ps1"
            (
                echo try {
                echo     $jsonFile = '%TEMP_DIR%\components.json'
                echo     if ^(Test-Path $jsonFile^) {
                echo         $json = Get-Content $jsonFile -Raw ^| ConvertFrom-Json
                echo         if ^($json -and $json.Count -gt 0^) {
                echo             $apiVersions = $json ^| ForEach-Object { [int]$_.apiVersion } ^| Sort-Object -Unique -Descending
                echo             $components = $json ^| Group-Object -Property path ^| ForEach-Object { $_.Name } ^| Sort-Object
                echo             $latestApi = $apiVersions[0]
                echo             $oldestApi = $apiVersions[-1]
                echo             Write-Host "API Versions Available: $($apiVersions -join ', ')"
                echo             Write-Host "Latest API Version: $latestApi"
                echo             Write-Host "Oldest API Version: $oldestApi"
                echo             Write-Host "Components Available: $($components -join ', ')"
                echo             Write-Host "Total Components: $($json.Count)"
                echo         } else {
                echo             Write-Host "No component data received from server"
                echo         }
                echo     } else {
                echo         Write-Host "Components file not found: $jsonFile"
                echo     }
                echo } catch {
                echo     Write-Host "Error processing version data: $($_.Exception.Message)"
                echo }
            ) > "!ps_version_script!"
            
            powershell -ExecutionPolicy Bypass -File "!ps_version_script!"
            
            :: 清理临时文件			
            del "!ps_version_script!" >nul 2>&1
            del "!components_file!" >nul 2>&1
            
        ) else (
            echo 从服务器获取组件数据失败
			
        )
    ) else (
        echo 无法连接OpenHarmony SDK服务器		
    )
    
    echo.
    echo 附加信息:
	
    echo   安装模式: 最新版, 指定版本, 组件:版本, 组件:API
	
    echo   配置选项: 持久化和临时SDK根目录设置
	
    echo   使用 --list 查看详细组件信息
    
) else (
    echo 无法检测平台类型
)
exit /b 0

:LIST_COMPONENTS
call :DETECT_PLATFORM
if !errorlevel! neq 0 (
    call :LOG_ERROR "Failed to detect platform"
    exit /b 1
)

call :LOG_INFO "平台可用SDK组件: !platform!"

call :GET_SDK_COMPONENTS "!platform!"
if !errorlevel! neq 0 (
    call :LOG_ERROR "获取SDK组件失败"
	
    exit /b 1
)

set "components_file=%TEMP_DIR%\components.json"

if not exist "!components_file!" (
    call :LOG_ERROR "组件信息文件未找到"
    exit /b 1
)

echo.

:: 使用PowerShell解析JSON并显示按API版本分组的组件
powershell -Command "try { $json = Get-Content '%components_file%' -Raw | ConvertFrom-Json; if ($json -and $json.Count -gt 0) { Write-Host ''; Write-Host 'Available SDK Components:'; Write-Host ('=' * 80); $groupedByApi = $json | Group-Object -Property apiVersion | Sort-Object { [int]$_.Name } -Descending; foreach ($apiGroup in $groupedByApi) { Write-Host ''; Write-Host \"API Version $($apiGroup.Name):\" -ForegroundColor Blue; Write-Host ('+' + ('-' * 78) + '+'); Write-Host ('| {0,-30} | {1,-20} | {2,-20} |' -f 'Component Name', 'Version', 'Size'); Write-Host ('+' + ('-' * 78) + '+'); foreach ($item in $apiGroup.Group) { $name = if ($item.displayName) { $item.displayName } else { 'Unknown' }; $version = if ($item.version) { $item.version } else { 'N/A' }; $size = if ($item.archive -and $item.archive.size) { [math]::Round($item.archive.size / 1MB, 2).ToString() + ' MB' } else { 'N/A' }; Write-Host ('| {0,-30} | {1,-20} | {2,-20} |' -f $name, $version, $size) }; Write-Host ('+' + ('-' * 78) + '+') }; Write-Host '' } else { Write-Host 'No SDK components found or invalid response format.' } } catch { Write-Host 'Error parsing SDK components:' $_.Exception.Message }"

:: 清理临时文件
del "%components_file%" >nul 2>&1

exit /b 0

:: ============================================================================
:: OpenHarmony SDK下载处理函数
:: ============================================================================

:INSTALL_COMPONENT
set "target=%~1"
call :LOG_INFO "安装SDK组件: %target%"

set "TEMP_DIR=%ROOT_DIR%\tmp"
call :LOG_INFO "[信息] 临时目录:%TEMP_DIR%"

:: 创建临时目录
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

call :DETECT_PLATFORM
if !errorlevel! neq 0 (
    call :LOG_ERROR "检测平台失败"
	
    exit /b 1
)

call :GET_SDK_COMPONENTS "!platform!"
if !errorlevel! neq 0 (
    call :LOG_ERROR "获取SDK组件失败"
	
    exit /b 1
)

set "components_file=%TEMP_DIR%\components.json"
if not exist "!components_file!" (
    call :LOG_ERROR "组件信息文件未找到"
	
    exit /b 1
)

:: Parse the target and install the components
if "!target!"=="latest" (
    call :INSTALL_LATEST_COMPONENTS
) else (
    :: Check whether the target is a pure number (API version)
    set "is_number=0"
    set /a test_num=!target! 2>nul
    if "!test_num!"=="!target!" (
        if !target! gtr 0 if !target! lss 100 set "is_number=1"
    )
    
    if "!is_number!"=="1" (
        call :INSTALL_API_VERSION_COMPONENTS "!target!"
    ) else (
        echo !target! | findstr ":" >nul
        if !errorlevel! equ 0 (
            call :INSTALL_SPECIFIC_COMPONENT "!target!"
        ) else (
            call :LOG_ERROR "无效的目标格式."
			
            exit /b 1
        )
    )
)
exit /b !errorlevel!

:INSTALL_LATEST_COMPONENTS
call :LOG_INFO "安装最新SDK组件..."

powershell -Command "try { $json = Get-Content '%components_file%' -Raw | ConvertFrom-Json; $latestApi = ($json | ForEach-Object { [int]$_.apiVersion } | Sort-Object -Descending)[0]; $latestComponents = $json | Where-Object { [int]$_.apiVersion -eq $latestApi }; foreach ($component in $latestComponents) { Write-Host \"Installing: $($component.displayName) v$($component.version) (API $($component.apiVersion))\"; } } catch { Write-Host 'Error:' $_.Exception.Message }"
:: Get latest API version and install all its components
powershell -Command "try { $json = Get-Content '%components_file%' -Raw | ConvertFrom-Json; $latestApi = ($json | ForEach-Object { [int]$_.apiVersion } | Sort-Object -Descending)[0]; $latestComponents = $json | Where-Object { [int]$_.apiVersion -eq $latestApi }; foreach ($component in $latestComponents) { $component | ConvertTo-Json -Compress | Out-File -FilePath '%TEMP_DIR%\install_queue.txt' -Append -Encoding UTF8 } } catch { Write-Host 'Error:' $_.Exception.Message; exit 1 }"
if !errorlevel! neq 0 exit /b 1
call :PROCESS_INSTALL_QUEUE
exit /b !errorlevel!

:INSTALL_API_VERSION_COMPONENTS
set "api_version=%~1"
call :LOG_INFO "安装指定API版本的所有组件 %api_version%..."

powershell -Command "try { $json = Get-Content '%components_file%' -Raw | ConvertFrom-Json; $components = $json | Where-Object { [int]$_.apiVersion -eq %api_version% }; if ($components.Count -eq 0) { Write-Host 'No components found for API version %api_version%'; exit 1 }; foreach ($component in $components) { Write-Host \"Installing: $($component.displayName) v$($component.version) (API $($component.apiVersion))\"; $component | ConvertTo-Json -Compress | Out-File -FilePath '%TEMP_DIR%\install_queue.txt' -Append -Encoding UTF8 } } catch { Write-Host 'Error:' $_.Exception.Message; exit 1 }"
if !errorlevel! neq 0 exit /b 1
call :PROCESS_INSTALL_QUEUE
exit /b !errorlevel!

:INSTALL_SPECIFIC_COMPONENT
set "target=%~1"
for /f "tokens=1,2 delims=:" %%a in ("%target%") do (
    set "component_name=%%a"
    set "component_version=%%b"
)

:: Check whether component_version is an API version (pure numbers) or a specific version
set "is_api_version=0"
set /a test_num=!component_version! 2>nul
if !test_num! equ !component_version! (
    if !component_version! gtr 0 if !component_version! lss 100 set "is_api_version=1"
)

if !is_api_version! equ 1 (
    REM :: It is an API version. Find the latest version of this component in this API
	
    call :LOG_INFO "安装最新的 !component_name! API版本: !component_version!"
	
    set "ps_script_file=%TEMP_DIR%\find_component.ps1"
    (
        echo try {
        echo     $json = Get-Content '%components_file%' -Raw ^| ConvertFrom-Json
        echo     $components = $json ^| Where-Object { $_.path -eq '!component_name!' -and [int]$_.apiVersion -eq [int]'!component_version!' }
        echo     if ^($components.Count -eq 0^) {
        echo         Write-Host 'No !component_name! component found for API version !component_version!'
        echo         exit 1
        echo     }
        echo     $latest = $components ^| Sort-Object { [version]$_.version } -Descending ^| Select-Object -First 1
        echo     Write-Host "Installing: " -NoNewline
        echo     Write-Host $latest.displayName -NoNewline
        echo     Write-Host " v" -NoNewline
        echo     Write-Host $latest.version -NoNewline
        echo     Write-Host " (API " -NoNewline
        echo     Write-Host $latest.apiVersion -NoNewline
        echo     Write-Host ")"
        echo     $latest ^| ConvertTo-Json -Compress ^| Out-File -FilePath '%TEMP_DIR%\install_queue.txt' -Encoding UTF8
        echo } catch {
        echo     Write-Host 'Error:' $_.Exception.Message
        echo     exit 1
        echo }
    ) > "!ps_script_file!"
	
    powershell -ExecutionPolicy Bypass -File "!ps_script_file!"
    del "!ps_script_file!" >nul 2>&1
) else (
    call :LOG_INFO "安装特定组件: !component_name! 版本: !component_version!"
	
    set "ps_script_file=%TEMP_DIR%\find_component.ps1"
    (
        echo try {
        echo     $json = Get-Content '%components_file%' -Raw ^| ConvertFrom-Json
        echo     $component = $json ^| Where-Object { $_.path -eq '!component_name!' -and $_.version -eq '!component_version!' }
        echo     if ^(-not $component^) {
        echo         Write-Host 'Component !component_name!:!component_version! not found'
        echo         exit 1
        echo     }
        echo     Write-Host "Installing: " -NoNewline
        echo     Write-Host $component.displayName -NoNewline
        echo     Write-Host " v" -NoNewline
        echo     Write-Host $component.version -NoNewline
        echo     Write-Host " (API " -NoNewline
        echo     Write-Host $component.apiVersion -NoNewline
        echo     Write-Host ")"
        echo     $component ^| ConvertTo-Json -Compress ^| Out-File -FilePath '%TEMP_DIR%\install_queue.txt' -Encoding UTF8
        echo } catch {
        echo     Write-Host 'Error:' $_.Exception.Message
        echo     exit 1
        echo }
    ) > "!ps_script_file!"
    powershell -ExecutionPolicy Bypass -File "!ps_script_file!"
    del "!ps_script_file!" >nul 2>&1
)
if !errorlevel! neq 0 exit /b 1
call :PROCESS_INSTALL_QUEUE
exit /b !errorlevel!

:PROCESS_INSTALL_QUEUE
set "queue_file=%TEMP_DIR%\install_queue.txt"
if not exist "!queue_file!" (
    call :LOG_ERROR "无需安装组件"
	
    exit /b 1
)

for /f "usebackq delims=" %%a in ("!queue_file!") do (
    call :DOWNLOAD_AND_INSTALL_COMPONENT "%%a"
    if !errorlevel! neq 0 (
        call :LOG_ERROR "安装组件失败"
		
        del "!queue_file!" >nul 2>&1
        exit /b 1
    )
)

del "!queue_file!" >nul 2>&1

set "OHOS_SDK_PATH=%ROOT_DIR%\ohos-sdk\%COMPONENT_API%"
set "LLVM_INSTALL_DIR=%OHOS_SDK_PATH%\native\llvm"
set "PATH=!PATH!;%LLVM_INSTALL_DIR%\bin"

call :LOG_INFO "[成功] OpenHarmony SDK准备完成"
call :LOG_INFO "SDK主目录:%OHOS_SDK_PATH%"
call :LOG_INFO "工具链路径:%LLVM_INSTALL_DIR%"

exit /b 0

:DOWNLOAD_AND_INSTALL_COMPONENT
set "component_json=%~1"
set "download_temp=%TEMP_DIR%\download_temp.json"
echo %component_json% > "!download_temp!"

:: Extract component information
powershell -Command "$component = Get-Content '%download_temp%' -Raw | ConvertFrom-Json; $component.displayName | Out-File -FilePath '%TEMP_DIR%\comp_name.txt' -Encoding ASCII; $component.path | Out-File -FilePath '%TEMP_DIR%\comp_path.txt' -Encoding ASCII; $component.version | Out-File -FilePath '%TEMP_DIR%\comp_version.txt' -Encoding ASCII; $component.apiVersion | Out-File -FilePath '%TEMP_DIR%\comp_api.txt' -Encoding ASCII; $component.archive.url | Out-File -FilePath '%TEMP_DIR%\comp_url.txt' -Encoding ASCII; $component.archive.size | Out-File -FilePath '%TEMP_DIR%\comp_size.txt' -Encoding ASCII; $component.archive.checksum | Out-File -FilePath '%TEMP_DIR%\comp_checksum.txt' -Encoding ASCII"

if !errorlevel! neq 0 (
    del "!download_temp!" >nul 2>&1
    exit /b 1
)

:: Read extracted information
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_name.txt") do set "COMPONENT_NAME=%%a"
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_path.txt") do set "COMPONENT_PATH=%%a"
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_version.txt") do set "COMPONENT_VERSION=%%a"
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_api.txt") do set "COMPONENT_API=%%a"
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_url.txt") do set "DOWNLOAD_URL=%%a"
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_size.txt") do set "FILE_SIZE=%%a"
for /f "usebackq delims=" %%a in ("%TEMP_DIR%\comp_checksum.txt") do set "CHECKSUM=%%a"

:: Clear temporary documents
del "%TEMP_DIR%\comp_*.txt" >nul 2>&1

:: Create the installation directory
set "install_dir=%ROOT_DIR%\ohos-sdk\!COMPONENT_API!\!COMPONENT_PATH!"
call :LOG_INFO "安装 !COMPONENT_NAME! v!COMPONENT_VERSION! to !install_dir!"

if not exist "!install_dir!" mkdir "!install_dir!" 2>nul

:: Determine the file name from the URL
for %%i in ("%DOWNLOAD_URL%") do set "filename=%%~nxi"
set "download_path=%TEMP_DIR%\%filename%"

:: Download file
call :LOG_INFO "下载 %filename% (%FILE_SIZE% bytes)..."

call :LOG_INFO "This may take several minutes depending on your internet connection..."
powershell -Command "try { $ProgressPreference = 'Continue'; Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%download_path%' -TimeoutSec 600; Write-Host 'Download completed successfully' } catch { Write-Host 'Download failed:' $_.Exception.Message; exit 1 }"

if !errorlevel! neq 0 (
    call :LOG_ERROR "下载失败"
	
    del "!download_temp!" >nul 2>&1
    exit /b 1
)

:: file verification
call :LOG_INFO "校验文件完整性..."

powershell -Command "try { if (Get-Command Get-FileHash -ErrorAction SilentlyContinue) { $hash = (Get-FileHash '%download_path%' -Algorithm SHA256).Hash.ToLower(); if ($hash -eq '%CHECKSUM%') { Write-Host 'Checksum verification passed' } else { Write-Host 'Checksum verification failed'; exit 1 } } else { $crypto = New-Object System.Security.Cryptography.SHA256CryptoServiceProvider; $stream = [System.IO.File]::OpenRead('%download_path%'); $hash = [System.BitConverter]::ToString($crypto.ComputeHash($stream)).Replace('-', '').ToLower(); $stream.Close(); if ($hash -eq '%CHECKSUM%') { Write-Host 'Checksum verification passed' } else { Write-Host 'Checksum verification failed'; exit 1 } } } catch { Write-Host 'Checksum verification error:' $_.Exception.Message; exit 1 }"

if !errorlevel! neq 0 (
    call :LOG_ERROR "文件完整性检查失败"
	
    del "%download_path%" >nul 2>&1
    del "!download_temp!" >nul 2>&1
    exit /b 1
)

:: file decompression
call :LOG_INFO "提取压缩文件到 !install_dir!..."

set "temp_extract_dir=%TEMP_DIR%\extract_temp"
if exist "%temp_extract_dir%" rmdir /s /q "%temp_extract_dir%"
mkdir "%temp_extract_dir%"

set "final_target_dir=!install_dir!"
powershell -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%download_path%', '%temp_extract_dir%'); Write-Host 'Extraction completed' } catch { Write-Host 'Extraction failed:' $_.Exception.Message; exit 1 }"

if !errorlevel! neq 0 (
    call :LOG_ERROR "提取文件失败"
    del "%download_path%" >nul 2>&1
    del "!download_temp!" >nul 2>&1
    exit /b 1
)

:: Move the file from the temporary retrieval directory to the target directory to reduce nested directories
call :LOG_INFO "将文件移动到目标目录..."
set "final_target_dir=!install_dir!"
powershell -Command "try { $tempDir = '%temp_extract_dir%'; $targetDir = '%final_target_dir%'; $items = Get-ChildItem $tempDir; if ($items.Count -eq 1 -and $items[0].PSIsContainer -and $items[0].Name -eq '%COMPONENT_PATH%') { $sourceDir = Join-Path $tempDir $items[0].Name; robocopy $sourceDir $targetDir /E /MOVE /NFL /NDL /NJH /NJS } else { robocopy $tempDir $targetDir /E /MOVE /NFL /NDL /NJH /NJS }; Write-Host 'Files moved successfully' } catch { Write-Host 'Move failed:' $_.Exception.Message; exit 1 }"

:: Clear the temporary extraction directory
if exist "%temp_extract_dir%" rmdir /s /q "%temp_extract_dir%"

del "%download_path%" >nul 2>&1
del "!download_temp!" >nul 2>&1

call :LOG_INFO "安装成功 %COMPONENT_NAME% v%COMPONENT_VERSION%"

exit /b 0

:FAIL
echo.
echo ============================================
call :LOG_ERROR "[%TIME%] 操作失败: 错误代码 %errorlevel%"
echo ============================================
exit /b %errorlevel%

:HELP
echo.
echo 使用方法: %~nx0 [选项]
echo.
echo 选项:
echo   -h, --help     显示帮助信息

echo   -clean         清理所有临时文件

echo   -config        交互式配置环境变量

echo   -version       显示OpenHarmony SDK信息

echo   -list          列出所有可用OpenHarmony SDK组件

echo.
echo 示例:
echo   %~nx0 -list
echo   %~nx0 -clean
echo   %~nx0 -config
echo   %~nx0 -version
echo.
exit /b 0

:: 加载配置文件
:LOAD_CFG
if exist "build-config.cfg" (
    call :LOG_INFO 加载配置文件...	
	
    for /f "usebackq tokens=1,* delims==" %%A in ("build-config.cfg") do (
        set "%%A=%%B"
		set "PATH=!PATH!;%%B"
    )
) else (
    call :LOG_ERROR "未找到配置文件，请先生成配置文件"
	exit /b 1
)
goto :eof

:MAIN
call :LOAD_CFG %ERROR%

:: 检查并准备必要工具
call :CHECK_AND_PREPARE_TOOLS %ERROR%

:: 参数处理
if "%~1" == "-config" goto CONFIG
if "%~1" == "-clean" goto CLEAN
if "%~1" == "-list" goto SHOW_VERSION
if "%~1" == "-version" goto SHOW_VERSION

:: 默认执行完整流程
goto FULL_PROCESS

:: ==============================================
:: 工具检查与下载模块
:: ==============================================
:CHECK_AND_PREPARE_TOOLS
echo.
call :LOG_INFO 检查必要工具...

:: 环境检查
where git >nul 2>&1 || (
    call :LOG_ERROR "Git工具缺失,Git未安装或未加入PATH"
	exit /b 1
)

:: 静默检查PowerShell
powershell -Command "exit 0" >nul 2>&1
if !errorlevel! neq 0 (
    call :LOG_ERROR "PowerShell是必需的，但没有找到"
	
    exit /b 1
)

set "TOOLS_DIR=%ROOT_DIR%\tools"
if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
call :LOG_INFO 工具目录:%TOOLS_DIR%

REM REM ::定义工具映射表(工具名 主URL 备用URL)
REM curl https://curl.se/windows/dl-8.15.0_1/curl-8.15.0_1-win64-mingw.zip https://curl.se/windows/dl-8.15.0_1/curl-8.15.0_1-win32-mingw.zip ^

(
echo unzip http://stahlworks.com/dev/unzip.exe http://stahlworks.com/dev/unzip.exe unzip.exe 
echo 7z https://www.7-zip.org/a/7zr.exe https://www.7-zip.org/a/7z2405-extra.7z 7z.exe 
REM echo curl https://curl.se/windows/dl-8.15.0_1/curl-8.15.0_1-win64-mingw.zip https://curl.se/windows/dl-8.15.0_1/curl-8.15.0_1-win32-mingw.zip curl.exe
) > "%ROOT_DIR%\tools\tool_map.tmp"


for /f "tokens=1-4" %%A in ('type "%ROOT_DIR%\tools\tool_map.tmp"') do (
    set "tool=%%A"
    set "primary_url=%%B"
    set "backup_url=%%C"
    set "target_file=%%D"
	
    if exist "%TOOLS_DIR%\!target_file!" (
        call :LOG_INFO "[√] 已安装:!tool!"
    ) else (
        call :LOG_INFO "[×] 正在安装:!tool!"
        
        :: Download attempt (with timeout and retry)		
        curl -L --connect-timeout 20 --retry 2 "!primary_url!" -o "%TOOLS_DIR%\!tool!.temp" || (
            call :LOG_WARN "[警告]主镜像不可用，尝试备用源..."
			
            curl -L --connect-timeout 20 --retry 2 "!backup_url!" -o "%TOOLS_DIR%\!tool!.temp" || (
                call :LOG_ERROR "无法获取!tool!"
				
                del "%TOOLS_DIR%\!tool!.temp" 2>nul
                exit /b 1
            )
        )

        :: File Processing		
        if "!primary_url:~-4!"==".zip" (
            if exist "%TOOLS_DIR%\unzip.exe" (
                "%TOOLS_DIR%\unzip.exe" -o "%TOOLS_DIR%\!tool!.temp" -d "%TOOLS_DIR%\!tool!_ext" >nul
                for /r "%TOOLS_DIR%\!tool!_ext" %%f in (!tool!*.exe) do (
                    if exist "%%f" copy /y "%%f" "%TOOLS_DIR%\" >nul
                )
            ) else (
                tar -xf "%TOOLS_DIR%\!tool!.temp" -C "%TOOLS_DIR%\" >nul
            )
        ) else (
            move /y "%TOOLS_DIR%\!tool!.temp" "%TOOLS_DIR%\!tool!.exe" >nul
        )
        del "%TOOLS_DIR%\!tool!.temp" 2>nul
        call :LOG_INFO "[√]安装完成"
		
    )
)

:: Final verification
for %%p in (unzip.exe 7z.exe) do (
    if not exist "%TOOLS_DIR%\%%p" (
        call :LOG_ERROR "缺失工具:%%p"
        exit /b 1
    )
)

:: 结束时删除临时文件 
del "%ROOT_DIR%\tools\tool_map.tmp" 2>nul 
:: 设置环境变量
set "PATH=!TOOLS_DIR!;!PATH!"
call :LOG_INFO "[完成]所有工具准备就绪"

goto :eof

:CONFIG
set "CONFIG_FILE=build-config.cfg"

if exist "!CONFIG_FILE!" (
    call :LOG_INFO "正在读取配置文件: !CONFIG_FILE!"   
    for /f "usebackq tokens=1* delims==" %%a in ("!CONFIG_FILE!") do (
        set "VAR_NAME=%%a"
        set "VAR_VALUE=%%b"
        
        :: 去除可能的引号和空格
        set "VAR_NAME=!VAR_NAME:"=!"
        set "VAR_VALUE=!VAR_VALUE:"=!"
        for /f "tokens=* delims= " %%v in ("!VAR_NAME!") do set "VAR_NAME=%%v"
        for /f "tokens=* delims= " %%v in ("!VAR_VALUE!") do set "VAR_VALUE=%%v"
        
        :: 检查变量名是否在配置列表中
        set "FOUND=0"
        for %%v in (ROOT_DIR PERL_DIR MINGW_DIR PYTHON_DIR OHOS_ARCH OHOS_API) do (
            if /i "!VAR_NAME!"=="%%v" (
                set "!VAR_NAME!=!VAR_VALUE!"
                set "FOUND=1"
            )
        )
        
        if !FOUND!==0 (
            call :LOG_WARNING "发现未知配置项: !VAR_NAME!=!VAR_VALUE!"
        )
    )
    
    call :LOG_INFO "配置文件读取完成"
) else (
    call :LOG_INFO "配置文件 !CONFIG_FILE! 不存在"
)

echo.
call :LOG_INFO "[配置向导]请输入以下信息（所有字段均为必填项）"

set "CONFIG_VARS=ROOT_DIR PERL_DIR MINGW_DIR PYTHON_DIR OHOS_ARCH OHOS_API"

:: 使用函数处理每个配置项
for %%v in (%CONFIG_VARS%) do (
    call :PROCESS_CONFIG_ITEM %%v
)

:: 最终验证
for %%v in (%CONFIG_VARS%) do (
    if not defined %%v (
        call :LOG_ERROR "%%v 必须配置"
        exit /b 1
    )
)

:: 保存配置
(
    for %%v in (%CONFIG_VARS%) do (
        echo %%v=!%%v!
    )
) > "!CONFIG_FILE!"

call :LOG_INFO "配置已保存到 !CONFIG_FILE!"
exit /b 0

:: ==============================================
:: 处理单个配置项的函数
:: ==============================================
:PROCESS_CONFIG_ITEM
set "VAR_NAME=%~1"
if defined %VAR_NAME% (
    set "CURRENT_VALUE=!%VAR_NAME%!"
) else (
    set "CURRENT_VALUE=未设置"
)

:INPUT_LOOP
set "USER_INPUT="
set /p "USER_INPUT=请输入 %VAR_NAME% (当前: !CURRENT_VALUE!): "

if "!USER_INPUT!"=="" (
    if defined %VAR_NAME% (
        call :LOG_INFO "%VAR_NAME% 保持原值: !CURRENT_VALUE!"
    ) else (
        call :LOG_ERROR "%VAR_NAME% 必须配置（不能为空）"
        goto INPUT_LOOP
    )
) else (
    set "%VAR_NAME%=!USER_INPUT!"
)

exit /b 0

:CHECK_ENV
:: 检查必要变量

echo.
call :LOG_INFO [检查]验证环境配置...
if not defined QT_DIR (
    call :LOG_ERROR 未配置QT_DIR环境变量
    exit /b 1
)

if not defined ROOT_DIR (
    call :LOG_ERROR 未配置ROOT_DIR环境变量
    exit /b 1
)

if not exist "!QT_DIR!\configure.bat" (
    call :LOG_ERROR 无效的Qt源码路径:!QT_DIR!
    exit /b 1
)

call :LOG_INFO "环境检查完成"

goto :eof

:DOWNLOAD_QT_AND_PATCH
where git >nul 2>&1 || (
    call :LOG_ERROR "Git工具缺失,Git未安装或未加入PATH"
	
	exit /b 1
)

set "QT_DIR=%ROOT_DIR%\qt5"
if not exist "%QT_DIR%\.git" (
	call :LOG_INFO "正在下载Qt源码(v5.15.12-lts-lgpl)..."
	
	git clone %QT_GIT_URL% %QT_DIR% -b v5.15.12-lts-lgpl --recursive %ERROR%
	
	if %ERRORLEVEL% neq 0 (
		call :LOG_ERROR "Qt源码下载失败,Git克隆Qt仓库失败"  
		
		exit /b 1
	)
) else (
    call :LOG_INFO "Qt源码仓库已存在，跳过下载"
	
    pushd "%QT_DIR%"
	
    call :LOG_INFO  "正在检查Qt仓库更新..."
	
	git clean -fdx 
	git reset --hard 
	git submodule foreach --recursive git clean -fdx 
	git submodule foreach --recursive git reset --hard 
	
    git pull origin v5.15.12-lts-lgpl 
    git submodule update --recursive 
	
	popd
)

set "QT_PATCH_PATH=%ROOT_DIR%\qtpatch"
if not exist "%ROOT_DIR%\qtpatch\.git" (
	call :LOG_INFO "正在下载Qt OpenHarmony patch..."
	
	git clone %QT_GIT_PATCH_URL% %QT_PATCH_PATH% -b master --recursive %ERROR%
	
	if %ERRORLEVEL% neq 0 (
		call :LOG_ERROR "Qt OpenHarmony patch下载失败,Git克隆Qt仓库失败"  
		
		exit /b 1
	)
) else (
    call :LOG_INFO "Qt OpenHarmony patch仓库已存在，跳过下载"
	
    pushd "%QT_PATCH_PATH%"
	
    call :LOG_INFO  "正在检查Qt OpenHarmony patch仓库更新..."
	
	git clean -fdx 
	git reset --hard 
	git submodule foreach --recursive git clean -fdx 
	git submodule foreach --recursive git reset --hard 
	
    git pull origin master 
    git submodule update --recursive
	
	popd
)

set "PATCH_PATH=%QT_PATCH_PATH%\patch\v5.15.12"

goto :eof

REM 下载OpenHarmony SDK (通过解析CI上的下载地址) 该函数暂时保留, 使用INSTALL_COMPONENT代替

:DOWNLOAD_SDK
echo.
call :LOG_INFO "[步骤1]准备OpenHarmony SDK..."
if not exist "%ROOT_DIR%" mkdir "%ROOT_DIR%" %ERROR%

:: 从TARGET_SDK提取文件名(兼容HTTP/FTP/本地路径)
set "SDK_PACKAGE=!TARGET_SDK!"
set "SDK_PACKAGE=!SDK_PACKAGE:*/=!"
set "SDK_PACKAGE=!SDK_PACKAGE:?=!"
set "SDK_PACKAGE=!SDK_PACKAGE:&=!"
for %%F in ("!SDK_PACKAGE!") do set "SDK_PACKAGE=%%~nxF"

:: 检查是否已下载
if exist "%ROOT_DIR%\%SDK_PACKAGE%" (
    call :LOG_INFO [信息]使用已下载的SDK包:%SDK_PACKAGE%
) else (
    call :LOG_INFO 正在下载:%SDK_PACKAGE%
    curl -L -o "%ROOT_DIR%\%SDK_PACKAGE%" "%TARGET_SDK%" %ERROR%
)

:: 提取版本号（如OpenHarmony_5.1.0.101）
for /f "tokens=1-3 delims=-." %%a in ("%SDK_PACKAGE%") do (
    set "OHOS_VERSION=%%a-%%b.%%c"
)

:: 提取解压目录名（如5.1.0.101）
set "UN_ZIP_DIR="
for /f "tokens=3 delims=-" %%a in ("%SDK_PACKAGE%") do (
    set "UN_ZIP_DIR=%%a"
)

if "%UN_ZIP_DIR%"=="" (
    call :LOG_ERROR 无法从SDK文件名提取版本信息
    exit /b 1
)

:: 提取SDK版本号（如5.1.0）
set "OHOS_SDK_VERSION="
for /f "tokens=2 delims=_" %%i in ("%UN_ZIP_DIR%") do (
    set "OHOS_SDK_VERSION=%%i"
)

:: 解压主SDK包
if not exist "%ROOT_DIR%\%UN_ZIP_DIR%" (
    call :LOG_INFO 正在解压到:%ROOT_DIR%\%UN_ZIP_DIR%
    mkdir "%ROOT_DIR%\%UN_ZIP_DIR%" %ERROR%
    tar -xzvf "%ROOT_DIR%\%SDK_PACKAGE%" -C "%ROOT_DIR%\%UN_ZIP_DIR%" %ERROR%
) else (
    call :LOG_INFO [信息]SDK已解压到:%ROOT_DIR%\%UN_ZIP_DIR%
)

REM :: 检查ohos-sdk目录是否存在（部分SDK包结构不同）
REM if not exist "%ROOT_DIR%\%UN_ZIP_DIR%\ohos-sdk" (
    REM echo %YELLOW%[警告]%NC% 未找到标准ohos-sdk目录，尝试直接解压
    REM tar -xzvf "%ROOT_DIR%\%SDK_PACKAGE%" -C "%ROOT_DIR%\%UN_ZIP_DIR%" %ERROR%
REM )

:: 动态检测native-windows包
set "NATIVE_WINDOWS="
for /f "delims=" %%a in ('dir "%ROOT_DIR%\%UN_ZIP_DIR%\windows" ^| findstr "native-windows"') do (
    for /f "tokens=4" %%i in ("%%a") do (
        set "NATIVE_WINDOWS=%%i"
    )
)

if defined NATIVE_WINDOWS (
   call :LOG_INFO [信息]检测到native-windows包:%NATIVE_WINDOWS%
    
    if not exist "%ROOT_DIR%\%UN_ZIP_DIR%\windows\native" (
        call :LOG_INFO 正在解压native-windows包...
        pushd "%ROOT_DIR%\%UN_ZIP_DIR%\windows"
		echo "%ROOT_DIR%\%UN_ZIP_DIR%\windows"
        "%TOOLS_DIR%\unzip.exe" -o "%NATIVE_WINDOWS%" -d "%ROOT_DIR%\%UN_ZIP_DIR%\windows" %ERROR%
        popd
    ) else (
        call :LOG_INFO [信息]native-windows已存在
    )
) else (
    call :LOG_ERROR 未找到native-windows包
    dir "%ROOT_DIR%\%UN_ZIP_DIR%\windows\native-windows*" /b
    exit /b 1
)

:: Set environment variables
set "OHOS_SDK_PATH=%ROOT_DIR%\%UN_ZIP_DIR%\windows"
set "LLVM_INSTALL_DIR=%OHOS_SDK_PATH%\native\llvm"
set "PATH=!PATH!;%LLVM_INSTALL_DIR%\bin"

call :LOG_INFO "[成功]SDK准备完成"
call :LOG_INFO "SDK主目录:%ROOT_DIR%\%UN_ZIP_DIR%"
call :LOG_INFO "工具链路径:%LLVM_INSTALL_DIR%"

goto :eof

:BUILD
call :LOG_INFO "[步骤2]编译Qt源码..."

call :CHECK_ENV %ERROR%

set "BUILD_DIR=%ROOT_DIR%\build_Qt_%OHOS_ARCH%_api!OHOS_API!"
set "QT_INSTALL_DIR=%ROOT_DIR%\Qt_%OHOS_ARCH%_api!OHOS_API!_bin"

call :LOG_INFO "编译目录:%BUILD_DIR%"
call :LOG_INFO "安装目录:%QT_INSTALL_DIR%"

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%" %ERROR%

pushd "%BUILD_DIR%"
call :LOG_INFO "正在配置Qt..."

call "%QT_DIR%\configure.bat" ^
    -platform win32-g++ ^
    -xplatform oh-clang ^
    -device-option OHOS_ARCH=%OHOS_ARCH% ^
    -opensource -confirm-license ^
    -nomake tests -nomake examples ^
    -prefix "%QT_INSTALL_DIR%" ^
    %DEFAULT_SKIP_PARAM% ^
    -opengl es2 -opengles3 -no-dbus -recheck-all -v 

:: Compile and log


for /f "tokens=2 delims==" %%A in ('wmic cpu get NumberOfLogicalProcessors /value ^| find "NumberOfLogicalProcessors"') do (
    set "threads=%%A"
)

call :LOG_INFO "正在编译Qt, 使用逻辑线程数:%threads%..."

mingw32-make -j%threads%
if %errorlevel% neq 0 (
    call :LOG_ERROR "Qt编译失败"
	
    exit /b %errorlevel%	
) else (
	call :LOG_INFO "[成功]Qt编译完成"
	echo.
)

mingw32-make install %ERROR%
popd

:: Copy the runtime dependencies
copy "%MINGW_DIR%\libstdc++-6.dll" "%QT_INSTALL_DIR%\bin\" %ERROR%
copy "%MINGW_DIR%\libgcc_s_seh-1.dll" "%QT_INSTALL_DIR%\bin\" %ERROR%
copy "%MINGW_DIR%\libwinpthread-1.dll" "%QT_INSTALL_DIR%\bin\" %ERROR%

goto :eof

:DEPLOY
echo.
call :LOG_INFO "[步骤3]打包部署..."

call :CHECK_ENV %ERROR%

:: 获取标准日期

for /f "tokens=2 delims==" %%d in ('wmic os get localdatetime /value') do (
    set "datetime=%%d"
)
set "ISO_DATE=%datetime:~0,8%" 

set "ZIP_FILE=%ROOT_DIR%\Qt_%OHOS_ARCH%_%ISO_DATE%.7z"
echo 正在创建压缩包: %ZIP_FILE%

%TOOLS_DIR%\7z.exe a -r -t7z "%ZIP_FILE%" "%QT_INSTALL_DIR%\*" 
if %errorlevel% neq 0 (
    call :LOG_ERROR "打包失败"	
    exit /b %errorlevel%	
) else (	
	call :LOG_INFO "[成功]打包完成:%ZIP_FILE%"
	echo.
)
goto :eof

:CLEAN
echo.
call :LOG_INFO "[清理]删除临时文件..."

if defined BUILD_DIR (
    if exist "!BUILD_DIR!" (
        call :LOG_INFO "删除编译目录:!BUILD_DIR!"
		
        rd /s /q "!BUILD_DIR!" 2>nul || (
            call :LOG_WARN "无法删除!BUILD_DIR!（可能被占用）"
			
            taskkill /f /im make.exe >nul 2>&1
            rd /s /q "!BUILD_DIR!" %ERROR%
        )
    )
) else (
	call :LOG_INFO "正在删除所有以 "build" 开头的目录..."
	for /f "delims=" %%D in ('dir /b /s /ad %ROOT_DIR%\build*') do do (
		call :LOG_INFO "正在删除: %%D"
		rd /s /q "%%D" 2>nul
		if !errorlevel! neq 0 (
			call :LOG_ERROR "无法删除: %%D"
		)
	)
)

if defined QT_INSTALL_DIR (
    if exist "!QT_INSTALL_DIR!" (
        call :LOG_INFO "删除安装目录:!QT_INSTALL_DIR!"
        rd /s /q "!QT_INSTALL_DIR!" %ERROR%
    )
)

if defined TEMP_DIR (
    if exist "!TEMP_DIR!" (
        call :LOG_INFO "删除缓存目录:!TEMP_DIR!"
        rd /s /q "!TEMP_DIR!" %ERROR%
    )
) else (
	if exist "!TEMP_DIR!" (
        call :LOG_INFO "删除缓存目录:!TEMP_DIR!"
        rd /s /q "!TEMP_DIR!" %ERROR%
    )
)

call :LOG_INFO "[完成]清理操作已完成"

exit /b 0

:FULL_PROCESS
REM call :DOWNLOAD_SDK %ERROR%

call :DOWNLOAD_QT_AND_PATCH %ERROR%

dir /a /b "%ROOT_DIR%\ohos-sdk" 2>nul | findstr . >nul
if %errorlevel% neq 0 (
    call :LOG_INFO "%ROOT_DIR%\ohos-sdk 文件夹为空,开始下载OpenHarmony SDK"
	
	call :INSTALL_COMPONENT native:!OHOS_API! %ERROR%
) else (
	set "OHOS_SDK_PATH=%ROOT_DIR%\ohos-sdk\!OHOS_API!"
	set "LLVM_INSTALL_DIR=%OHOS_SDK_PATH%\native\llvm"
	set "PATH=!PATH!;%LLVM_INSTALL_DIR%\bin"
    call :LOG_INFO "%ROOT_DIR%\ohos-sdk 文件夹不为空,跳过下载OpenHarmony SDK"
)

call apply-patch.bat -r %QT_DIR% -p !PATCH_PATH!
if %errorlevel% neq 0 (
    call :LOG_ERROR "应用Patch文件失败"
	
    exit /b %errorlevel%	
)

call :BUILD && (
	call :DEPLOY
) %ERROR%

REM goto CLEAN

exit /b 0
