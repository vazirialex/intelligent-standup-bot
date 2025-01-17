from typing import Optional, Type
from langchain_core.tools.structured import StructuredTool
from pydantic import BaseModel, Field
from helpers.llm_helpers import llm, insufficient_information_response, create_standup_update, make_edits_to_update

# Define the tools
create_standup_update_tool = StructuredTool.from_function(func=create_standup_update)
insufficient_information_tool = StructuredTool.from_function(func=insufficient_information_response)
make_edits_to_update_tool = StructuredTool.from_function(func=make_edits_to_update)

# List of tools
tools = [
    create_standup_update_tool,
    insufficient_information_tool,
    make_edits_to_update_tool
]

agent = llm.bind_tools(tools)