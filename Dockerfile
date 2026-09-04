# Headless SNID-SAGE CLI image (for batch/pipeline spectral classification, e.g. OSG).
# Templates are baked in so jobs run fully offline; the GUI (Qt) stack is stripped.
#
# Multi-stage: install into a venv in the builder, then carry only the venv and a
# single copy of the template bank into the runtime image (no source, no pip cache).

FROM python:3.11-slim-bookworm AS builder

# setuptools_scm can't see git history in the build context; pass the version in.
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_SNID_SAGE=${SETUPTOOLS_SCM_PRETEND_VERSION} \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv
WORKDIR /src
COPY . .

# Install the package, then drop the GUI-only stack — the CLI never imports it.
RUN pip install --upgrade pip \
    && pip install . \
    && pip uninstall -y PySide6 PySide6-Addons PySide6-Essentials shiboken6 pyqtgraph || true


FROM python:3.11-slim-bookworm

# libgomp1 for scipy/scikit-learn OpenMP; the rest ship manylinux wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    MPLBACKEND=Agg \
    SNID_SAGE_TEMPLATE_DIR="" \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /src/templates /opt/snid_sage/templates

# The meta stamp marks the baked bank as complete so a job never tries to
# re-download it (OSG execute nodes have no egress).
RUN rm -rf /opt/snid_sage/templates/Individual_templates \
    && python -c "import json; from snid_sage.shared import templates_manager as t; \
json.dump({'version': t.TEMPLATE_BANK_VERSION, 'files': list(t.TEMPLATES_FILES), 'archive_url': 'baked'}, \
open('/opt/snid_sage/templates/templates_meta.json', 'w'), indent=2, sort_keys=True)"

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

WORKDIR /work
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["sage", "--help"]
