from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel import Session
from app.db.session import get_session
from app.schemas.ai import ContinuationRequest, ContinuationResponse, GeneralAIRequest
from app.schemas.response import ApiResponse
from app.services import prompt_service, llm_config_service

from app.services.schema_service import compose_full_schema
from app.utils.stream_utils import wrap_sse_stream
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from typing import Type, Dict, Any, List
import json

from app.db.models import Card, CardType
from app.utils.schema_utils import filter_schema_for_ai

# Import the knowledge base
from app.services.knowledge_service import KnowledgeService
from app.schemas.entity import DYNAMIC_INFO_TYPES
from app.schemas import entity as entity_schemas
from app.core import emit_event
from app.services.ai.core import llm_service
from app.services.ai.core.model_builder import build_model_from_json_schema
from app.services.ai.generation.continuation_context_service import enrich_continuation_context_info
from app.services.ai.generation.continuation_budget_runtime import estimate_required_call_count
from app.services.ai.generation.instruction_validator import validate_instruction, apply_instruction
from app.services.ai.generation.instruction_generator import generate_instruction_stream
from app.services.ai.generation.prompt_builder import build_instruction_system_prompt
from app.schemas.instruction import InstructionGenerateRequest
from app.schemas.wizard import Tags as _Tags
from loguru import logger

router = APIRouter()

# Response model mapping (built-in)
from app.schemas.response_registry import RESPONSE_MODEL_MAP


@router.get("/schemas", response_model=Dict[str, Any], summary="Get the JSON Schema of all output models (built-in only)")
def get_all_schemas(session: Session = Depends(get_session)):
    """Return an aggregate of built-in pydantic model schemas, keyed by model name."""
    all_definitions: Dict[str, Any] = {}

    # 1) Built-in pydantic models
    for name, model_class in RESPONSE_MODEL_MAP.items():
        schema = model_class.model_json_schema(ref_template="#/$defs/{model}")
        if '$defs' in schema:
            all_definitions.update(schema['$defs'])
            del schema['$defs']
        all_definitions[name] = schema

    # Dynamically fix the properties of CharacterCard.dynamic_info
    try:
        cc = all_definitions.get('CharacterCard')
        if isinstance(cc, dict):
            props = (cc.get('properties') or {})
            if 'dynamic_info' in props:
                item_schema = {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "info": {"type": "string"},
                        "weight": {"type": "number"}
                    },
                    "required": ["id", "info", "weight"]
                }
                enum_values = DYNAMIC_INFO_TYPES
                props['dynamic_info'] = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        ev: {"type": "array", "items": item_schema} for ev in enum_values
                    },
                    "description": "Character dynamic info, grouped arrays by category (keys are Chinese enum values)"
                }
                cc['properties'] = props
                all_definitions['CharacterCard'] = cc
    except Exception:
        pass

    # 2) Inject entity dynamic-info related models (used by the frontend to resolve $ref: DynamicInfo, etc.)
    try:
        entity_models = [
            entity_schemas.DynamicInfoItem,
            entity_schemas.DynamicInfo,
            entity_schemas.UpdateDynamicInfo,
        ]
        for mdl in entity_models:
            sch = mdl.model_json_schema(ref_template="#/$defs/{model}")
            if '$defs' in sch:
                all_definitions.update(sch['$defs'])
                del sch['$defs']
            all_definitions[mdl.__name__] = sch
    except Exception:
        pass

    return all_definitions

@router.get("/content-models", response_model=List[str], summary="Get the names of all available output models")
def get_content_models(session: Session = Depends(get_session)):
    # Only return built-in model names
    return list(RESPONSE_MODEL_MAP.keys())


@router.get("/config-options", summary="Get AI generation config options")
async def get_ai_config_options(session: Session = Depends(get_session)):
    """Get the config options available during AI generation."""
    try:
        # Get all LLM configs
        llm_configs = llm_config_service.get_llm_configs(session)
        # Get all prompts
        prompts = prompt_service.get_prompts(session)
        # Response models are built-in only
        response_models = get_content_models(session)
        return ApiResponse(data={
            "llm_configs": [{"id": config.id, "display_name": config.display_name or config.model_name} for config in llm_configs],
            "prompts": [{"id": prompt.id, "name": prompt.name, "description": prompt.description, "built_in": getattr(prompt, 'built_in', False)} for prompt in prompts],
            "available_tasks": [],
            "response_models": response_models
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config options: {str(e)}")

@router.get("/prompts/render", summary="Render a prompt template with the knowledge base injected")
async def render_prompt_with_knowledge(name: str, session: Session = Depends(get_session)):
    p = prompt_service.get_prompt_by_name(session, name)
    if not p or not p.template:
        raise HTTPException(status_code=404, detail=f"Prompt not found: {name}")
    try:
        text = prompt_service.inject_knowledge(session, str(p.template))
        return ApiResponse(data={"text": text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render failed: {e}")

@router.post("/generate", summary="General AI generation endpoint")
async def generate_ai_content(
    request: GeneralAIRequest = Body(...),
    session: Session = Depends(get_session),
):
    """
    General AI content generation endpoint: the frontend must provide response_model_schema.
    """
    # Basic parameter validation: input/llm_config_id/prompt_name/response_model_schema are required
    if not request.input or not request.llm_config_id or not request.prompt_name:
        raise HTTPException(status_code=400, detail="Missing required generation parameters: input, llm_config_id or prompt_name")
    if request.response_model_schema is None:
        raise HTTPException(status_code=400, detail="Please provide response_model_schema")

    # Resolve the response model (dynamic schema only)
    try:
        # Full schema assembly: built-in defs + CardType defs
        composed = compose_full_schema(session, request.response_model_schema)
        # Filter fields based on x-ai-exclude
        schema_for_prompt = filter_schema_for_ai(composed) if request.exclude_ai_fields else composed
        # Dynamically build the Pydantic model
        resp_model = build_model_from_json_schema('DynamicResponseModel', schema_for_prompt or composed)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create model dynamically: {e}")

    # Get the prompt
    prompt = prompt_service.get_prompt_by_name(session, request.prompt_name)
    if not prompt:
        raise HTTPException(status_code=400, detail=f"Prompt not found: {request.prompt_name}")

    # Inject the knowledge base
    prompt_template = prompt_service.inject_knowledge(session, prompt.template or '')

    # System Prompt: carries the JSON Schema
    schema_json = json.dumps(schema_for_prompt if schema_for_prompt is not None else resp_model.model_json_schema(), indent=2, ensure_ascii=False)
    system_prompt = (
        f"{prompt_template}\n\n"
        f"```json\n{schema_json}\n```"
    )

    user_prompt = request.input['input_text']
    deps_str = request.deps or ""

    try:
        result = await llm_service.generate_structured(
            session=session,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            output_type=resp_model,
            llm_config_id=request.llm_config_id, 
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            timeout=request.timeout,
            deps=deps_str,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Trigger OnGenerateFinish (if a card can be located)
    card: Card | None = None
    try:
        card_id = None
        if isinstance(request.input, dict):
            card_id = request.input.get('card_id')
        if card_id:
            card = session.get(Card, int(card_id))
        project_id = None
        if isinstance(request.input, dict):
            project_id = request.input.get('project_id') or (card.project_id if card else None)
        emit_event("generate.finished", {
            "session": session,
            "card": card,
            "project_id": int(project_id) if project_id else (card.project_id if card else None)
        })
    except Exception:
        pass
    return ApiResponse(data=result)

@router.post("/generate/continuation", 
             response_model=ApiResponse[ContinuationResponse], 
             summary="Continue writing body text",
             responses={
                 200: {
                     "content": {
                         "application/json": {},
                         "text/event-stream": {}
                     },
                     "description": "Returns the continuation result or event stream on success"
                 }
             })
async def generate_continuation(
    request: ContinuationRequest,
    session: Session = Depends(get_session),
):
    try:
        # Force reading the template from prompt_name as the system prompt
        if not request.prompt_name:
            raise HTTPException(status_code=400, detail="Continuation requires prompt_name to be specified")
        p = prompt_service.get_prompt_by_name(session, request.prompt_name)
        if not p or not p.template:
            raise HTTPException(status_code=400, detail=f"Prompt not found: {request.prompt_name}")
        # Inject the knowledge base
        system_prompt = prompt_service.inject_knowledge(session, str(p.template))


        request.context_info = enrich_continuation_context_info(session, request)
        

        if request.stream:
            # Run a quota pre-check first to avoid errors surfacing mid-stream
            expected_calls = estimate_required_call_count(request)
            ok, reason = llm_config_service.can_consume(session, request.llm_config_id, 0, 0, expected_calls)
            if not ok:
                raise HTTPException(status_code=400, detail=f"LLM quota insufficient: {reason}")
            async def _stream_and_trigger():
                content_acc = []
                async for chunk in llm_service.generate_continuation_streaming(session, request, system_prompt):
                    content_acc.append(chunk)
                    yield chunk
                try:
                    # Trigger after continuation finishes
                    emit_event("generate.finished", {
                        "session": session,
                        "card": None,
                        "project_id": request.project_id
                    })
                except Exception:
                    pass
            return StreamingResponse(wrap_sse_stream(_stream_and_trigger()), media_type="text/event-stream")
        else:
            # Non-streaming mode: collect all content
            content_parts = []
            async for chunk in llm_service.generate_continuation_streaming(session, request, system_prompt):
                content_parts.append(chunk)
            result = "".join(content_parts)
            try:
                emit_event("generate.finished", {
                    "session": session,
                    "card": None,
                    "project_id": request.project_id
                })
            except Exception:
                pass
            return ApiResponse(data=ContinuationResponse(content=result))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/models/tags", response_model=_Tags, summary="Export the Tags model (for type generation)")
def export_tags_model():
    return _Tags()


# ==================== Instruction stream generation endpoint ====================


@router.post("/generate/stream", summary="Instruction streaming generation endpoint")
async def generate_with_instruction_stream(
    request: InstructionGenerateRequest,
    session: Session = Depends(get_session),
):
    """
    Instruction streaming generation endpoint.
    
    Returns the LLM-generated instruction stream in real time; the frontend
    executes each instruction and updates the UI. Supports auto-validation
    and repair, and the user can interact with the AI during generation.
    """
    async def event_generator():
        try:
            # 1. Assemble the full schema (inject $defs)
            full_schema = compose_full_schema(session, request.response_model_schema)
            
            # 2. Load the card task prompt (if a name is provided)
            card_prompt_content = None
            if request.prompt_template:
                from app.services import prompt_service
                from loguru import logger
                prompt = prompt_service.get_prompt_by_name(session, request.prompt_template)
                if prompt and prompt.template:
                    card_prompt_content = prompt_service.inject_knowledge(session, str(prompt.template))
                    logger.info(f"[CardGeneration] Loaded prompt template: {request.prompt_template}, length: {len(card_prompt_content)}")
                else:
                    logger.warning(f"[CardGeneration] Prompt template not found: {request.prompt_template}")
            
            # 3. Build the System Prompt (card task + instruction spec + Schema)
            system_prompt = build_instruction_system_prompt(
                session=session,
                schema=full_schema,
                card_prompt=card_prompt_content
            )
            
            # 4. Call the instruction stream generation service
            async for event in generate_instruction_stream(
                session=session,
                llm_config_id=request.llm_config_id,
                user_prompt=request.user_prompt,
                system_prompt=system_prompt,
                schema=full_schema,
                current_data=request.current_data,
                conversation_context=request.conversation_context,
                context_info=request.context_info,
                temperature=request.temperature or 0.7,
                max_tokens=request.max_tokens,
                timeout=request.timeout or 150
            ):
                # 5. Send an SSE event (format: data: {json}\n\n)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            logger.error(f"Instruction stream generation failed: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "text": f"Generation failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    ) 
