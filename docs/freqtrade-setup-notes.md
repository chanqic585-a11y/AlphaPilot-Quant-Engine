# Freqtrade Setup Notes

V13.2 uses the official stable Freqtrade Docker image as a local research foundation.

Docker Compose service:

- image: `freqtradeorg/freqtrade:stable`
- mounts `./user_data` into `/freqtrade/user_data`
- default command is `--help`
- no public REST port is exposed
- no live trading command is configured

Config templates:

- `user_data/config/config.backtest.json`
- `user_data/config/config.dryrun.template.json`

Both configs:

- use `okx`
- use `USDT`
- use `dry_run: true`
- use `futures`
- use `isolated`
- contain placeholders only
- should never contain real API credentials

The helper scripts print commands first. Add `-Run` only when intentionally executing a local command.
