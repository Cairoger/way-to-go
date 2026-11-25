param([switch]$OnlyExternal)
$ErrorActionPreference = 'Stop'
$stage = 'D:\WayToGo\.local\acceptance-retest-cada651'
$expected = if ($OnlyExternal) { Join-Path $stage 'wiki-retry-pytest' } else { $stage }
if (-not (Test-Path -LiteralPath $expected)) { return }
$root = (Resolve-Path -LiteralPath $expected).Path
if ($root -ne $expected -or (Get-Item -Force -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected staging directory' }
$pending = [Collections.Generic.Stack[string]]::new()
$pending.Push($root)
while ($pending.Count) {
    foreach ($entry in Get-ChildItem -Force -LiteralPath $pending.Pop()) {
        if (-not $entry.FullName.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Path outside audit subtree' }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $target = [IO.Path]::GetFullPath([string]$entry.Target, [IO.Path]::GetDirectoryName($entry.FullName))
            $shared = $entry.FullName -eq (Join-Path $stage 'source\frontend\node_modules') -and $entry.LinkType -eq 'Junction' -and $target -eq 'D:\WayToGo\frontend\node_modules'
            $nextBundle = $entry.FullName -eq (Join-Path $stage 'source\frontend\.next\standalone\node_modules') -and $entry.LinkType -eq 'SymbolicLink' -and $target -eq 'D:\WayToGo\frontend\node_modules'
            $fixture = $entry.LinkType -eq 'SymbolicLink' -and $entry.Name.EndsWith('current') -and $target.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)
            if (-not ($shared -or $nextBundle -or $fixture)) { throw ('Unexpected link ' + $entry.FullName) }
            if ($entry.PSIsContainer) { [IO.Directory]::Delete($entry.FullName) } else { [IO.File]::Delete($entry.FullName) }
        } elseif ($entry.PSIsContainer) {
            $pending.Push($entry.FullName)
        }
    }
}
if ($root -ne $expected) { throw 'Unexpected final path' }
Remove-Item -Recurse -Force -LiteralPath $root
if ((Test-Path -LiteralPath $root) -or -not (Test-Path -LiteralPath 'D:\WayToGo\frontend\node_modules\@playwright\test')) { throw 'Cleanup verification failed' }
Write-Output ('Removed isolated test directory ' + $root)

