# Re-runnable: sync ERP users (hash+salt only, no plaintext) into server Synapse (im.dpdc.co).
# Run from this PC (it reaches ERP SQL 10.10.12.52): powershell -File erp_user_sync.ps1
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$tmp = Join-Path $env:TEMP 'erp_users.json'
try {
  docker cp "$here\erp_user_export.py" element-messenger-synapse-1:/tmp/erp_user_export.py
  cmd /c "docker exec element-messenger-synapse-1 python /tmp/erp_user_export.py > `"$tmp`""
  if ($LASTEXITCODE) { throw 'ERP export failed' }
  scp "$here\erp_user_load.py" dpdc-ai-srv:erp_user_load.py
  cmd /c "ssh dpdc-ai-srv python3 erp_user_load.py < `"$tmp`""
} finally { Remove-Item $tmp -ErrorAction SilentlyContinue; ssh dpdc-ai-srv "rm -f erp_user_load.py" }