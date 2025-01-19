from typing import Optional, Type
from langchain_core.tools.structured import StructuredTool
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.messages.chat import ChatMessage
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
from helpers.llm_helpers import llm, ask_question_response, create_standup_update, make_edits_to_update, friendly_conversation_response
from helpers.mongo_db_helpers import insert_item, update_exists, get_standup_updates_by_user_id

# Define the tools
create_standup_update_tool = StructuredTool.from_function(func=create_standup_update)
ask_question_tool = StructuredTool.from_function(func=ask_question_response)
make_edits_to_update_tool = StructuredTool.from_function(func=make_edits_to_update)
friendly_conversation_tool = StructuredTool.from_function(func=friendly_conversation_response)
check_if_update_exists_tool = StructuredTool.from_function(func=update_exists)
get_standup_update_by_user_id_tool = StructuredTool.from_function(func=get_standup_updates_by_user_id)

tool_map = {
    "create_standup_update": create_standup_update_tool,
    "ask_question_response": ask_question_tool,
    "ask_question": ask_question_tool,
    "make_edits_to_update": make_edits_to_update_tool,
    "friendly_conversation": friendly_conversation_tool,
    "friendly_conversation_response": friendly_conversation_tool
}

tools = [
    create_standup_update_tool,
    ask_question_tool,
    make_edits_to_update_tool,
    friendly_conversation_tool
]

agent = llm.bind_tools(tools)

def execute_agent_with_user_context(message: str, user_id: str, channel_id: str):
    has_update = update_exists(user_id) and get_standup_update_by_user_id_tool(user_id)["updates"] # need to check if the update is not empty in case we need to insert an empty update for the day
    print("has_update: ", has_update)
    tool_prompt = """
    You are a project manager that helps developers with their standup updates. You are given a set of tools to use to help you reply to the user's standup update.

    You are also given the following context:
    channel_id: {channel_id}
    user_id: {user_id}
    Does the human have an existing update: {update_exists}

    The user's message is: {message}

    Use only one tool to respond to the user and provide that tool the necessary context to respond to the user from above without changing any of the parameters.
    Make sure to follow the tool's instructions carefully.
    
    """.format(channel_id=channel_id, user_id=user_id, message=message, update_exists="Yes" if has_update else "No")
    m = """
    Channel id is: {channel_id}
    User id is: {user_id}
    Update exists: {update_exists}

    User message is: {message}
    # """.format(channel_id=channel_id, user_id=user_id, message=message, update_exists="Yes, an update exists" if has_update else "No update exists")
    tool_response = agent.invoke(tool_prompt)

    def execute_tool_call(tool_response):
        messages = []
        tool_name = None
        for tool_call in tool_response.tool_calls:
            print("Tool call: ", tool_call)
            tool_name = tool_call["name"].lower()
            selected_tool = tool_map[tool_name]
            tool_output = selected_tool.invoke(tool_call["args"])
            messages.append(tool_output)
        return messages, tool_name

    # TODO: need a way to ensure only one tool is returned and only use that tool
    agent_response, used_tool = execute_tool_call(tool_response)
    if used_tool in ["create_standup_update", "make_edits_to_update"]:
        # insert standup update to standup collection
        insert_item(user_id, agent_response)
    if used_tool == "friendly_conversation" and not has_update:
        # add empty update to the standup collection in case the conversation ends here and no update has been created
        insert_item(user_id, {"updates": [], "preferred_style": "Paragraph"})
    return agent_response, used_tool