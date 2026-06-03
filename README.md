# Honeypot Extension

The `honeypot` extension provides automatic spammer-banning capabilities for Powercord by monitoring designated "honeypot" channels. If a user posts in all designated honeypot channels within a specific time limit, they are automatically banned from the server. At least 2 honeypot channels must be configured for bans to trigger (this prevents accidental bans from a single channel).

## Python Dependencies
- None beyond Powercord core dependencies

## Database Schema Changes
- `HoneypotSettings`: Stores the guild-specific time limit (default 60 seconds), optional log channel ID for ban reports, and shame mode toggle (default off).
- `HoneypotChannel`: Tracks which channels in a guild are designated as honeypots.
- `HoneypotBanReport`: Logs records of successful automatic bans for dashboard reporting.

## Architecture

The honeypot extension follows the standard Powercord split-stack pattern:

| Component | Server | Purpose |
|-----------|--------|---------|
| `widget.py` | FastHTML (UI) | Renders dashboard configuration forms using HTMX |
| `routes.py` | FastHTML (UI) | Handles form submissions from widgets, performs DB operations, returns re-rendered HTML fragments |
| `sprocket.py` | FastAPI (API) | Form-handling API returning redirect responses for programmatic consumers |
| `cog.py` | Discord Bot | Slash commands and message listeners |

> **Note:** The `routes.py` and `sprocket.py` operate independently. Widget forms POST
> to `routes.py` (same-origin FastHTML routes) via HTMX, *not* to the sprocket. The
> sprocket remains available for programmatic API access by external tools.

## Features

### Bot Features (Cogs)
- **Commands**:
  - `/honeypot set_time_limit`: Set the time limit (in seconds) for a user to post in all honeypot channels to trigger a ban.
  - `/honeypot set_log_channel`: Set the channel where honeypot ban report embeds will be sent.
  - `/honeypot set_shame_mode`: Toggle whether to include humorous insults in the ban report embed footer.
  - `/honeypot add_channel`: Designate an existing public text channel as a honeypot.
  - `/honeypot remove_channel`: Remove a channel from honeypot designation.
  - `/honeypot create_channel`: Create a new public text channel and automatically designate it as a honeypot.
  - `/honeypot add_all_channels`: Add all public text channels in the server to the honeypot list (requires confirmation via button prompt).
  - `/honeypot clear_channels`: Clear all registered honeypot channels for the server.
  - `/honeypot status`: Show current honeypot configuration including time limit, shame mode, log channel, and active honeypot channels.
- **Listeners**:
  - `on_message`: Tracks when users post in honeypot channels using an in-memory dictionary. Calculates time differences and issues bans if all honeypot channels are posted in within the time limit. At least 2 honeypot channels must be configured for a ban to trigger.

### Dashboard UI Routes (`routes.py`)
These endpoints run on the **FastHTML** server and handle form submissions from
the dashboard widgets. They query the database directly and return re-rendered
HTML fragments for HTMX to swap in-place.

- `POST /honeypot/config/{guild_id}/settings`: Upserts the time limit, log channel, and shame mode settings.
- `POST /honeypot/config/{guild_id}/remove_channel`: Removes a single channel from the honeypot tracking list.
- `POST /honeypot/config/{guild_id}/clear_channels`: Removes all active honeypot tracking channels for a guild.

### API Routes (`sprocket.py`)
*These endpoints run on the **FastAPI** server as a form-handling API. They accept
`Form(...)` data and return `RedirectResponse` (HTTP 303), making them suitable for
browser-based form consumers rather than a typical JSON API. These routes are
currently unprotected (no authentication middleware is applied).*

- `POST /honeypot/config/{guild_id}/settings`: Updates settings (accepts `Form(...)` data, returns redirect).
- `POST /honeypot/config/{guild_id}/remove_channel`: Removes a channel (accepts `Form(...)` data, returns redirect).
- `POST /honeypot/config/{guild_id}/clear_channels`: Clears all channels (returns redirect).

### UI Elements (Widgets)
- `guild_admin_honeypot_config`: Displays forms in the Admin Dashboard to set the time limit, log channel, shame mode, and manage active honeypot channels. Uses **HTMX** (`hx_post`, `hx_target`, `hx_swap`) for in-place widget updates without full page reloads.
- `guild_admin_honeypot_reports`: Displays a table of the 10 most recent spammers banned by the extension.

## Lifecycle Hooks

### Delete Server Data
The honeypot extension registers a `delete_guild_data` lifecycle hook. When a server admin uses the **Delete Server Data** action (via the dashboard or `/powercord delete_server_data`), the following data is permanently removed for that guild:
- `HoneypotSettings` (time limit, log channel, shame mode)
- `HoneypotChannel` (designated honeypot channels)
- `HoneypotBanReport` (ban history records)

Additionally, Powercord's core framework automatically cleans up `GuildExtensionSettings` and `WidgetSettings` rows for any extension during the delete-server-data lifecycle.

### Graceful Reinstallations & Decoupled Migrations
This extension governs its own disconnected idempotent database schema via a standalone `alembic/versions` directory (completely isolated from the Powercord core database history).
It uses the `latest_migration_version` key in its `extension.just` manifest to instruct Powercord which decoupled schema branch to target during installation. Running `just ext-install` on an already installed Honeypot extension will gracefully overwrite the Python files and dynamically detect if the `latest_migration_version` hash has incremented. If it has not, the installer intelligently skips the Alembic database mapping phases, rapidly speeding up developer deployment workflows.

## Local Development and Testing

You can run this extension's test suite standalone natively via `just test`. 

> **Important**: This extension relies on the `powercord` core framework for testing utilities. Ensure the core repository is cloned natively as a sibling directory to this extension, or manually set the `POWERCORD_PATH` environment variable pointing to the core `powercord` repository.

