# Honeypot Standalone Development Recipes
set shell := ["cmd.exe", "/c"]
import? "extension.just"

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
test type="":
    #!powershell
    if ("{{type}}" -eq "all") { poetry run pytest tests }
    elseif ("{{type}}" -ne "") { poetry run pytest tests -m "{{type}}" }
    else { poetry run pytest tests -m "not integration" }
alias t := test
