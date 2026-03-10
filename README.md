# Honeypot Extension

The `honeypot` extension provides automatic spammer-banning capabilities for Powercord by monitoring designated "honeypot" channels. If a user posts in all designated honeypot channels within a specific time limit, they are automatically banned from the server.

## Python Dependencies
- None (Standard Library)

## Database Schema Changes
- `HoneypotSettings`: Stores the guild-specific time limit (default 60 seconds).
- `HoneypotChannel`: Tracks which channels in a guild are designated as honeypots.
- `HoneypotBanReport`: Logs records of successful automatic bans for dashboard reporting.

## Features

### Bot Features (Cogs)
- **Commands**:
  - `/honeypot set_time_limit`: Configure the maximum window of time between a user's first post and their last post across all honeypots.
  - `/honeypot add_channel`: Add a channel to the honeypot list.
  - `/honeypot remove_channel`: Remove a channel from the honeypot list.
  - `/honeypot status`: View the active configuration and current honeypot channels.
- **Listeners**:
  - `on_message`: Tracks when users post in honeypot channels using an in-memory dictionary. Calculates time differences and issues bans if conditions are met.

### API Routes (Sprockets)
*Note: As of the recent framework security updates, these endpoints are strictly protected behind the `api_scope_required("honeypot")` middleware. They require a valid internal API Key or Discord token passed via an `Authorization: Bearer` header or `?token=` query parameter.*
- `POST /honeypot/config/{guild_id}/settings`: Updates the time limit setting for a specific guild.
- `POST /honeypot/config/{guild_id}/remove_channel`: Removes a channel from the honeypot tracking list.
- `POST /honeypot/config/{guild_id}/clear_channels`: Removes all active honeypot tracking channels for a guild.

### UI Elements (Widgets)
- `guild_admin_honeypot_config`: Displays forms in the Admin Dashboard to precisely set the time limit and manage active honeypot channels.
- `guild_admin_honeypot_reports`: Displays a table of the 10 most recent spammers banned by the extension.

## Lifecycle Hooks

### Delete Server Data
The honeypot extension registers a `delete_guild_data` lifecycle hook. When a server admin uses the **Delete Server Data** action (via the dashboard or `/powercord delete_server_data`), the following data is permanently removed for that guild:
- `HoneypotSettings` (time limit, log channel, shame mode)
- `HoneypotChannel` (designated honeypot channels)
- `HoneypotBanReport` (ban history records)

Additionally, Powercord's core `GuildExtensionSettings` and `WidgetSettings` rows for this extension are cleaned up.

### Graceful Reinstallations
This extension uses the `latest_migration_version` key in its `extension.json` manifest. Running `just ext-install` on an already installed Honeypot extension will gracefully overwrite the Python files and skip the lengthy Alembic database migration phases if the version has not incremented, significantly speeding up the developer deployment workflow.
