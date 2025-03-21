from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.messages import HumanMessage
from .reply_agent import reply_agent

workflow = StateGraph(state_schema=MessagesState)



# Define the function that calls the model
def call_model(state: MessagesState):
    response = reply_agent.invoke(state["messages"])
    # Update message history with response:
    return {"messages": response}


# Define the (single) node in the graph
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

# Add memory
memory = MemorySaver()
workflow = workflow.compile(checkpointer=memory)