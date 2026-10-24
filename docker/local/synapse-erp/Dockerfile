FROM matrixdotorg/synapse:latest
RUN pip install --no-cache-dir pymssql
COPY erp_auth.py /modules/erp_auth.py
ENV PYTHONPATH=/modules
