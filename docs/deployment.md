# Day 12 deployment

## Completion requirements

Ruff, pytest and Docker CI must pass; merge the feature-branch PR only after green
checks. Deploy on Render or Hugging Face Spaces, then verify the actual public URL
and add it to README and the training tracker's Live URL cell for 2124UDSM2013.
A configuration file alone does not complete Day 12.

## Container architecture

The image includes a prebuilt public-guideline Chroma index and cached model.
The default command supervises FastAPI (internal 8000), Streamlit (internal 8501)
and unprivileged nginx (PORT, default 7860). The gateway handles WebSockets,
/health and /api/*; Swagger is /api/docs. If a service exits, the container stops
rather than staying half-running. Docker Compose retains separate API/UI commands.

```
docker build -t fasalbima-sathi:local .
docker run --rm -p 7860:7860 --env-file .env fasalbima-sathi:local
python deploy/smoke.py http://127.0.0.1:7860
```

## Hugging Face Docker Space

Create a public Docker Space. Root README metadata selects sdk: docker and port
7860; the image uses user ID 1000. Sync tracked project files, never .env, feedback
or local environments. Set LLM_PROVIDER=groq and GROQ_MODEL=openai/gpt-oss-20b as
variables. Put GROQ_API_KEY in Settings > Secrets, never in chat or Git. Await
Running status, then run deploy/smoke.py against the actual hf.space URL assigned
by the platform. Spot-check a real provider answer with citations afterwards.

## Render

render.yaml describes one Docker web service and public /health. Connect the
GitHub repo through a Blueprint and privately supply GROQ_API_KEY in Render.
Use the assigned onrender.com URL. Deployments wait for CI checks. The free plan
has limited memory and can sleep; use a Docker Space if the model cannot fit.
No paid service is required by this setup.

## Limits and evidence

Free-host filesystems are ephemeral: feedback can disappear on redeployment.
Conversation checkpoints and approval state reset with the API process. Use one
worker. The app does not submit claims or guarantee coverage. Never provide personal
identifiers. Provider quotas apply and failed calls remain visible.

CI retains pytest XML, container logs and smoke-results.json. The smoke test checks
a real RFC6455 WebSocket handshake as well as API/UI HTTP responses and Q6 refusal.
Repeat it on the actual public URL before putting that URL in the tracker.

References: https://huggingface.co/docs/hub/spaces-sdks-docker,
https://huggingface.co/docs/hub/spaces-config-reference,
https://render.com/docs/blueprint-spec.
