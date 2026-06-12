FROM ghcr.io/frappe/erpnext:v15

USER root

# Copy the app repo into the bench apps directory.
# The repo root IS the Frappe app (contains basic_spine/ + pyproject.toml).
COPY --chown=frappe:frappe . /home/frappe/frappe-bench/apps/basic_spine

# Install Python dependencies into the bench virtualenv.
# rapidfuzz / openpyxl / pandas are declared in pyproject.toml but pip install -e
# only resolves them if the build backend supports it; install explicitly to be safe.
RUN /home/frappe/frappe-bench/env/bin/pip install --no-cache-dir \
        rapidfuzz openpyxl pandas \
    && /home/frappe/frappe-bench/env/bin/pip install --no-cache-dir \
        -e /home/frappe/frappe-bench/apps/basic_spine

USER frappe
