<#
.SYNOPSIS
  Starts LocalStack (S3 + DynamoDB), the Django backend, and the frontend
  dev server together - a fully local stand-in for the whole app, with no
  real AWS account (or LocalStack account) required.

.DESCRIPTION
  Pinned to localstack/localstack:4.14.0, deliberately not :latest -
  starting with the 2026.03.0 calendar-versioned release, even LocalStack's
  free-tier image requires a LOCALSTACK_AUTH_TOKEN (a free account) just to
  start. 4.14.0 is the last semver release before that requirement, so this
  stays genuinely account-free - at the cost of no further LocalStack bug
  fixes/AWS API coverage beyond that release. Revisit this pin if that
  tradeoff stops being worth it.

  Does NOT simulate Auth0 or the Lambda/API Gateway deployment shape:
    - Auth0JWTAuthentication talks to a real Auth0 tenant regardless (see
      docs/auth0-setup.md). Every /api/... view requires it (permission_classes
      = [IsAuthenticated]) - including /api/market/... (Profile/Prices/Search),
      not just accounts/pies/watchlists/holdings/transactions/identity. Only
      /health/ and the admin work with no token at all. Pass
      -Auth0Domain/-Auth0Audience (or export $env:AUTH0_DOMAIN/
      $env:AUTH0_AUDIENCE first) so the server can verify a token - but you
      still need a genuine Auth0-issued token in hand (e.g. via the frontend's
      real login flow) to call anything under /api/... regardless.
    - The backend runs via `manage.py runserver`, the same Django app
      `equicast_api.lambda_handler.handler` wraps in prod - Lambda/API
      Gateway themselves aren't part of this loop, so iteration stays
      instant instead of a rebuild-and-redeploy cycle per change.

  By default (no -Start* switch) this starts all three: LocalStack, the
  backend, and the frontend. Pass one or more of -StartLocalStack/
  -StartBackend/-StartFrontend to start only that subset instead - e.g.
  -StartFrontend alone just runs `npm run dev`, with no Docker/AWS CLI/uv
  checks at all. The backend and frontend each run in their own new
  PowerShell window (so their logs stay readable and separate from this
  one); this window just waits and tears everything down - both spawned
  windows (via taskkill /T, since npm/uv each fork child processes a plain
  Stop-Process wouldn't reach) and the LocalStack container - on Ctrl+C.

.PARAMETER StartLocalStack
  Start LocalStack and provision its buckets/table. Combine with
  -StartBackend/-StartFrontend, or use alone to just stand up LocalStack
  (e.g. to drive it with your own backend/frontend elsewhere).

.PARAMETER StartBackend
  Run the Django backend (`manage.py migrate` then `runserver`) in its own
  window. Assumes LocalStack is already reachable at localhost:4566 (its
  fixed default port) if not also passing -StartLocalStack this run.

.PARAMETER StartFrontend
  Run the frontend dev server (`npm run dev`) in its own window.

.PARAMETER SeedMarketData
  Only applies with -StartLocalStack: also ingests all three asset classes
  via their CLI/config (equicast-fx/packages/fx/config/fx_pairs.yaml,
  equicast-stock/packages/stock/config/stocks.yaml,
  equicast-etf/packages/etf/config/etfs.yaml) and builds/uploads each
  asset class's catalog into LocalStack, so /api/market/... has something
  to return. These CLIs hit live Yahoo Finance data, so this makes real
  network calls even though everything else stays local.

.PARAMETER FullLoad
  Only applies with -SeedMarketData: passes --full-load through to each
  ingestion CLI, fetching each ticker/pair's entire available price
  history (one price.parquet per year) instead of just the current year.
  Slower and more network-heavy - omit unless you specifically need
  multi-year price data locally.

.PARAMETER Reset
  Only applies with -StartLocalStack: removes any existing LocalStack
  container (and its data) before starting a fresh one.

.PARAMETER Stop
  Stops and removes the LocalStack container, then exits without starting
  anything. The backend/frontend windows (if any are still open from a
  previous run) aren't tracked across invocations - close them directly.

.EXAMPLE
  .\scripts\local-dev.ps1
.EXAMPLE
  .\scripts\local-dev.ps1 -StartLocalStack -StartBackend
.EXAMPLE
  .\scripts\local-dev.ps1 -StartFrontend
.EXAMPLE
  .\scripts\local-dev.ps1 -SeedMarketData -FullLoad
.EXAMPLE
  .\scripts\local-dev.ps1 -Auth0Domain equicast.eu.auth0.com -Auth0Audience https://api.equicast.app
.EXAMPLE
  .\scripts\local-dev.ps1 -Stop
#>

param(
    [switch]$StartLocalStack,
    [switch]$StartBackend,
    [switch]$StartFrontend,
    [switch]$SeedMarketData,
    [switch]$FullLoad,
    [switch]$Reset,
    [switch]$Stop,
    [string]$Auth0Domain = $env:AUTH0_DOMAIN,
    [string]$Auth0Audience = $env:AUTH0_AUDIENCE,
    [string]$Region = "eu-west-1",
    [string]$MarketDataBucket = "equicast-market-data-dev",
    [string]$UserDataBucket = "equicast-user-data-dev",
    [string]$UserProfilesTable = "equicast-user-profiles-dev"
)

# No -Start* switch given - run the full stack (LocalStack + backend +
# frontend), matching this script's original all-in-one default.
if (-not ($StartLocalStack -or $StartBackend -or $StartFrontend)) {
    $StartLocalStack = $true
    $StartBackend = $true
    $StartFrontend = $true
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ContainerName = "equicast-localstack"
$Endpoint = "http://localhost:4566"

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Stop-LocalStackContainer {
    docker rm -f $ContainerName *> $null
}

function Stop-SpawnedProcess {
    param($Process, [string]$Label)
    if (-not $Process) { return }
    try {
        if (-not $Process.HasExited) {
            Write-Host "Stopping $Label (PID $($Process.Id))..."
            # taskkill /T, not Stop-Process: npm/uv each fork their own
            # child process (node/python) on Windows, and Stop-Process only
            # ever reaches the immediate powershell.exe wrapper, leaving
            # the actual dev server running as an orphan.
            taskkill /PID $Process.Id /T /F *> $null
        }
    } catch {
        # Already gone - fine.
    }
}

if ($StartLocalStack -or $Stop) {
    if (-not (Test-Command docker)) {
        Write-Error "Docker is required (LocalStack runs as a container). Install Docker Desktop and make sure it's running, then re-run."
        exit 1
    }

    docker info *> $null
    $dockerRunning = ($LASTEXITCODE -eq 0)

    if ($Stop) {
        if (-not $dockerRunning) {
            Write-Host "Docker Desktop doesn't appear to be running - nothing to stop."
            exit 0
        }
        Write-Host "Stopping and removing $ContainerName..."
        Stop-LocalStackContainer
        Write-Host "Done."
        exit 0
    }

    if (-not $dockerRunning) {
        Write-Error "Docker Desktop doesn't appear to be running. Start it, then re-run."
        exit 1
    }

    if (-not (Test-Command aws)) {
        Write-Error "AWS CLI is required to provision LocalStack's buckets/table (e.g. 'winget install Amazon.AWSCLI'), then re-run."
        exit 1
    }
}

if (($StartBackend -or ($StartLocalStack -and $SeedMarketData)) -and -not (Test-Command uv)) {
    Write-Error "uv is required to run the backend / ingestion CLIs. Install it: https://docs.astral.sh/uv/"
    exit 1
}

if ($StartFrontend) {
    if (-not (Test-Command npm)) {
        Write-Error "npm is required to start the frontend (Node.js). Install Node.js, then re-run."
        exit 1
    }
    if (-not (Test-Path (Join-Path $RepoRoot "frontend\node_modules"))) {
        Write-Warning "frontend/node_modules not found - run 'npm install' in frontend/ first; the frontend window will show the failure otherwise."
    }
}

# Fake creds + boto3 endpoint overrides - equicast-core's clients call
# plain boto3.client(...)/boto3.resource(...) with no endpoint_url hook of
# their own, this relies on boto3>=1.28's AWS_ENDPOINT_URL_* env var
# support (pinned boto3>=1.35.9 here) to route them at LocalStack instead,
# with no code change. Harmless to set even when this run isn't the one
# starting LocalStack (e.g. -StartBackend alone, against a LocalStack
# already running from a previous invocation).
$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_REGION = $Region
$env:AWS_ENDPOINT_URL_S3 = $Endpoint
$env:AWS_ENDPOINT_URL_DYNAMODB = $Endpoint
$env:MARKET_DATA_BUCKET = $MarketDataBucket
$env:USER_DATA_BUCKET = $UserDataBucket
$env:USER_PROFILES_TABLE = $UserProfilesTable

if ($StartBackend) {
    if (-not $Auth0Domain -or -not $Auth0Audience) {
        Write-Warning "AUTH0_DOMAIN/AUTH0_AUDIENCE not set: every /api/... endpoint (including /api/market/...) requires a valid Auth0 Bearer token and will 401 without one - only /health/ and the admin work with no token. Pass -Auth0Domain/-Auth0Audience, or set them in your shell first - see docs/auth0-setup.md."
    } else {
        $env:AUTH0_DOMAIN = $Auth0Domain
        $env:AUTH0_AUDIENCE = $Auth0Audience
    }
}

$backendProcess = $null
$frontendProcess = $null

try {
    if ($StartLocalStack) {
        if ($Reset) {
            Write-Host "Removing existing $ContainerName for a clean slate..."
            docker rm -f $ContainerName | Out-Null
        }

        # --- Start LocalStack ---------------------------------------------
        $allContainers = @((docker ps -a --format "{{.Names}}") -split "`n" | Where-Object { $_ -ne "" })
        $runningContainers = @((docker ps --format "{{.Names}}") -split "`n" | Where-Object { $_ -ne "" })

        if ($runningContainers -contains $ContainerName) {
            Write-Host "$ContainerName is already running."
        } elseif ($allContainers -contains $ContainerName) {
            Write-Host "Starting existing $ContainerName container..."
            docker start $ContainerName | Out-Null
        } else {
            Write-Host "Creating $ContainerName (localstack/localstack:4.14.0, S3 + DynamoDB)..."
            docker run -d --name $ContainerName -p 4566:4566 `
                -e SERVICES=s3,dynamodb `
                -e DEFAULT_REGION=$Region `
                localstack/localstack:4.14.0 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Failed to start the LocalStack container - check 'docker logs $ContainerName' or whether port 4566 is already in use."
                exit 1
            }
        }

        # --- Wait for S3 + DynamoDB to be ready -----------------------------
        Write-Host "Waiting for LocalStack to be ready" -NoNewline
        $ready = $false
        for ($i = 0; $i -lt 60; $i++) {
            try {
                $health = Invoke-RestMethod -Uri "$Endpoint/_localstack/health" -TimeoutSec 2
                if ($health.services.s3 -in @("available", "running") -and $health.services.dynamodb -in @("available", "running")) {
                    $ready = $true
                    break
                }
            } catch {
                # Not up yet - expected during the first few seconds.
            }
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 2
        }
        Write-Host ""
        if (-not $ready) {
            Write-Error "LocalStack didn't report S3/DynamoDB ready in time. Check 'docker logs $ContainerName'."
            exit 1
        }
        Write-Host "LocalStack is up at $Endpoint."

        # --- Provision the S3 buckets and DynamoDB table ---------------------
        function Confirm-Bucket {
            param([string]$Name)
            aws --endpoint-url $Endpoint s3api head-bucket --bucket $Name | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Creating bucket $Name..."
                aws --endpoint-url $Endpoint s3api create-bucket --bucket $Name `
                    --region $Region --create-bucket-configuration LocationConstraint=$Region | Out-Null
            } else {
                Write-Host "Bucket $Name already exists."
            }
        }
        Confirm-Bucket $MarketDataBucket
        Confirm-Bucket $UserDataBucket

        aws --endpoint-url $Endpoint dynamodb describe-table --table-name $UserProfilesTable | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Creating DynamoDB table $UserProfilesTable..."
            # Matches infra/modules/dynamodb_table: PAY_PER_REQUEST billing, hash
            # key user_id (String), no sort key.
            aws --endpoint-url $Endpoint dynamodb create-table `
                --table-name $UserProfilesTable `
                --attribute-definitions AttributeName=user_id,AttributeType=S `
                --key-schema AttributeName=user_id,KeyType=HASH `
                --billing-mode PAY_PER_REQUEST | Out-Null
        } else {
            Write-Host "Table $UserProfilesTable already exists."
        }

        # --- Optionally seed all three asset classes' catalogs ---------------
        if ($SeedMarketData) {
            # Each pipeline package shares the same CLI shape (--config/--out
            # [--full-load]) and writes <asset_class>=<TICKER>/... under its own
            # ./output, which equicast-core-build-catalog then reads to build that
            # asset class's catalog.json.
            $pipelines = @(
                @{ AssetClass = "fx";    Package = "fx";    Cli = "equicast-fx";    Config = "config\fx_pairs.yaml" },
                @{ AssetClass = "stock"; Package = "stock"; Cli = "equicast-stock"; Config = "config\stocks.yaml" },
                @{ AssetClass = "etf";   Package = "etf";   Cli = "equicast-etf";   Config = "config\etfs.yaml" }
            )

            foreach ($pipeline in $pipelines) {
                Write-Host "Seeding $($pipeline.AssetClass) market data ($($pipeline.Config)) into $MarketDataBucket..."
                Push-Location (Join-Path $RepoRoot "packages\$($pipeline.Package)")

                # equicast-core-build-catalog globs every <asset_class>=*/profile.parquet
                # under --output-dir, regardless of what's in this run's config -
                # a stale ticker from an earlier manual run (different config,
                # different day) would otherwise silently leak into the catalog
                # alongside whatever this run actually ingested.
                if (Test-Path .\output) {
                    Remove-Item -Recurse -Force .\output
                }

                # --config (a file), not --pairs-json/--tickers-json: inline JSON
                # with embedded double quotes gets mangled by PowerShell's
                # native-command argument marshalling on Windows (the quotes don't
                # survive). Array splatting here (not a single interpolated
                # string) is what keeps --full-load conditional without needing
                # any manual argument-quoting either.
                $ingestArgs = @("run", $pipeline.Cli, "--config", $pipeline.Config, "--out", ".\output")
                if ($FullLoad) { $ingestArgs += "--full-load" }
                uv @ingestArgs
                if ($LASTEXITCODE -ne 0) {
                    Pop-Location
                    Write-Error "$($pipeline.Cli) failed (exit $LASTEXITCODE) - see output above."
                    exit 1
                }

                aws --endpoint-url $Endpoint s3 cp .\output\ "s3://$MarketDataBucket/" --recursive
                Pop-Location

                Push-Location (Join-Path $RepoRoot "packages\core")
                uv run equicast-core-build-catalog --asset-class $pipeline.AssetClass `
                    --output-dir "..\$($pipeline.Package)\output" --bucket $MarketDataBucket
                Pop-Location
            }
        }
    }

    if ($StartBackend) {
        Write-Host ""
        Write-Host "Starting the Django backend in a new window:"
        Write-Host "  MARKET_DATA_BUCKET  = $MarketDataBucket"
        Write-Host "  USER_DATA_BUCKET    = $UserDataBucket"
        Write-Host "  USER_PROFILES_TABLE = $UserProfilesTable"
        $backendProcess = Start-Process powershell `
            -ArgumentList "-NoExit", "-Command", "uv run manage.py migrate; uv run manage.py runserver" `
            -WorkingDirectory (Join-Path $RepoRoot "backend") -PassThru
        Write-Host "Backend:  http://localhost:8000"
    }

    if ($StartFrontend) {
        Write-Host ""
        Write-Host "Starting the frontend dev server in a new window..."
        $frontendProcess = Start-Process powershell `
            -ArgumentList "-NoExit", "-Command", "npm run dev" `
            -WorkingDirectory (Join-Path $RepoRoot "frontend") -PassThru
        Write-Host "Frontend: http://localhost:5173"
    }

    Write-Host ""
    Write-Host "Press Ctrl+C to stop everything this script started."
    while ($true) {
        Start-Sleep -Seconds 1
    }
} finally {
    Stop-SpawnedProcess -Process $frontendProcess -Label "frontend"
    Stop-SpawnedProcess -Process $backendProcess -Label "backend"
    if ($StartLocalStack) {
        Write-Host "Stopping LocalStack ($ContainerName)..."
        Stop-LocalStackContainer
        Write-Host "Stopped."
    }
}
