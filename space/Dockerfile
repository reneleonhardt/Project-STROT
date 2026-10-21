FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    STROT_NLU_CHECKPOINT=/opt/julia-1 \
    STROT_STATE=/app/state \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

WORKDIR /app

# CPU-only torch first, so the heavy CUDA wheels never get pulled in.
RUN pip install --no-cache-dir torch>=2.6 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir "strot-ai[local,anthropic]==0.11.1" "gradio>=4.44,<5"

# Bake the 144M local decision model into the image (CPU inference).
RUN python -c "import strot; strot.prefetch_nlu(local_dir='/opt/julia-1', install=True)"

COPY demo_tasks.py precompile.py app.py ./

# Pre-compile the demo artifacts once, at build time, using an Anthropic key
# supplied as a build secret. Runtime never sees the key and makes zero LLM
# calls. If the secret is absent the build still succeeds (BYO-key tab only).
RUN --mount=type=secret,id=ANTHROPIC_API_KEY \
    sh -c 'if [ -f /run/secrets/ANTHROPIC_API_KEY ]; then \
             ANTHROPIC_API_KEY="$(cat /run/secrets/ANTHROPIC_API_KEY)" python precompile.py; \
           else echo "No build secret ANTHROPIC_API_KEY; skipping pre-compile."; fi'

EXPOSE 7860
CMD ["python", "app.py"]
