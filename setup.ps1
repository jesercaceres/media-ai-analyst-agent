# =====================================================================
# setup.ps1 — Script de instalação para Python 3.14 no Windows
# =====================================================================
# Uso: .\setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "`n==> Criando ambiente virtual..." -ForegroundColor Cyan
if (Test-Path ".venv") {
    Remove-Item -Recurse -Force ".venv"
}
py -3.14 -m venv .venv

Write-Host "`n==> Ativando ambiente virtual..." -ForegroundColor Cyan
& ".venv\Scripts\Activate.ps1"

Write-Host "`n==> Atualizando pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# PyO3 0.24.x ainda não tem suporte oficial a Python 3.14.
# Esta variável instrui o compilador a usar a Stable ABI (abi3),
# que é forward-compatible e permite a compilação do pydantic-core.
Write-Host "`n==> Configurando compatibilidade PyO3 para Python 3.14..." -ForegroundColor Yellow
$env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY = "1"

Write-Host "`n==> Instalando dependências (pode demorar — pydantic-core compila do Rust)..." -ForegroundColor Cyan
pip install -r requirements.txt --prefer-binary

Write-Host "`n==> Instalação concluída!" -ForegroundColor Green
Write-Host "Para iniciar a API:" -ForegroundColor White
Write-Host "  uvicorn app.main:app --reload`n" -ForegroundColor Yellow
