# Deploying the STROT Space

This folder is a self-contained Hugging Face **Docker Space**. Pushing it to a
Space repo builds the image (bakes in the 144M model, pre-compiles the demo
artifacts) and launches the Gradio app.

## One-time setup

1. Create a new Space: https://huggingface.co/new-space
   - **SDK: Docker** (blank template), CPU basic (free) is enough.
2. Add your Anthropic key as a **build secret** (not a variable):
   Space → Settings → *Secrets* → New secret
   - Name: `ANTHROPIC_API_KEY`
   - Value: your key
   The key is used **only at build time** to pre-compile the demo artifacts. It
   is never read at runtime and never exposed to visitors. Without it the build
   still succeeds, but only the "Compile your own" tab works.

## Push

```bash
# from the repo root
cd space
git init -b main
git remote add space https://huggingface.co/spaces/<your-user>/<space-name>
git add .
git commit -m "STROT live demo"
git push space main
```

(Or drag these files into the Space's web editor.)

The first build takes a few minutes (CPU torch + model download + compiling the
three demo tasks, ~6–20¢ of tokens once). After that the Space serves decisions
key-free.

## Files

- `app.py` — Gradio app (Try-it + Compile-your-own tabs)
- `demo_tasks.py` — the three demo decision tasks
- `precompile.py` — build-time compilation into `STROT_STATE`
- `Dockerfile` — CPU torch, bakes Julia-1, pre-compiles, launches on port 7860

## Updating

Bump the pinned `strot-ai==` version in the `Dockerfile` when you want the Space
to track a new release, then push. The cache key includes the package version,
so the demo artifacts are recompiled on that build (hence the build secret stays
useful).
