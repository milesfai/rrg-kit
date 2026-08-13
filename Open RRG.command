#!/bin/bash
# Double-click in Finder to open the dashboards as plain files (no Update button).
cd "$(dirname "$0")" || exit 1
for d in output/*/dashboard.html; do [ -e "$d" ] && open "$d"; done
