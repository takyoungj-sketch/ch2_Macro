# OPS-013. The deploy script is not run and the server is not contacted.
$ErrorActionPreference = "Stop"
$passed = 0
$failed = 0

function Pass([string]$Name) {
  Write-Output "PASS $Name"
  $script:passed++
}

function Fail([string]$Name, [string]$Detail) {
  Write-Output "FAIL $Name ($Detail)"
  $script:failed++
}

$phrase = -join @(0xB85C, 0xADF8, 0xC778, 0xC774, 0x20, 0xD544, 0xC694, 0xD569, 0xB2C8, 0xB2E4, 0x2E | ForEach-Object { [char]$_ })
$utf8 = [System.Text.Encoding]::UTF8.GetBytes($phrase)
$mis = [System.Text.Encoding]::GetEncoding(949).GetString($utf8)
$parts = $mis.Split([char]32)
if ($mis -ne $phrase -and $parts.Length -eq 2 -and $parts[0].Length -eq 6 -and $parts[1].Length -eq 8) {
  Pass "before-cp949-misread"
} else {
  Fail "before-cp949-misread" $mis.Length
}
$shown = [System.Text.Encoding]::ASCII.GetString([System.Text.Encoding]::ASCII.GetBytes($mis))
$expectedShown = ("?" * 6) + " " + ("?" * 8)
if ($shown -eq $expectedShown) {
  Pass "before-console-question-marks"
} else {
  Fail "before-console-question-marks" $shown
}
if (-not ($shown -eq $phrase)) {
  Pass "before-check-fails"
} else {
  Fail "before-check-fails" "question marks matched the phrase"
}

$ps1 = Join-Path $PSScriptRoot "deploy-from-windows.ps1"
$raw = [System.IO.File]::ReadAllText($ps1)
$hereAt = $raw.IndexOf("`$verifyBash = @'")
$hereEnd = $raw.IndexOf("'@", $hereAt)
if ($hereAt -lt 0 -or $hereEnd -lt 0) {
  Fail "here-string-found" "markers missing"
  exit 1
}
$here = $raw.Substring($hereAt, $hereEnd - $hereAt)
$hereBytes = [System.Text.Encoding]::UTF8.GetBytes($here)
$high = @($hereBytes | Where-Object { $_ -gt 127 })
if ($high.Length -eq 0) {
  Pass "here-string-ascii"
} else {
  Fail "here-string-ascii" ("non-ascii " + $high.Length)
}

function Get-PyBlock([string]$Source, [string]$Marker) {
  $at = $Source.IndexOf($Marker)
  if ($at -lt 0) { throw "missing $Marker" }
  $at = $Source.IndexOf("<<'PY'", $at)
  $at = $Source.IndexOf("`n", $at) + 1
  $end = $Source.IndexOf("`nPY", $at)
  return $Source.Substring($at, $end - $at).Replace("`r", "")
}

$tmp = Join-Path $env:TEMP ("ops013-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $bodyFile = (Join-Path $tmp "body.json").Replace("\", "/")
  $respFile = (Join-Path $tmp "resp.json").Replace("\", "/")
  $bodyCode = Get-PyBlock $here "built regression gate"
  $bodyCode = $bodyCode.Replace("/tmp/built_reg_body.json", $bodyFile)
  $checkCode = Get-PyBlock $here 'python3 - "$CODE"'
  $checkCode = $checkCode.Replace("/tmp/built_reg_smoke.json", $respFile)
  $bodyPy = Join-Path $tmp "body.py"
  $checkPy = Join-Path $tmp "check.py"
  [System.IO.File]::WriteAllText($bodyPy, $bodyCode)
  [System.IO.File]::WriteAllText($checkPy, $checkCode)

  & python $bodyPy
  if ($LASTEXITCODE -ne 0) { throw "body python failed" }
  $bodyJson = [System.IO.File]::ReadAllText($bodyFile)
  $addr1 = -join @(0xCDA9, 0xCCAD, 0xBD81, 0xB3C4 | ForEach-Object { [char]$_ })
  $addr2 = -join @(0xCCAD, 0xC8FC, 0xC2DC | ForEach-Object { [char]$_ })
  $addr4 = -join @(0xAC00, 0xACBD, 0xB3D9 | ForEach-Object { [char]$_ })
  if ($bodyJson.Contains($addr1) -and $bodyJson.Contains($addr2) -and $bodyJson.Contains($addr4)) {
    Pass "body-addresses"
  } else {
    Fail "body-addresses" "missing address"
  }

  function Invoke-Gate([string]$Code, [string]$Detail) {
    & python -c "import json,sys; json.dump({'detail': sys.argv[1]}, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False)" $Detail $respFile
    if ($LASTEXITCODE -ne 0) { throw "mock write failed" }
    & python $checkPy $Code | Out-Null
    return $LASTEXITCODE
  }

  $ok = Invoke-Gate "401" $phrase
  if ($ok -eq 0) { Pass "fixed-401-phrase" } else { Fail "fixed-401-phrase" "exit $ok" }
  $wrong = Invoke-Gate "401" "different"
  if ($wrong -ne 0) { Pass "fixed-wrong-phrase-fails" } else { Fail "fixed-wrong-phrase-fails" "exit 0" }
  $http200 = Invoke-Gate "200" $phrase
  if ($http200 -ne 0) { Pass "fixed-200-fails" } else { Fail "fixed-200-fails" "exit 0" }
} finally {
  Remove-Item -Recurse -Force $tmp
}

Write-Output ("RESULT passed=" + $passed + " failed=" + $failed)
if ($failed -ne 0) { exit 1 }
exit 0
