param([Parameter(Mandatory = $true)][string]$Origin)
$ErrorActionPreference = 'Stop'
$authority = ([uri]$Origin).Authority
if ($authority -notmatch '^127\.0\.0\.1:\d+$') { throw 'Expected a disposable loopback origin' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$element = [System.Windows.Automation.AutomationElement]
$scope = [System.Windows.Automation.TreeScope]
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$root = $element::RootElement
$title = [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, 'WayToGo 旅伴手札')
$deadline = [DateTime]::UtcNow.AddSeconds(5)
while ([DateTime]::UtcNow -lt $deadline) {
    foreach ($hostProcess in @(Get-Process -Name ShellExperienceHost,ShellHost -ErrorAction SilentlyContinue)) {
        $hostFilter = [System.Windows.Automation.PropertyCondition]::new($element::ProcessIdProperty, $hostProcess.Id)
        foreach ($panel in $root.FindAll($scope::Children, $hostFilter)) {
            $candidate = $panel.FindFirst($scope::Descendants, $title)
            for ($i = 0; $null -ne $candidate -and $i -lt 5; $i++) {
                # Do not act on a different profile, another site's toast, or an existing trip.
                $sender = [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, $authority)
                $current = $candidate.Current.Name
                if ($current.Contains($authority) -or $candidate.FindFirst($scope::Descendants, $sender)) {
                    $invoke = $null
                    if ($candidate.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern, [ref]$invoke)) {
                        $invoke.Invoke()
                        'clicked-isolated-toast'
                        exit 0
                    }
                }
                $candidate = $walker.GetParent($candidate)
            }
        }
    }
    Start-Sleep -Milliseconds 250
}
'no-matching-actionable-banner'
