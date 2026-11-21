#!/bin/bash
# Default "maker" for a new plugin: the GitHub account's name (or login) through gh,
# else the system user's full name (GECOS), else the login name.
# Show it to the user for confirmation: it goes into the plugin's metadata.

name=""
if command -v gh >/dev/null 2>&1; then
	name="$(timeout 10 gh api user --jq '.name // .login' 2>/dev/null)"
fi
if [ -z "$name" ]; then
	name="$(getent passwd "$USER" 2>/dev/null | cut -d: -f5 | cut -d, -f1)"
fi
if [ -z "$name" ]; then
	name="$USER"
fi
echo "$name"
