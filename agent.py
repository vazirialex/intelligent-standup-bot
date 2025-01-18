from typing import Optional, Type
from langchain_core.tools.structured import StructuredTool
from langchain_community.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from helpers.llm_helpers import llm, insufficient_information_response, create_standup_update, make_edits_to_update
from helpers.mongo_db_helpers import update_exists, get_standup_updates_by_user_id
from datetime import datetime

# Define the tools
create_standup_update_tool = StructuredTool.from_function(func=create_standup_update)
insufficient_information_tool = StructuredTool.from_function(func=insufficient_information_response)
make_edits_to_update_tool = StructuredTool.from_function(func=make_edits_to_update)
check_if_update_exists_tool = StructuredTool.from_function(func=update_exists)
get_standup_update_by_user_id_tool = StructuredTool.from_function(func=get_standup_updates_by_user_id)

# List of tools
tools = [
    create_standup_update_tool,
    insufficient_information_tool,
    make_edits_to_update_tool,
    check_if_update_exists_tool,
    get_standup_update_by_user_id_tool
]

system = """
You are a project manager that facilitates daily standup updates. Your job is to:
1. Create a new standup update if one does not already exist.
2. Edit an existing standup update if the user replies with updates or changes to the existing update.
3. Handle vague or unclear responses by asking clarifying questions and asking for more details, or responding to the query as you see fit.

Here are your tools to accomplish this job:

{tools}

You must use external data like the Slack user ID and MongoDB to check for the existence of a standup update:
- If editing an update, always ensure you query MongoDB to retrieve the current update using the provided Slack user ID.

Here is the workflow:
1. If no update is provided, you cannot proceed with making edits. Either create a standup update if the user has provided sufficient information or handle the unclear response based on the context.
2. Always pass the fetched update to making edits.
3. Respond clearly and concisely to guide users.

Use a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input).

Valid "action" values: "Final Answer" or {tool_names}

Provide only ONE action per $JSON_BLOB, as shown:
{{
    "action": $TOOL_NAME,
    "action_input": $INPUT
}}

Reminder to ALWAYS respond with a valid json blob of a single action. Use tools if necessary. Respond directly if appropriate
"""

human = '''{input}

{agent_scratchpad}

(reminder to respond in a JSON blob no matter what)'''

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", human)
    ]
)

agent_for_execution = create_structured_chat_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent_for_execution, tools=tools)

# agent_executor.invoke({"input": "hi"})

# Using with chat history
# agent_executor.invoke(
#     {
#         "input": "what's my name?",
#         "chat_history": [
#             HumanMessage(content="hi! my name is bob"),
#             AIMessage(content="Hello Bob! How can I assist you today?"),
#         ],
#     }
# )

# agent = llm.bind_tools(tools)

# Fetch external data dynamically
def fetch_standup_update(slack_user_id: str):
    """
    Query MongoDB to get the user's existing standup update for the given day.
    """
    day = datetime.now().strftime("%Y-%m-%d")
    
    return get_standup_updates_by_user_id(slack_user_id, date=day) if update_exists(slack_user_id, date=day) else None

def execute_agent_with_context(agent_executor, slack_user_id, user_input):
    """
    Dynamically executes the agent with context from external data.
    """
    # Fetch external data
    update = fetch_standup_update(slack_user_id)

    print("Standup update exists:", update)

    # Prepare the tool input
    if update:
        tool_input = {"update": update, "text": user_input}
        tool_name = "make_edits_to_update"
    else:
        tool_input = {"text": user_input}
        tool_name = "create_standup_update"

    response = agent_executor.invoke(tool_name, tool_input)
    return response