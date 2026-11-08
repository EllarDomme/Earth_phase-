# shot_doubao.ps1 —— 用 CDP 直接给豆包窗口拍一张，看看它现在是什么状态
$ErrorActionPreference = "Stop"

$tabs = Invoke-RestMethod "http://127.0.0.1:9225/json/list" -TimeoutSec 8
$page = $tabs | Where-Object { $_.type -eq 'page' -and $_.webSocketDebuggerUrl } | Select-Object -First 1
if (-not $page) { throw "没有可用的页面" }

Write-Output ("目标: " + $page.title)
Write-Output ("网址: " + $page.url)

$ws = [System.Net.WebSockets.ClientWebSocket]::new()
$ct = [System.Threading.CancellationToken]::None
$ws.ConnectAsync([Uri]$page.webSocketDebuggerUrl, $ct).Wait(10000) | Out-Null

function Send-Cdp([string]$json) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $seg = [ArraySegment[byte]]::new($bytes)
    $ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).Wait(10000) | Out-Null
}

function Recv-Cdp([int]$wantId, [int]$timeoutMs = 20000) {
    $buf = New-Object byte[] 4194304
    $seg = [ArraySegment[byte]]::new($buf)
    $deadline = (Get-Date).AddMilliseconds($timeoutMs)
    while ((Get-Date) -lt $deadline) {
        $sb = [Text.StringBuilder]::new()
        do {
            $r = $ws.ReceiveAsync($seg, $ct).Result
            $sb.Append([Text.Encoding]::UTF8.GetString($buf, 0, $r.Count)) | Out-Null
        } while (-not $r.EndOfMessage)
        $msg = $sb.ToString()
        if ($msg -match '"id"\s*:\s*' + $wantId) { return $msg }
    }
    return $null
}

Send-Cdp '{"id":1,"method":"Page.enable"}'
Recv-Cdp 1 8000 | Out-Null

Send-Cdp '{"id":2,"method":"Page.captureScreenshot","params":{"format":"png"}}'
$resp = Recv-Cdp 2 20000
if (-not $resp) { throw "截图没有返回" }

$obj = $resp | ConvertFrom-Json
$b64 = $obj.result.data
$out = "E:\DeskTop\地球\v2\_doubao_state.png"
[IO.File]::WriteAllBytes($out, [Convert]::FromBase64String($b64))
Write-Output ("已保存: " + $out + "  " + [math]::Round((Get-Item $out).Length / 1KB, 1) + " KB")

$ws.Dispose()
