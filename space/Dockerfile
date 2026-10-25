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

RUN pip install --no-cache-dir "strot-ai[local,anthropic]==0.11.1"

# Bake the 144M local decision model into the image (CPU inference).
RUN python -c "import strot; strot.prefetch_nlu(local_dir='/opt/julia-1', install=True)"

# Pre-compiled demo artifacts, built offline and committed to the repo. Runtime
# serves these frozen pipelines directly, so the build needs no API key and the
# running Space makes zero LLM calls. (See precompile.py for how they're made.)
COPY state ./state

# gradio 5+ (gradio 4.x is incompatible with huggingface_hub >= 1.0).
RUN pip install --no-cache-dir "gradio>=5,<6"

COPY demo_tasks.py app.py ./

EXPOSE 7860
CMD ["python", "app.py"]
