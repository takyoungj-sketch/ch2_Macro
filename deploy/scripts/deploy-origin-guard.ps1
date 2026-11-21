# 배포할 폴더를 서버에 접속하기 전에 확인한다.
# 원본 폴더, 추적 파일의 미커밋 변경, origin/main과 다른 HEAD, fetch 실패는 거부한다.
function Invoke-DeployOriginGuard {
  param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [string]$AllowCommit = ""
  )

  $root = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd('\', '/')
  $originFolder = [System.IO.Path]::GetFullPath("D:\ch2\ch2_Macro").TrimEnd('\', '/')
  Push-Location $root
  $previousPrompt = $env:GIT_TERMINAL_PROMPT
  try {
    $env:GIT_TERMINAL_PROMPT = "0"
    $hash = (git rev-parse HEAD).Trim()
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $hash -or -not $branch) {
      throw "배포 거부: 커밋을 확인하지 못했습니다."
    }
    Write-Output "DEPLOY $hash $branch $root"

    if ([string]::Equals($root, $originFolder, [stringComparison]::OrdinalIgnoreCase)) {
      throw "배포 거부: 원본 폴더에서는 배포하지 않습니다. ($root)"
    }

    $porcelain = @(git status --porcelain --untracked-files=normal)
    if ($LASTEXITCODE -ne 0) {
      throw "배포 거부: 작업 트리 상태를 확인하지 못했습니다."
    }
    $tracked = @($porcelain | Where-Object { $_ -and -not "$_".StartsWith("??") })
    if ($tracked.Count -gt 0) {
      throw "배포 거부: 추적 파일에 커밋되지 않은 변경이 있습니다."
    }

    git fetch origin
    if ($LASTEXITCODE -ne 0) {
      throw "배포 거부: git fetch origin에 실패했습니다. 확인하지 못한 커밋은 배포하지 않습니다."
    }
    $remote = (git rev-parse origin/main).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $remote) {
      throw "배포 거부: origin/main을 확인하지 못했습니다."
    }
    if ($hash -ne $remote) {
      $allowed = "$AllowCommit".Trim()
      if ($allowed -and $allowed -eq $hash) {
        Write-Output "origin/main이 아닌 커밋을 배포한다"
      } else {
        throw "배포 거부: HEAD가 origin/main과 다릅니다. 승인한 커밋이면 -AllowCommit 값이 HEAD 전체 해시와 같아야 합니다."
      }
    }
  } finally {
    $env:GIT_TERMINAL_PROMPT = $previousPrompt
    Pop-Location
  }
}
