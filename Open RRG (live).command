#!/bin/bash
# Double-click to start the local server and open the dashboard with a
# working Update button. Close this Terminal window to stop the server.
cd "$(dirname "$0")" || exit 1
exec python3 serve.py
