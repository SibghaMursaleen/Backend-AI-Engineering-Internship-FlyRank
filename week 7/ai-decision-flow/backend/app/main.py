from fastapi import FastAPI
import inngest
import inngest.fast_api
from app.core.clients import inngest_client

# Define a simple test workflow function
@inngest_client.create_function(
    fn_id="test_workflow",
    trigger=inngest.TriggerEvent(event="app/test.workflow"),
)
async def test_workflow(ctx: inngest.Context) -> str:
    ctx.logger.info("Test workflow triggered successfully!")
    return "Test workflow executed"

# Initialize FastAPI application
app = FastAPI(title="AI Decision Flow API", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "AI Decision Flow API is running"}

# Serve the Inngest endpoint at /api/inngest
inngest.fast_api.serve(app, inngest_client, [test_workflow])
