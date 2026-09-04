#!/bin/sh
# Expose the baked (read-only) template bank through a writable dir, since
# SNID-SAGE requires SNID_SAGE_TEMPLATE_DIR to pass a W_OK check. Symlinks keep
# it cheap and work on a read-only Apptainer image (OSG) as well as `docker run`.
set -e

if [ -z "${SNID_SAGE_TEMPLATE_DIR}" ] && [ -d /opt/snid_sage/templates ]; then
    work="${TMPDIR:-/tmp}/snid_sage_templates"
    mkdir -p "$work"
    for f in /opt/snid_sage/templates/*; do
        ln -sfn "$f" "$work/$(basename "$f")"
    done
    export SNID_SAGE_TEMPLATE_DIR="$work"
fi

exec "$@"
