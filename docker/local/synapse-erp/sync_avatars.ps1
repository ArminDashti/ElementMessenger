# Re-runnable ERP personnel photo -> Synapse avatar sync (same source as dev-portal Users directory).
param([switch]$DryRun, [int]$Limit = 0)
$a = @()
if ($DryRun) { $a += '--dry-run' }
if ($Limit -gt 0) { $a += '--limit'; $a += "$Limit" }
Get-Content -Raw -Encoding utf8 "$PSScriptRoot\sync_avatars.py" | docker exec -i element-messenger-synapse-1 python - @a
