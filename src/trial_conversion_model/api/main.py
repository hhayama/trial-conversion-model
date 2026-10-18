from fastapi import FastAPI

from trial_conversion_model.api.logging_config import setup_logging

# Configure logging once, here, before routes (which loads the model) is imported.
setup_logging()

from trial_conversion_model.api.routes import router

app = FastAPI(title="Beam trial conversion model")
app.include_router(router)
