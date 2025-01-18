from typing import Optional, Type
from langchain_core.tools.structured import StructuredTool
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.messages.chat import ChatMessage
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
from helpers.llm_helpers import llm, insufficient_information_response, create_standup_update, make_edits_to_update
from helpers.mongo_db_helpers import insert_item, update_exists, get_standup_updates_by_user_id

# Define the tools
create_standup_update_tool = StructuredTool.from_function(func=create_standup_update)
insufficient_information_tool = StructuredTool.from_function(func=insufficient_information_response)
make_edits_to_update_tool = StructuredTool.from_function(func=make_edits_to_update)
check_if_update_exists_tool = StructuredTool.from_function(func=update_exists)
get_standup_update_by_user_id_tool = StructuredTool.from_function(func=get_standup_updates_by_user_id)

tool_map = {
    "create_standup_update": create_standup_update_tool,
    "insufficient_information": insufficient_information_tool,
    "make_edits_to_update": make_edits_to_update_tool
}

# List of tools
tools = [
    create_standup_update_tool,
    insufficient_information_tool,
    make_edits_to_update_tool
]

agent = llm.bind_tools(tools)

def execute_agent_with_user_context(message: str, user_id: str):
    has_update = update_exists(user_id)
    m = """
    User id is: {user_id}
    Update exists: {update_exists}

    User message is: {message}
    # """.format(user_id=user_id, message=message, update_exists="Yes, an update exists" if has_update else "No update exists")
    # TODO: need a way to ensure only one tool is returned
    tool_response = agent.invoke(m)

    def execute_tool_call(tool_response):
        messages = []
        for tool_call in tool_response.tool_calls:
            print("Tool call: ", tool_call)
            selected_tool = tool_map[tool_call["name"].lower()]
            tool_output = selected_tool.invoke(tool_call["args"])
            messages.append(tool_output)
        return messages

    agent_response = execute_tool_call(tool_response)
    if tool_response.tool_calls[0]["name"] in ["create_standup_update", "make_edits_to_update"]:
        insert_item(user_id, agent_response)
    return agent_response