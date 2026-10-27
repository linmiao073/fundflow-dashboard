# update_site.ps1 - refresh fund-flow dashboard and publish to GitHub Pages
# steps: collect board flow -> collect sentiment -> build data.js -> commit & push main + gh-pages
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"

$WS   = "C:\Users\game-netease\AppData\Roaming\LobsterAI\openclaw\state\workspace-stockexpert"
$SITE = "C:\Users\game-netease\lobsterai\project\fundflow"
$LOG  = Join-Path $SITE "update.log"

function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Write-Output $line
  Add-Content -Path $LOG -Value $line -Encoding UTF8
}

Log "=== start ==="

Set-Location $WS
& node "scripts\collect_node2.js" 2>&1 | ForEach-Object { Log "flow: $_" }

$rawPath = Join-Path $WS "data\daily_flow_raw.json"
if (-not (Test-Path $rawPath)) { Log "ERROR missing daily_flow_raw.json"; exit 1 }

$flowCount = (& python -c "import json,io;print(json.load(io.open(r'$rawPath',encoding='utf-8')).get('flowCount',0))") 2>$null
Log "flowCount=$flowCount"
if ([int]$flowCount -lt 400) { Log "ERROR incomplete collection ($flowCount/496), skip publish"; exit 2 }

& node "$WS\scripts\collect_sentiment.js" 2>&1 | ForEach-Object { Log "sent: $_" }

Set-Location $SITE
& python "export_data.py" 2>&1 | ForEach-Object { Log "export: $_" }

$today = Get-Date -Format "yyyy-MM-dd"
git add -A 2>&1 | Out-Null
git -c core.quotepath=false commit -m "data: $today fund flow update" 2>&1 | ForEach-Object { Log "git: $_" }
git push origin main 2>&1 | ForEach-Object { Log "push main: $_" }
git push -f origin "main:gh-pages" 2>&1 | ForEach-Object { Log "push gh-pages: $_" }

Log "=== done ==="
