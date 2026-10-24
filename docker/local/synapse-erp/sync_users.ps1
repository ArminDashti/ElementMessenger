# Re-runnable ERP -> Synapse user sync. Add -Deactivate to actually deactivate users no longer eligible.
param([switch]$Deactivate)
$a = @(); if ($Deactivate) { $a += '--deactivate' }
Get-Content -Raw -Encoding utf8 "$PSScriptRoot\sync_users.py" | docker exec -i element-messenger-synapse-1 python - @a
