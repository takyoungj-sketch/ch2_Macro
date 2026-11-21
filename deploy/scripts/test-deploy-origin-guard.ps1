# 배포 가드만 확인한다. 배포 스크립트 본체와 서버에는 접속하지 않는다.
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "deploy-origin-guard.ps1")

$passed = 0
$failed = 0

function Assert-Reject([scriptblock]$Action, [string]$Expect, [string]$Name) {
  try {
    & $Action | Out-Null
    Write-Output "FAIL $Name (통과함)"
    $script:failed++
  } catch {
    $text = $_.Exception.Message
    if ($text -like "*$Expect*") {
      Write-Output "PASS $Name"
      $script:passed++
    } else {
      Write-Output "FAIL $Name ($text)"
      $script:failed++
    }
  }
}

function New-SampleRepo([string]$Dir, [string]$Remote) {
  git init -b main $Dir | Out-Null
  git -C $Dir config user.email "ops012@example.com"
  git -C $Dir config user.name "ops012"
  Set-Content -Path (Join-Path $Dir "a.txt") -Value "a" -Encoding ascii
  git -C $Dir add a.txt | Out-Null
  git -C $Dir commit -m "a" | Out-Null
  if ($Remote) {
    git -C $Dir remote add origin $Remote
  }
}

$deploy = Get-Content -Raw (Join-Path $PSScriptRoot "deploy-from-windows.ps1")
$guardAt = $deploy.IndexOf("Invoke-DeployOriginGuard")
$sshAt = $deploy.IndexOf("ssh")
$scpAt = $deploy.IndexOf("scp")
if ($guardAt -ge 0 -and $sshAt -gt $guardAt -and $scpAt -gt $guardAt) {
  Write-Output "PASS guard-before-ssh"
  $passed++
} else {
  Write-Output "FAIL guard-before-ssh"
  $failed++
}

Assert-Reject {
  Invoke-DeployOriginGuard -RepoRoot "D:\ch2\ch2_Macro"
} "원본 폴더" "origin-folder"

$tmp = Join-Path $env:TEMP ("ops012-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $bare = Join-Path $tmp "bare.git"
  $work = Join-Path $tmp "work"
  git init --bare -b main $bare | Out-Null
  New-SampleRepo $work $bare
  git -C $work push -u origin HEAD:main | Out-Null

  $same = @(Invoke-DeployOriginGuard -RepoRoot $work)
  if ($same[0] -like "DEPLOY *" -and ($same -notcontains "origin/main이 아닌 커밋을 배포한다")) {
    Write-Output "PASS head-matches-origin"
    $passed++
  } else {
    Write-Output "FAIL head-matches-origin ($same)"
    $failed++
  }

  Set-Content -Path (Join-Path $work "extra.txt") -Value "untracked" -Encoding ascii
  $untracked = @(Invoke-DeployOriginGuard -RepoRoot $work)
  if ($untracked[0] -like "DEPLOY *") {
    Write-Output "PASS untracked-allowed"
    $passed++
  } else {
    Write-Output "FAIL untracked-allowed"
    $failed++
  }
  Remove-Item (Join-Path $work "extra.txt")

  Add-Content -Path (Join-Path $work "a.txt") -Value "dirty" -Encoding ascii
  Assert-Reject {
    Invoke-DeployOriginGuard -RepoRoot $work
  } "추적 파일" "dirty-tracked"
  git -C $work checkout -- a.txt | Out-Null

  Add-Content -Path (Join-Path $work "a.txt") -Value "next" -Encoding ascii
  git -C $work add a.txt | Out-Null
  git -C $work commit -m "b" | Out-Null
  $head = (git -C $work rev-parse HEAD).Trim()
  Assert-Reject {
    Invoke-DeployOriginGuard -RepoRoot $work
  } "origin/main" "head-differs"

  $allowed = @(Invoke-DeployOriginGuard -RepoRoot $work -AllowCommit $head)
  if ($allowed -contains "origin/main이 아닌 커밋을 배포한다") {
    Write-Output "PASS allow-exact"
    $passed++
  } else {
    Write-Output "FAIL allow-exact ($allowed)"
    $failed++
  }

  Assert-Reject {
    Invoke-DeployOriginGuard -RepoRoot $work -AllowCommit ("a" * 40)
  } "origin/main" "allow-mismatch"
  Assert-Reject {
    Invoke-DeployOriginGuard -RepoRoot $work -AllowCommit $head.Substring(0, 12)
  } "origin/main" "allow-short"

  $broken = Join-Path $tmp "broken"
  New-SampleRepo $broken "D:\ch2\ops012-no-such-remote.git"
  Assert-Reject {
    Invoke-DeployOriginGuard -RepoRoot $broken
  } "fetch" "fetch-fails"
} finally {
  Remove-Item -Recurse -Force $tmp
}

Write-Output "RESULT passed=$passed failed=$failed"
if ($failed -ne 0) { exit 1 }
