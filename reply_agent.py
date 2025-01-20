from helpers.mongo_db_helpers import update_exists, get_standup_updates_by_user_id, get_messages_from_db
from helpers.llm_helpers import llm, convert_conversation_history_to_langchain_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages.system import SystemMessage
import json

def reply(tool_agent_response, channel_id, user_id, message, last_used_tool) -> str:
    # Get conversation history and convert to langchain messages
    # conversation_history = fetch_conversation_history(channel_id, max_number_of_messages_to_fetch=6)
    conversation_history = get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=8)
    langchain_messages = convert_conversation_history_to_langchain_messages(conversation_history)
    
    has_update = update_exists(user_id)
    update_data = get_standup_updates_by_user_id(user_id)[0] if has_update else None
    system_prompt = ""

    # TODO: check if we want to use this if statement for the ask question and friendly conversation tools. Doing this will get me closer to my goal
    # TODO: Do we want to use the agent response within the system prompt to make the agent response more relevant?
    # if last_used_tool not in ["create_standup_update", "make_edits_to_update"] and tool_agent_response and isinstance(tool_agent_response, list) and isinstance(tool_agent_response[0], str):
    #     print("executing tool agent response reply and tool agent response is: ", tool_agent_response)
    #     return tool_agent_response[0]
    
    # if we have an update and the last tool used was create or edit
    if update_data and last_used_tool in ["create_standup_update", "make_edits_to_update"]:
        print("update data from reply agent is: ", update_data)
        
        system_prompt = f"""
        You are a project manager that responds to standup updates from developers.
        Your task is to craft a beautiful response to the user's message.
        
        The developer has provided their update in the following format:
        {update_data['updates']['updates'] if 'updates' in update_data and update_data['updates']['updates'] else "No updates provided"}
        
        Please format this update into a well-structured Slack message.
        Write your response such that it follows the developer's preferred writing style: {update_data['updates']['preferred_style'] if 'preferred_style' in update_data['updates'] else "Paragraph"}.
        
        For tasks that are BLOCKED, make sure to highlight the blockers clearly.
        Make sure to differentiate between yesterday and today updates if needed.
        Use appropriate formatting for a clean slack message to make the message easy to read and include emojis for each task's status.

        Reply with a brief and courteous message to the user followed by the formatted update.
        """
    else:
        # this is wrong. It's possible to have an update and still up in this block
        system_prompt = """
        You are a project manager that responds to standup updates from developers.
        Your task is to craft a beautiful response to the user's message. 
        
        Please engage with the developer based on their message and the conversation history, and ask questions to get more information for a sufficient standup update if needed.
        For clarity, it may be best to let the user know the status of the update that you have for them.
        Use appropriate formatting for a slack message in your response and include emojis where appropriate.
        """
    # system_prompt = """
    #     You are a project manager that responds to standup updates from developers.
    #     Your task is to craft a beautiful response to the user's message. 
        
    #     Please engage with the developer based on their message and the conversation history, and ask questions to get more information for a sufficient standup update if needed.
    #     For clarity, it may be best to let the user know the status of the update that you have for them.
    #     Use appropriate formatting for a slack message in your response and include emojis where appropriate.
    #     """
    # Combine system prompt with chat history and current message
    messages = [
        SystemMessage(content=system_prompt),
        *langchain_messages,
        HumanMessage(content=message)
    ]
    
    # Get response from LLM
    response = llm.invoke(messages)
    
    return response.content
