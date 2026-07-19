from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.workflow_context import init_workflow_context, get_triggered_run_ids

class WorkflowHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Initialize the context (ensure each request has its own independent list)
        init_workflow_context()
        
        # 2. Process the request
        response = await call_next(request)
        
        # 3. Check the context and inject the header
        run_ids = get_triggered_run_ids()
        if run_ids:
            # If the header already exists (rare), append
            existing = response.headers.get("X-Workflows-Started")
            if existing:
                new_ids = f"{existing},{','.join(map(str, run_ids))}"
                response.headers["X-Workflows-Started"] = new_ids
            else:
                response.headers["X-Workflows-Started"] = ",".join(map(str, run_ids))
                
        return response