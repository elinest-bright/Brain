# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import numpy as np

from Brain.src.service.train_service import TrainService
from langchain.docstore.document import Document

from Brain.src.common.brain_exception import BrainException
from Brain.src.common.utils import (
    COMMAND_SMS_INDEXES,
    COMMAND_BROWSER_OPEN,
    PINECONE_INDEX_NAME,
    DEFAULT_GPT_MODEL,
)
from Brain.src.model.req_model import ReqModel
from Brain.src.model.requests.request_model import BasicReq
from Brain.src.rising_plugin.image_embedding import (
    query_image_text,
)
from Brain.src.rising_plugin.csv_embed import get_embed

from nemoguardrails.actions import action

from Brain.src.rising_plugin.llm.falcon_llm import FalconLLM
from Brain.src.rising_plugin.llm.gpt_llm import GptLLM
from Brain.src.rising_plugin.llm.llms import (
    get_llm_chain,
    GPT_3_5_TURBO,
    GPT_4_32K,
    GPT_4,
    FALCON_7B,
    GPT_LLM_MODELS,
)

from Brain.src.rising_plugin.pinecone_engine import (
    get_pinecone_index_namespace,
    init_pinecone,
)

"""
query is json string with below format
{
    "query": string,
    "model": string,
    "uuid": string,
    "image_search": bool,
    "setting": {
        "host_name": string,
        "openai_key": string, 
        "pinecone_key": string, 
        "pinecone_env": string,
        "firebase_key": string,
        "firebase_env": string 
        "settings": {
                "temperature": float
            }, 
        "token": string, 
        "uuid": string, 
    }
}
"""


@action()
async def general_question(query):
    """init falcon model"""
    falcon_llm = FalconLLM()
    docs = []

    """step 0-->: parsing parms from the json query"""
    try:
        json_query = json.loads(query)
    except Exception as ex:
        raise BrainException(BrainException.JSON_PARSING_ISSUE_MSG)
    query = json_query["query"]
    image_search = json_query["image_search"]
    page_content = json_query["page_content"]
    document_id = json_query["document_id"]
    setting = ReqModel(json_query["setting"])
    is_browser = json_query["is_browser"]

    docs.append(Document(page_content=page_content, metadata=""))
    """ 1. calling gpt model to categorize for all message"""
    chain_data = get_llm_chain(model=DEFAULT_GPT_MODEL, setting=setting).run(
        input_documents=docs, question=query
    )
    try:
        result = json.loads(chain_data)
        # check image query with only its text
        if result["program"] == "image":
            if image_search:
                result["content"] = {
                    "image_name": query_image_text(result["content"], "", setting)
                }
        """ 2. check program is message to handle it with falcon llm """
        if result["program"] == "message":
            if is_browser:
                result["program"] = "ask_website"
            else:
                # """FALCON_7B:"""
                result["content"] = falcon_llm.query(question=query)
        return json.dumps(result)
    except ValueError as e:
        # Check sms and browser query
        if document_id in COMMAND_SMS_INDEXES:
            return json.dumps({"program": "sms", "content": chain_data})
        elif document_id in COMMAND_BROWSER_OPEN:
            return json.dumps({"program": "browser", "content": "https://google.com"})

        if is_browser:
            return json.dumps({"program": "ask_website", "content": ""})
        return json.dumps(
            {"program": "message", "content": falcon_llm.query(question=query)}
        )
