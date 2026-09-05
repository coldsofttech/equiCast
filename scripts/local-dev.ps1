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
      $env:AUTH0_AUDIENCE first) so the server can verify a token. With
      -StartFrontend, the same values plus -Auth0ClientId (or
      $env:AUTH0_CLIENT_ID) are exported as VITE_AUTH0_DOMAIN/
      VITE_AUTH0_CLIENT_ID/VITE_AUTH0_AUDIENCE for the frontend's spawned
      process too - Vite gives an already-set environment variable priority
      over any .env.local, so no file is needed just for local dev - letting
      you log in for real through the frontend and obtain a genuine
      Auth0-issued token end to end.
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

  LocalStack itself keeps no state across a container removal, and this
  script always removes it on teardown - so accounts/pies/etc. created
  against it (the user-data bucket + user-profiles table, both real app
  data, not market data) would otherwise vanish every time you stop and
  restart. To avoid that, they're backed up to disk (data/localstack-seed/,
  gitignored - see -SeedMarketData's help for the same folder's other use)
  right before every teardown (Ctrl+C, or -Stop - both wait for/handle
  Ctrl+C the same deliberate way, see the wait loop below) and restored
  right after every fresh container start - only a clean stop is covered,
  killing the process or Docker itself isn't. -Reset also clears this
  backup, for a genuinely fresh start.

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
  via their CLI/config (equicast-fx/packages/fx/config/fx_pairs.dev.yaml,
  equicast-stock/packages/stock/config/stocks.dev.yaml,
  equicast-etf/packages/etf/config/etfs.dev.yaml) and builds/uploads each
  asset class's catalog into LocalStack, so /api/market/... has something
  to return. These CLIs hit live Yahoo Finance data, so this makes real
  network calls even though everything else stays local. The three
  pipelines run in parallel (PowerShell background jobs), not one after
  another.

  LocalStack keeps no data across container removal (a fresh
  `docker run`, or `-Reset`), so everything this ingests would otherwise
  need re-fetching from Yahoo Finance every single run. To avoid that,
  a successful seed is mirrored to disk under data/localstack-seed/ (see
  .gitignore) once every pipeline finishes; the next run with
  -SeedMarketData restores straight from that folder (via `aws s3 sync`,
  no network calls, no ingestion CLIs) instead of re-seeding, as long as
  -FullLoad matches what was cached. Pass -ForceReseed to ignore the cache
  and ingest fresh data anyway (e.g. the dev config files changed, or the
  cached data is just stale).

.PARAMETER FullLoad
  Only applies with -SeedMarketData: passes --full-load through to each
  ingestion CLI, fetching each ticker/pair's entire available price
  history (one price.parquet per year) instead of just the current year.
  Slower and more network-heavy - omit unless you specifically need
  multi-year price data locally. Also part of the seed cache's reuse check
  - switching this on/off from what's cached forces a fresh ingest, same
  as -ForceReseed.

.PARAMETER ForceReseed
  Only applies with -SeedMarketData: skips the data/localstack-seed/ cache
  reuse check and re-ingests from Yahoo Finance regardless, refreshing the
  cache afterward.

.PARAMETER Reset
  Only applies with -StartLocalStack: removes any existing LocalStack
  container (and its data) before starting a fresh one. Also clears the
  on-disk user-data/user-profiles-table backup described above, so this is
  a genuinely clean slate rather than one that gets silently repopulated
  from yesterday's data right after. Does not touch the separate
  market-data seed cache - see -ForceReseed for that.

.PARAMETER Stop
  Backs up the app's own user-data/user-profiles-table (see above), then
  stops and removes the LocalStack container, then exits without starting
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
  .\scripts\local-dev.ps1 -SeedMarketData -ForceReseed
.EXAMPLE
  .\scripts\local-dev.ps1 -Auth0Domain equicast.eu.auth0.com -Auth0Audience https://api.equicast.app -Auth0ClientId <client-id>
.EXAMPLE
  .\scripts\local-dev.ps1 -Stop
#>

param(
    [switch]$StartLocalStack,
    [switch]$StartBackend,
    [switch]$StartFrontend,
    [switch]$SeedMarketData,
    [switch]$FullLoad,
    [switch]$ForceReseed,
    [switch]$Reset,
    [switch]$Stop,
    [string]$Auth0Domain = $env:AUTH0_DOMAIN,
    [string]$Auth0Audience = $env:AUTH0_AUDIENCE,
    [string]$Auth0ClientId = $env:AUTH0_CLIENT_ID,
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

# Persists a seeded market-data bucket, and (separately) the app's own
# user-data bucket/user-profiles table, across LocalStack container
# removals - gitignored, since this is purely a local dev-loop speedup/
# data-preservation measure, not something to ship.
$SeedCacheDir = Join-Path $RepoRoot "data\localstack-seed"
$SeedCacheMarketData = Join-Path $SeedCacheDir "market-data"
$SeedInfoPath = Join-Path $SeedCacheDir "seed-info.json"
$AppDataCachePath = Join-Path $SeedCacheDir "user-data.json"
$UserProfilesTableCachePath = Join-Path $SeedCacheDir "user-profiles-table.json"

# Fake creds + boto3 endpoint overrides - equicast-core's clients call plain
# boto3.client(...)/boto3.resource(...) with no endpoint_url hook of their
# own, this relies on boto3>=1.28's AWS_ENDPOINT_URL_* env var support
# (pinned boto3>=1.35.9 here) to route them at LocalStack instead, with no
# code change. Set unconditionally and this early (before even -Stop's
# early exit below) since the AWS CLI itself needs *some* credentials
# configured to talk to LocalStack at all, including for -Stop's/this
# script's own backup-before-teardown calls - harmless to set even when
# this run isn't the one starting LocalStack (e.g. -StartBackend alone,
# against a LocalStack already running from a previous invocation).
$env:AWS_ACCESS_KEY_ID = "test"
$env:AWS_SECRET_ACCESS_KEY = "test"
$env:AWS_REGION = $Region
# Forces the AWS CLI's own response formatting (not boto3 - equicast-core
# never shells out to it) to "json" regardless of what a machine's
# ~/.aws/config happens to have set for `output` - one machine tested here
# had `output = none` set globally (for an unrelated project), which made
# several of this script's own `aws` calls (get-object/put-object among
# them) exit non-zero ("Unknown output type: none") despite succeeding,
# which this script's own $LASTEXITCODE checks then wrongly treated as a
# real failure.
$env:AWS_DEFAULT_OUTPUT = "json"
$env:AWS_ENDPOINT_URL_S3 = $Endpoint
$env:AWS_ENDPOINT_URL_DYNAMODB = $Endpoint
$env:MARKET_DATA_BUCKET = $MarketDataBucket
$env:USER_DATA_BUCKET = $UserDataBucket
$env:USER_PROFILES_TABLE = $UserProfilesTable

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Stop-LocalStackContainer {
    docker rm -f $ContainerName *> $null
}

# LocalStack itself keeps no state across a container removal, and this
# script's own teardown always removes it (see Stop-LocalStackContainer) -
# so unlike market-data (explicitly (re-)seeded via -SeedMarketData), the
# app's own user-data bucket (accounts/pies/watchlists/holdings/
# transactions - all S3 JSON via equicast-core) and user-profiles
# DynamoDB table are backed up to disk right before every teardown and
# restored right after every fresh container start, so creating a couple
# of accounts, stopping, and starting again doesn't lose them. Only a
# clean stop is covered - a crash/kill before the `finally`/-Stop path
# runs means whatever changed since the last clean stop isn't backed up.
function Backup-LocalStackAppData {
    Write-Host "Backing up user data (accounts/pies/etc.) to $SeedCacheDir..."
    New-Item -ItemType Directory -Force -Path $SeedCacheDir | Out-Null

    # NOT `aws s3 sync` to a real directory: a real Auth0 user id contains
    # a literal "|" (e.g. "auth0|abc123"), which every equicast-core client
    # bakes straight into its S3 keys (accounts/<user_id>.json, etc.), and
    # "|" is an illegal character in a Windows file name. `sync` silently
    # fails per-file in that case - it creates the "accounts" directory,
    # then errors trying to create the actual file, and that error was
    # being thrown away here. Reading every object's key/content into one
    # JSON manifest instead - the key only ever appears as a JSON string
    # value, never as a literal path component - sidesteps that (and every
    # other S3-legal-but-Windows-illegal character) entirely.
    $objects = @()
    $listJson = aws --endpoint-url $Endpoint s3api list-objects-v2 --bucket $UserDataBucket --output json 2>$null
    if ($LASTEXITCODE -eq 0 -and $listJson) {
        # No pagination handling (list-objects-v2 caps at 1000 keys/page) -
        # fine for this bucket's size in local dev, not meant to scale further.
        $keys = ($listJson | ConvertFrom-Json).Contents | ForEach-Object { $_.Key }
        foreach ($key in $keys) {
            $objectFile = [System.IO.Path]::GetTempFileName()
            try {
                aws --endpoint-url $Endpoint s3api get-object --bucket $UserDataBucket --key "$key" $objectFile *> $null
                if ($LASTEXITCODE -eq 0) {
                    $bytes = [System.IO.File]::ReadAllBytes($objectFile)
                    $objects += @{ key = $key; contentBase64 = [Convert]::ToBase64String($bytes) }
                }
            } finally {
                Remove-Item -Force $objectFile -ErrorAction SilentlyContinue
            }
        }
    }
    @{ objects = $objects } | ConvertTo-Json -Depth 10 | Set-Content -Path $AppDataCachePath

    # A plain `scan` (no pagination handling) - fine for this table's size
    # (one small item per user) in local dev, not meant to scale further.
    $scanJson = aws --endpoint-url $Endpoint dynamodb scan --table-name $UserProfilesTable --output json 2>$null
    if ($LASTEXITCODE -eq 0 -and $scanJson) {
        Set-Content -Path $UserProfilesTableCachePath -Value $scanJson
    }
}

function Restore-LocalStackAppData {
    if (Test-Path $AppDataCachePath) {
        Write-Host "Restoring cached user data from $AppDataCachePath..."
        $cache = Get-Content $AppDataCachePath -Raw | ConvertFrom-Json
        foreach ($object in $cache.objects) {
            $objectFile = [System.IO.Path]::GetTempFileName()
            try {
                $bytes = [Convert]::FromBase64String($object.contentBase64)
                [System.IO.File]::WriteAllBytes($objectFile, $bytes)
                aws --endpoint-url $Endpoint s3api put-object --bucket $UserDataBucket --key "$($object.key)" --body $objectFile | Out-Null
            } finally {
                Remove-Item -Force $objectFile -ErrorAction SilentlyContinue
            }
        }
    }

    if (Test-Path $UserProfilesTableCachePath) {
        Write-Host "Restoring cached user-profiles table items from $UserProfilesTableCachePath..."
        $scan = Get-Content $UserProfilesTableCachePath -Raw | ConvertFrom-Json
        foreach ($item in $scan.Items) {
            $itemFile = [System.IO.Path]::GetTempFileName()
            try {
                $itemJson = $item | ConvertTo-Json -Depth 20 -Compress
                # Set-Content -Encoding utf8 writes a UTF-8 BOM in Windows
                # PowerShell 5.1 - the AWS CLI's `file://` JSON parser chokes
                # on that BOM ("Expected: '=', received: ..."), so this
                # writes plain BOM-less UTF-8 instead.
                [System.IO.File]::WriteAllText($itemFile, $itemJson, [System.Text.UTF8Encoding]::new($false))
                aws --endpoint-url $Endpoint dynamodb put-item --table-name $UserProfilesTable --item "file://$itemFile" | Out-Null
            } finally {
                Remove-Item -Force $itemFile -ErrorAction SilentlyContinue
            }
        }
    }
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

    if (-not $dockerRunning) {
        if ($Stop) {
            Write-Host "Docker Desktop doesn't appear to be running - nothing to stop."
            exit 0
        }
        Write-Error "Docker Desktop doesn't appear to be running. Start it, then re-run."
        exit 1
    }

    if (-not (Test-Command aws)) {
        Write-Error "AWS CLI is required to provision LocalStack's buckets/table (e.g. 'winget install Amazon.AWSCLI'), then re-run."
        exit 1
    }

    if ($Stop) {
        $runningNow = @((docker ps --format "{{.Names}}") -split "`n" | Where-Object { $_ -ne "" })
        if ($runningNow -contains $ContainerName) {
            Backup-LocalStackAppData
        }
        Write-Host "Stopping and removing $ContainerName..."
        Stop-LocalStackContainer
        Write-Host "Done."
        exit 0
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

if ($StartBackend) {
    if (-not $Auth0Domain -or -not $Auth0Audience) {
        Write-Warning "AUTH0_DOMAIN/AUTH0_AUDIENCE not set: every /api/... endpoint (including /api/market/...) requires a valid Auth0 Bearer token and will 401 without one - only /health/ and the admin work with no token. Pass -Auth0Domain/-Auth0Audience, or set them in your shell first - see docs/auth0-setup.md."
    } else {
        $env:AUTH0_DOMAIN = $Auth0Domain
        $env:AUTH0_AUDIENCE = $Auth0Audience
    }
}

if ($StartFrontend) {
    if (-not $Auth0Domain -or -not $Auth0Audience -or -not $Auth0ClientId) {
        Write-Warning "VITE_AUTH0_DOMAIN/VITE_AUTH0_CLIENT_ID/VITE_AUTH0_AUDIENCE not set: RequireAuth will show a 'not configured' message instead of a login button. Pass -Auth0Domain/-Auth0Audience/-Auth0ClientId, or set AUTH0_DOMAIN/AUTH0_AUDIENCE/AUTH0_CLIENT_ID in your shell first (or create frontend/.env.local yourself) - see docs/auth0-setup.md."
    } else {
        # Vite gives an already-set environment variable priority over
        # frontend/.env.local, so the spawned `npm run dev` process picks
        # these up with no file needed - same tenant/API as the backend
        # above (see frontend/src/auth/auth0Config.js).
        $env:VITE_AUTH0_DOMAIN = $Auth0Domain
        $env:VITE_AUTH0_CLIENT_ID = $Auth0ClientId
        $env:VITE_AUTH0_AUDIENCE = $Auth0Audience
    }
}

$backendProcess = $null
$frontendProcess = $null

try {
    if ($StartLocalStack) {
        if ($Reset) {
            Write-Host "Removing existing $ContainerName for a clean slate..."
            docker rm -f $ContainerName | Out-Null
            # -Reset means "start over" for the app's own data too, not just
            # the container - otherwise Restore-LocalStackAppData below would
            # immediately repopulate the "fresh" container from yesterday's
            # backup. The market-data seed cache is untouched here - that
            # one's expensive (real Yahoo Finance calls) and has its own
            # dedicated -ForceReseed switch instead.
            if (Test-Path $AppDataCachePath) { Remove-Item -Force $AppDataCachePath }
            if (Test-Path $UserProfilesTableCachePath) { Remove-Item -Force $UserProfilesTableCachePath }
        }

        # --- Start LocalStack ---------------------------------------------
        $allContainers = @((docker ps -a --format "{{.Names}}") -split "`n" | Where-Object { $_ -ne "" })
        $runningContainers = @((docker ps --format "{{.Names}}") -split "`n" | Where-Object { $_ -ne "" })
        $wasAlreadyRunning = $runningContainers -contains $ContainerName

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

        # --- Restore any previously backed-up app data ------------------------
        # Only when this run is the one that just created/started the
        # container - if it was already running (e.g. a second -StartBackend-
        # only invocation attaching to a LocalStack still up from before),
        # whatever's live in there is newer than any on-disk backup, and
        # restoring would overwrite it with stale data.
        if (-not $wasAlreadyRunning) {
            Restore-LocalStackAppData
        }

        # --- Optionally seed all three asset classes' catalogs ---------------
        if ($SeedMarketData) {
            # A previous run's seed, if its -FullLoad mode matches this run's -
            # see the cache-write side below for what gets written here and why.
            $cachedSeedInfo = $null
            if (-not $ForceReseed -and (Test-Path $SeedInfoPath)) {
                try {
                    $cachedSeedInfo = Get-Content $SeedInfoPath -Raw | ConvertFrom-Json
                } catch {
                    Write-Warning "Couldn't read $SeedInfoPath - ignoring the cache and re-seeding."
                    $cachedSeedInfo = $null
                }
            }

            if ($cachedSeedInfo -and ($cachedSeedInfo.FullLoad -eq [bool]$FullLoad) -and (Test-Path $SeedCacheMarketData)) {
                Write-Host "Restoring cached market data (seeded $($cachedSeedInfo.SeededAt), FullLoad=$($cachedSeedInfo.FullLoad)) from $SeedCacheMarketData - pass -ForceReseed to ingest fresh data instead."
                aws --endpoint-url $Endpoint s3 sync $SeedCacheMarketData "s3://$MarketDataBucket/" | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    Write-Error "Restoring the cached seed into $MarketDataBucket failed (exit $LASTEXITCODE)."
                    exit 1
                }
            } else {
                # Each pipeline package shares the same CLI shape (--config/--out
                # [--full-load]) and writes <asset_class>=<TICKER>/... under its own
                # ./output, which equicast-core-build-catalog then reads to build
                # that asset class's catalog.json. The three run as parallel
                # background jobs (each its own process, so no Push-Location/
                # $env: interference between them) rather than one after another -
                # they're independent, network-bound CLI calls, so there's nothing
                # to gain from serializing them.
                $pipelines = @(
                    @{ AssetClass = "fx";    Package = "fx";    Cli = "equicast-fx";    Config = "config\fx_pairs.dev.yaml" },
                    @{ AssetClass = "stock"; Package = "stock"; Cli = "equicast-stock"; Config = "config\stocks.dev.yaml" },
                    @{ AssetClass = "etf";   Package = "etf";   Cli = "equicast-etf";   Config = "config\etfs.dev.yaml" }
                )

                Write-Host "Seeding fx/stock/etf market data into $MarketDataBucket in parallel (FullLoad=$([bool]$FullLoad))..."
                $seedJobs = foreach ($pipeline in $pipelines) {
                    Start-Job -Name $pipeline.AssetClass -ScriptBlock {
                        param($RepoRoot, $Endpoint, $MarketDataBucket, $FullLoad, $pipeline)

                        Set-Location (Join-Path $RepoRoot "packages\$($pipeline.Package)")

                        # equicast-core-build-catalog globs every
                        # <asset_class>=*/profile.parquet under --output-dir,
                        # regardless of what's in this run's config - a stale
                        # ticker from an earlier manual run (different config,
                        # different day) would otherwise silently leak into the
                        # catalog alongside whatever this run actually ingested.
                        if (Test-Path .\output) {
                            Remove-Item -Recurse -Force .\output
                        }

                        # --config (a file), not --pairs-json/--tickers-json:
                        # inline JSON with embedded double quotes gets mangled by
                        # PowerShell's native-command argument marshalling on
                        # Windows (the quotes don't survive). Array splatting
                        # here (not a single interpolated string) is what keeps
                        # --full-load conditional without needing any manual
                        # argument-quoting either.
                        $ingestArgs = @("run", $pipeline.Cli, "--config", $pipeline.Config, "--out", ".\output")
                        if ($FullLoad) { $ingestArgs += "--full-load" }
                        uv @ingestArgs
                        if ($LASTEXITCODE -ne 0) {
                            throw "$($pipeline.Cli) failed (exit $LASTEXITCODE)."
                        }

                        aws --endpoint-url $Endpoint s3 cp .\output\ "s3://$MarketDataBucket/" --recursive
                        if ($LASTEXITCODE -ne 0) {
                            throw "Uploading $($pipeline.AssetClass) output to $MarketDataBucket failed (exit $LASTEXITCODE)."
                        }

                        Set-Location (Join-Path $RepoRoot "packages\core")
                        uv run equicast-core-build-catalog --asset-class $pipeline.AssetClass `
                            --output-dir "..\$($pipeline.Package)\output" --bucket $MarketDataBucket
                        if ($LASTEXITCODE -ne 0) {
                            throw "Building the $($pipeline.AssetClass) catalog failed (exit $LASTEXITCODE)."
                        }
                    } -ArgumentList $RepoRoot, $Endpoint, $MarketDataBucket, [bool]$FullLoad, $pipeline
                }

                $seedJobs | Wait-Job | Out-Null
                $seedFailed = $false
                foreach ($job in $seedJobs) {
                    Write-Host "--- $($job.Name) ---"
                    Receive-Job -Job $job -ErrorAction Continue
                    if ($job.State -eq "Failed") { $seedFailed = $true }
                    Remove-Job -Job $job
                }
                if ($seedFailed) {
                    Write-Error "One or more market-data seed jobs failed - see output above."
                    exit 1
                }

                # --- Cache the freshly seeded bucket for next time ---------------
                Write-Host "Caching seeded market data to $SeedCacheMarketData for reuse next time..."
                New-Item -ItemType Directory -Force -Path $SeedCacheDir | Out-Null
                if (Test-Path $SeedCacheMarketData) {
                    Remove-Item -Recurse -Force $SeedCacheMarketData
                }
                aws --endpoint-url $Endpoint s3 sync "s3://$MarketDataBucket/" $SeedCacheMarketData | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Caching the seeded bucket to $SeedCacheMarketData failed (exit $LASTEXITCODE) - next run will re-seed from scratch."
                } else {
                    @{ FullLoad = [bool]$FullLoad; SeededAt = (Get-Date).ToString("o") } |
                        ConvertTo-Json | Set-Content -Path $SeedInfoPath
                }
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

    # A plain Ctrl+C's default behavior (breaking PowerShell's pipeline) is
    # unreliable for actually reaching the `finally` block below - which
    # terminal host has focus decides whether the interrupt tears the whole
    # process down before PowerShell gets a chance to unwind try/finally,
    # silently skipping Backup-LocalStackAppData and losing whatever
    # accounts/pies/etc. were created this session. Treating Ctrl+C as
    # plain input and polling for it here instead guarantees this loop
    # exits normally into `finally` regardless of host quirks. Falls back
    # to the old plain Start-Sleep loop if console manipulation isn't
    # available at all (e.g. no real console attached).
    try {
        $previousTreatControlCAsInput = [Console]::TreatControlCAsInput
        [Console]::TreatControlCAsInput = $true
        try {
            while ($true) {
                if ([Console]::KeyAvailable) {
                    $key = [Console]::ReadKey($true)
                    if ($key.Key -eq "C" -and ($key.Modifiers -band [ConsoleModifiers]::Control)) {
                        break
                    }
                }
                Start-Sleep -Milliseconds 200
            }
        } finally {
            [Console]::TreatControlCAsInput = $previousTreatControlCAsInput
        }
    } catch {
        while ($true) {
            Start-Sleep -Seconds 1
        }
    }
} finally {
    Stop-SpawnedProcess -Process $frontendProcess -Label "frontend"
    Stop-SpawnedProcess -Process $backendProcess -Label "backend"
    if ($StartLocalStack) {
        Backup-LocalStackAppData
        Write-Host "Stopping LocalStack ($ContainerName)..."
        Stop-LocalStackContainer
        Write-Host "Stopped."
    }
}
