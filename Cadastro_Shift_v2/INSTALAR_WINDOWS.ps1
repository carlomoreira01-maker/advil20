$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot
$probe = Join-Path $PSScriptRoot 'instalacao_aux.py'
Write-Host 'Cadastro Assistido Shift 2.2 - instalacao local' -ForegroundColor Cyan
Write-Host 'A internet sera usada somente para instalar Python, bibliotecas e o mecanismo OCR. Nenhum documento e enviado.'
function Find-Python {
    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
        'python.exe'
    )) {
        try {
            $result = & $candidate $probe python 2>$null
            if ($LASTEXITCODE -eq 0 -and $result -and (Test-Path ([string]$result))) { return [string]$result }
        } catch {}
    }
    try {
        $result = & py -3.12 $probe python 2>$null
        if ($LASTEXITCODE -eq 0 -and $result) { return [string]$result }
    } catch {}
    return $null
}
try {
    $python = Find-Python
    if (-not $python) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw 'Instale Python 3.12 de https://www.python.org/downloads/windows/ marcando Add Python to PATH. Depois execute este instalador novamente.'
        }
        Write-Host 'Instalando Python 3.12 pelo Windows Package Manager...'
        & winget install --exact --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
        $python = Find-Python
        if (-not $python) { throw 'Python nao localizado. Feche esta janela e execute INSTALAR_WINDOWS.bat novamente.' }
    }
    Write-Host "Python: $python"
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        & $python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar o ambiente Python.' }
    }
    $venv = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    & $venv -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar bibliotecas. Confira a conexao e execute este instalador novamente.' }
    $ocr = & $venv $probe localizar-ocr
    if (-not $ocr) {
        Write-Host 'Tesseract nao localizado. Se ja estiver instalado, selecione tesseract.exe (por exemplo, em Downloads\TESSERACT). Cancele para tentar instalar pelo winget.'
        $ocr = & $venv $probe selecionar-ocr
    }
    if (-not $ocr) {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host 'Instalando Tesseract OCR (o Windows pode pedir autorizacao de administrador)...'
            & winget install --exact --id UB-Mannheim.TesseractOCR --source winget --accept-package-agreements --accept-source-agreements
        }
        $ocr = & $venv $probe localizar-ocr
        if (-not $ocr) { throw 'Instale Tesseract pela pagina https://github.com/UB-Mannheim/tesseract/wiki e execute este instalador novamente. Os idiomas portugues e ingles ja acompanham este pacote.' }
    }
    & $venv diagnostico.py
    if ($LASTEXITCODE -ne 0) { throw 'O diagnostico encontrou um problema. Leia a mensagem acima antes de continuar.' }
    try {
        $shell=New-Object -ComObject WScript.Shell
        $shortcut=$shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Cadastro Assistido Shift v2.lnk'))
        $shortcut.TargetPath=Join-Path $PSScriptRoot 'INICIAR_WINDOWS.bat'
        $shortcut.WorkingDirectory=$PSScriptRoot
        $shortcut.Save()
    } catch { Write-Host 'Atalho nao criado. Use INICIAR_WINDOWS.bat dentro desta pasta.' }
    Write-Host 'Instalacao concluida. Abra INICIAR_WINDOWS.bat ou o atalho na area de trabalho.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
