import json
import logging
from typing import Callable, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from services.get_construct_info import get_construct_info

# from app.services.action_tier import action_tier_data
# from app.services.classify import classify_data
# from app.services.get_construct_info import get_construct_info
# from app.services.get_labels import get_labels_data
# from app.services.summarize import summarize_data


router = APIRouter()
logger = logging.getLogger(__name__)


class ExampleRequest(BaseModel):

    data: str
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data": "大樓工程中的假設工程，需要做的子工程有哪些？",
                }
            ]
        }
    }


# Only autocomplete api needs stream_reponse
async def stream_response(request_data: str, func: Callable[[str], dict]):
    logger.info("Received request with data: %s", request_data)
    try:
        # Call the func and stream chunks
        async for chunk in func(request_data):
            yield f"data: {chunk}\n\n"

    except Exception as e:
        logger.error("Error during processing: %s", str(e))
        yield json.dumps({"error": str(e)}) + "\n"


# Define a function to handle the common logic
async def handle_request(req: ExampleRequest, func: Callable[[str], dict]):
    logger.info("Received request with data: %s", req.data)
    try:
        if not req.data:
            logger.warning("Data cannot be empty")
            raise HTTPException(status_code=400, detail="Data cannot be empty")

        result = func(req.data)
        return {"results": result, "original": req.data}
    except ValidationError as e:
        logger.error("Error during processing: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    except Exception as e:
        logger.error("Error during processing: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/get_construct_info/")
async def get_construct(req: ExampleRequest):
    return await handle_request(req, get_construct_info)
