# Initialise le serveur MySQL 8.4 installe par winget (Oracle.MySQL) et
# l'enregistre comme service Windows demarrant automatiquement.
# A executer dans un PowerShell administrateur :
#   powershell -ExecutionPolicy Bypass -File scripts\install_mysql_service.ps1
# Le compte root est cree SANS mot de passe : lancez ensuite
#   python -m cadeaux init
# qui lui en attribue un.
param(
    [string]$BaseDir = "C:\Program Files\MySQL\MySQL Server 8.4",
    [string]$DataRoot = "C:\ProgramData\MySQL\MySQL Server 8.4",
    [string]$ServiceName = "MySQL84",
    [int]$Port = 3306,
    [string]$LogFile = ""
)
$ErrorActionPreference = "Stop"
if ($LogFile) { Start-Transcript -Path $LogFile -Force | Out-Null }

try {
    $mysqld = Join-Path $BaseDir "bin\mysqld.exe"
    $ini = Join-Path $DataRoot "my.ini"
    $dataDir = Join-Path $DataRoot "Data"

    if (-not (Test-Path $mysqld)) { throw "mysqld.exe introuvable dans $BaseDir" }

    if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
        Write-Host "Le service $ServiceName existe deja."
    } else {
        New-Item -ItemType Directory -Force $DataRoot | Out-Null
        $base = $BaseDir -replace '\\', '/'
        $data = $dataDir -replace '\\', '/'
        @"
[mysqld]
basedir="$base"
datadir="$data"
port=$Port
character-set-server=utf8mb4
collation-server=utf8mb4_0900_ai_ci

[client]
port=$Port
default-character-set=utf8mb4
"@ | Set-Content -Encoding ascii $ini

        if (-not (Test-Path $dataDir)) {
            Write-Host "Initialisation du dossier de donnees $dataDir ..."
            & $mysqld --defaults-file="$ini" --initialize-insecure --console
            if ($LASTEXITCODE -ne 0) { throw "Echec de l'initialisation de MySQL" }
        }

        Write-Host "Enregistrement du service $ServiceName ..."
        & $mysqld --install $ServiceName --defaults-file="$ini"
        if ($LASTEXITCODE -ne 0) { throw "Echec de l'enregistrement du service" }
    }

    Set-Service $ServiceName -StartupType Automatic
    Start-Service $ServiceName
    Write-Host "Service $ServiceName : $((Get-Service $ServiceName).Status)"
} finally {
    if ($LogFile) { Stop-Transcript | Out-Null }
}
