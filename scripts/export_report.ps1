$python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
& $python -m alphapilot.reports.export_backtest_report
