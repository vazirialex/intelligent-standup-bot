from langchain_core.tools.structured import StructuredTool
from helpers.llm_helpers import llm, ask_question_response, create_standup_update, make_edits_to_update, friendly_conversation_response, convert_conversation_history_to_langchain_messages
from helpers.mongo_db_helpers import insert_item, update_exists, get_standup_updates_by_user_id, get_messages_from_db
from langchain_core.messages import SystemMessage, HumanMessage

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
    has_update = update_exists(user_id) and get_standup_updates_by_user_id(user_id)[0]["updates"] # need to check if the update is not empty in case we need to insert an empty update for the day
    print("has_update: ", has_update)
    # give the agent conversation history
    # TODO: do we need to conditionally change prompt based on whether or not we have access to github activity?
    tool_prompt = """
    You are a project manager that helps developers with their standup updates. You are given a set of tools to use to help you reply to the user's standup update.

    You are also given the following context:
    channel_id: {channel_id}
    user_id: {user_id}
    Does the human have an existing update: {update_exists}

    You will also be given a conversation history with the user.

    You must use the tools provided to you to take the most appropriate actions to help the user with their standup update. You can use more than one tool if needed.
    In situations where you need to use more than one tool, you should prioritize using the create_standup_update and make_edits_to_update tools first before the ask question and friendly_conversation tools.

    Here are some examples of when you may need to use more than one tool:
    - the user likes the standup update provided by the scheduled message, no update exists for this user yet, but the user has not replied with any updates for the current day. In this case, it would make sense to use the create_standup_update tool and then use the ask_question tool to respond to the user.
    - the user likes the standup update provided by the scheduled message, no update exists for this user yet, and the user has provided an update for the current day. In this case, it would make sense to use the create_standup_update tool and then use the friendly_conversation tool to respond to the user.
    
    However, in a case where the user does not like the standup update provided by you, you can use the ask_question tool to respond to the user on what they would like to change or use the create or edit update tools to make changes depending on if an update already exists for the given day.

    You must use your best judgement to determine which tool to use and if more than one tool is needed.
    Make sure to provide that tool the necessary context to respond to the user from above without changing any of the parameters like the channel_id, user_id, update_exists, and message from the user.
    Also make sure to follow the tool's instructions carefully.
    
    """.format(channel_id=channel_id, user_id=user_id, update_exists="Yes" if has_update else "No")

    test_prompt = """
    You are a project manager that helps developers with their standup updates. You are given a set of tools to use to help you reply to the user's standup update.

    You are also given the following context:
    channel_id: {channel_id}
    user_id: {user_id}
    Does the human have an existing update: {update_exists}

    Use only one tool to respond to the user and provide that tool the necessary context to respond to the user from above without changing any of the parameters.
    You must analyze the conversation history carefully to determine if you have enough information to create or edit an update. Sufficient information is defined as having a status for each task.
    It is likely that tasks and their associated statuses are in the conversation history, so use the conversation history to infer statuses for each task and the items that are in the update.
    You MUST use the conversation history to infer statuses for each task and the items that are in the update.
    Keep the conversation relevant to the user's standup update and only use friendly conversation if the user has provided a standup update.
    """.format(channel_id=channel_id, user_id=user_id, message=message, update_exists="Yes" if has_update else "No")

    test_prompt_2 = """
    You are a project manager that helps developers with their standup updates. You are given a set of tools to use to help you reply to the user's standup update.

    You are also given the following context:
    channel_id: {channel_id}
    user_id: {user_id}
    Does the human have an existing update: {update_exists}

    Use only one tool to respond to the user and provide that tool the necessary context to respond to the user from above without changing any of the parameters.
    Make sure to follow the tool's instructions carefully and only create or edit an update if there is sufficient information from the user and conversation history to do so.
    You should always be asking yourself if you have enough information to create or edit an update. 
    If not, asking the user for more information about statuses and blockers should be your first priority using the ask_question tool.
    Remember to not change any of the parameters like the channel_id, user_id, update_exists, and message from the user.
    """.format(channel_id=channel_id, user_id=user_id, message=message, update_exists="Yes" if has_update else "No")

    conversation_history = get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=8)
    langchain_messages = convert_conversation_history_to_langchain_messages(conversation_history)

    chat_template = [
        *langchain_messages,
        SystemMessage(content=tool_prompt),
        HumanMessage(content=message),
    ]
   
    tool_response = agent.invoke(chat_template)

    print(f"all tools used for the following message: {message} ", [tool_call["name"] for tool_call in tool_response.tool_calls])

    def execute_tool_calls(tool_response):
        messages = []
        tool_name = None
        for tool_call in tool_response.tool_calls:
            tool_name = tool_call["name"].lower()
            selected_tool = tool_map[tool_name]
            tool_output = selected_tool.invoke(tool_call["args"])
            messages.append(tool_output)
            if tool_name == "create_standup_update" or tool_name == "make_edits_to_update":
                try:
                    insert_item(user_id, tool_output)
                except Exception as e:
                    print("Error inserting item: ", e)
        return messages, tool_name

    agent_response, last_used_tool = execute_tool_calls(tool_response)
    # if last_used_tool == "friendly_conversation" and not has_update:
    #     print("friendly conversation and no update exists")
        # attempt to create an update if no update exists yet and there's friendly conversation because 
        # try:
        #     create_standup_update(user_id, channel_id)
        # except Exception as e:
        #     print("Error inserting empty update: ", e)
    return agent_response, last_used_tool