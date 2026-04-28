param(
    [string]$Repository = "timoshinoleg-eng/restobot",
    [string]$IssueListPath = "PRODUCTION_ISSUE_LIST.md",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Assert-CommandAvailable {
    param([string]$CommandName)
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Command '$CommandName' is not available in PATH."
    }
}

function Parse-IssueSections {
    param([string]$Path)

    $content = Get-Content $Path -Raw
    $pattern = '(?ms)^##\s+\d+\.\s+(?<title>.+?)\r?\n(?<body>.*?)(?=^##\s+\d+\.|\z)'
    $matches = [System.Text.RegularExpressions.Regex]::Matches($content, $pattern)

    $issues = @()
    foreach ($match in $matches) {
        $title = $match.Groups["title"].Value.Trim()
        $body = $match.Groups["body"].Value.Trim()
        if ($title -and $body) {
            $issues += [PSCustomObject]@{
                Title = $title
                Body  = $body
            }
        }
    }
    return $issues
}

Assert-CommandAvailable -CommandName "gh"

if (-not (Test-Path $IssueListPath)) {
    throw "Issue list file not found: $IssueListPath"
}

$issues = Parse-IssueSections -Path $IssueListPath

if ($issues.Count -eq 0) {
    throw "No issues were parsed from $IssueListPath"
}

foreach ($issue in $issues) {
    Write-Host "==> $($issue.Title)"
    if ($DryRun) {
        Write-Host "---"
        Write-Host $issue.Body
        Write-Host "---"
        continue
    }

    $tempFile = [System.IO.Path]::GetTempFileName()
    try {
        Set-Content -Path $tempFile -Value $issue.Body -Encoding utf8
        gh issue create `
            --repo $Repository `
            --title $issue.Title `
            --body-file $tempFile | Out-Host
    }
    finally {
        Remove-Item $tempFile -ErrorAction SilentlyContinue
    }
}
