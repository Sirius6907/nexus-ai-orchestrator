"""
Chat WebSocket Route — Production-grade streaming pipeline.

Message lifecycle:
  1. Client sends message (with optional session_id)
  2. If no session_id → create new session
  3. Persist user message in DB
  4. Run agent orchestrator
  5. Persist agent response in DB
  6. Stream result back with session_id for frontend sync
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging

from api.agents.orchestrator import AgentOrchestrator
from api.db.session import AsyncSessionLocal
from api.services import chat_service

logger = logging.getLogger(__name__)
router = APIRouter()

orchestrator = AgentOrchestrator()


@router.websocket("/ws")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection opened")

    try:
        while True:
            raw_data = await websocket.receive_text()
            logger.info(f"Received WS message: {raw_data[:200]}")

            # ── Parse the incoming payload ──
            try:
                data = json.loads(raw_data)
                prompt = data.get("message", "")
                session_id = data.get("session_id", None)
                planner_model = data.get("planner_model", "gemma3:1b")
                coder_model = data.get("coder_model", "gemma3:1b")
                image_base64 = data.get("image_base64", None)
            except json.JSONDecodeError:
                prompt = raw_data
                session_id = None
                planner_model = "gemma3:1b"
                coder_model = "gemma3:1b"
                image_base64 = None

            if not prompt.strip():
                await websocket.send_text(json.dumps(
                    {"type": "error", "message": "Empty message"}
                ))
                continue

            # ── Open a DB session for this exchange ──
            async with AsyncSessionLocal() as db:
                # ── Step 1: Create or fetch session ──
                if not session_id:
                    # Auto-title from first few words
                    auto_title = prompt[:50].strip() + ("..." if len(prompt) > 50 else "")
                    session = await chat_service.create_session(
                        db,
                        title=auto_title,
                        model_config={
                            "planner_model": planner_model,
                            "coder_model": coder_model,
                        },
                    )
                    session_id = session.id
                    logger.info(f"Created new session: {session_id}")

                    # Notify client of the new session
                    await websocket.send_text(json.dumps({
                        "type": "session_created",
                        "session_id": session_id,
                        "title": auto_title,
                    }))

                # ── Step 2: Persist user message ──
                await chat_service.add_message(
                    db,
                    session_id=session_id,
                    role="user",
                    content=prompt,
                )

                # ── Step 3: Send status update ──
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "session_id": session_id,
                    "message": f"Planner ({planner_model}) analyzing...",
                }))

                # ── Step 4: Run the agent orchestrator ──
                try:
                    result = await orchestrator.run_task(
                        prompt=prompt,
                        planner_model=planner_model,
                        coder_model=coder_model,
                        image_base64=image_base64,
                    )

                    agent_content = result.get("plan", "No response generated")
                    agent_trace = result.get("agent_trace", None)
                    code_output = result.get("code", None)

                    # If coder also produced output, append it
                    if code_output:
                        agent_content += f"\n\n```\n{code_output}\n```"

                    # ── Step 5: Persist agent response ──
                    agent_msg = await chat_service.add_message(
                        db,
                        session_id=session_id,
                        role="agent",
                        content=agent_content,
                        model_used=planner_model,
                        agent_trace=agent_trace,
                        token_count=len(agent_content.split()),
                    )

                    # ── Step 6: Send final result ──
                    await websocket.send_text(json.dumps({
                        "type": "result",
                        "session_id": session_id,
                        "message_id": agent_msg.id,
                        "plan": agent_content,
                        "agent_trace": agent_trace,
                        "status": "success",
                    }))

                except Exception as e:
                    logger.error(f"Error processing task: {e}", exc_info=True)

                    # Persist the error as a system message
                    await chat_service.add_message(
                        db,
                        session_id=session_id,
                        role="system",
                        content=f"Error: {str(e)}",
                    )

                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "session_id": session_id,
                        "message": str(e),
                    }))

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket fatal error: {e}", exc_info=True)
