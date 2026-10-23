# 编译 Shadow Eye，安装到模拟器并启用无障碍服务
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$repo = Split-Path $PSScriptRoot
$eye  = Join-Path $repo "eye"
$adb  = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
$apk  = Join-Path $eye "app\build\outputs\apk\debug\app-debug.apk"

# 用 Android Studio 自带的 JDK（只对这次运行生效，不改系统设置）
$jbr = "D:\Android\jbr"
if (-not (Test-Path "$jbr\bin\java.exe")) {
    $studio = Get-Process studio64 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($studio) { $jbr = Join-Path (Split-Path (Split-Path $studio.Path)) "jbr" }
}
if (-not (Test-Path "$jbr\bin\java.exe")) { "找不到 Android Studio 自带的 JDK"; exit 1 }
$env:JAVA_HOME = $jbr

"--- 编译 Shadow Eye"
Push-Location $eye
& .\gradlew.bat assembleDebug --offline 2>&1 | Select-Object -Last 8 | ForEach-Object { "$_" }
$built = ($LASTEXITCODE -eq 0)
if (-not $built) {
    "--- 离线编译没成功，改成联网再试一次（走本机代理 127.0.0.1:7890）"
    $proxyArgs = @('-Dhttps.proxyHost=127.0.0.1', '-Dhttps.proxyPort=7890', '-Dhttp.proxyHost=127.0.0.1', '-Dhttp.proxyPort=7890')
    & .\gradlew.bat assembleDebug @proxyArgs 2>&1 | Select-Object -Last 15 | ForEach-Object { "$_" }
    $built = ($LASTEXITCODE -eq 0)
}
Pop-Location
if (-not $built -or -not (Test-Path $apk)) { "编译失败，上面的输出就是原因"; exit 1 }
"APK: " + (Get-Item $apk).Length + " 字节，更新于 " + (Get-Item $apk).LastWriteTime

"--- 安装到模拟器"
& $adb install -r $apk 2>&1 | ForEach-Object { "$_" }

"--- 启用无障碍服务"
& $adb shell settings put secure enabled_accessibility_services com.shadowagent.eye/com.shadowagent.eye.EyeService
& $adb shell settings put secure accessibility_enabled 1
Start-Sleep -Seconds 4
"服务列表: " + (& $adb shell settings get secure enabled_accessibility_services)

"--- 请求一次导出并读取"
& $adb shell am broadcast -a com.shadowagent.eye.DUMP -p com.shadowagent.eye --es id 1 | Out-Null
Start-Sleep -Seconds 2
$text = (& $adb exec-out run-as com.shadowagent.eye cat files/ui.xml) -join "`n"
if ($text -match "<displays") {
    "导出成功，文件长度: " + $text.Length
    exit 0
}
"没读到有效的导出内容: " + $text
"可以运行 adb logcat -d -s ShadowEye 看看"
exit 1
