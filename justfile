# Honeypot Standalone Development Recipes
set shell := ["cmd.exe", "/c"]
set dotenv-load
set export

import? "extension.just"

# Provision local dev database via powercord devkit.just.
# Set POWERCORD_PATH to override the default sibling directory layout.
[private]
_ensure-db:
    #!powershell
    $pcPath = if ($env:POWERCORD_PATH) { $env:POWERCORD_PATH } else { "../../powercord" }
    $devkit = Join-Path $pcPath "devkit.just"
    if (Test-Path $devkit) {
        just --justfile $devkit _ensure-db
    } else {
        Write-Host "[devkit] powercord/devkit.just not found - skipping DB provisioning" -ForegroundColor Yellow
    }

# Default: List available just commands
default:
    @just --list

# ---------------------------------------------------------------------------- #
#                                 QA COMMANDS                                  #
# ---------------------------------------------------------------------------- #

# Quality Assurance. Usage: just qa [--fix]
[group: "qa"]
[arg("fix", long, value="true")]
qa fix="false": (lint fix) (format fix) test

# Linting. Usage: just lint [--fix] (auto-fix issues)
[group: "qa"]
[arg("fix", long, value="true")]
lint fix="false":
    poetry run ruff check . {{ if fix == "true" { "--fix" } else { "" } }}
alias lc := lint

# Formatting. Usage: just format [--fix] (apply formatting, otherwise check-only)
[group: "qa"]
[arg("fix", long, value="true")]
format fix="false":
    poetry run ruff format . {{ if fix == "false" { "--check" } else { "" } }}

# Type Checking
[group: "qa"]
check:
    poetry run mypy .
alias c := check

# Run tests. Usage: just test [--type unit|integration|all]
[group: "qa"]
[arg("type", long)]
test type="": _ensure-db
    #!powershell
    if ("{{type}}" -eq "all") { poetry run pytest tests }
    elseif ("{{type}}" -ne "") { poetry run pytest tests -m "{{type}}" }
    else { poetry run pytest tests -m "not integration" }
alias t := test
