from helpers.mongo_db_helpers import update_exists, get_standup_updates_by_user_id, get_messages_from_db
from helpers.llm_helpers import llm, convert_conversation_history_to_langchain_messages
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.messages.system import SystemMessage
import json

def reply(channel_id, user_id, message) -> str:
    # Get conversation history and convert to langchain messages
    # conversation_history = fetch_conversation_history(channel_id, max_number_of_messages_to_fetch=6)
    conversation_history = get_messages_from_db(user_id, channel_id, max_number_of_messages_to_fetch=4)
    langchain_messages = convert_conversation_history_to_langchain_messages(conversation_history)
    
    # Check if update exists and get appropriate prompt
    has_update = update_exists(user_id)
    system_prompt = ""
    
    if has_update:
        update_data = get_standup_updates_by_user_id(user_id)

        print("update data from reply agent is: ", update_data)
        
        system_prompt = f"""
        You are a project manager that responds to standup updates from developers.
        Your task is to craft a beautiful response to the user's message.
        
        The developer has provided their update in the following format:
        {update_data['updates']['updates']}
        
        Please format this update into a well-structured Slack message using markdown.
        Follow the developer's preferred style: {update_data['updates']['preferred_style']}.
        
        For tasks that are BLOCKED, make sure to highlight the blockers clearly.
        Use appropriate markdown formatting to make the message easy to read.

        Only reply with the relevant information. Do not include any other information.
        """
    else:
        system_prompt = """
        You are a project manager that responds to standup updates from developers.
        Your task is to craft a beautiful response to the user's message. 
        No standup update has been provided for this conversation.
        
        Please engage with the developer based on their message and the conversation history.
        Use appropriate markdown formatting in your response.
        """
    
    # Combine system prompt with chat history and current message
    messages = [
        SystemMessage(content=system_prompt),
        *langchain_messages,
        HumanMessage(content=message)
    ]
    
    # Get response from LLM
    response = llm.invoke(messages)
    
    return response.content
