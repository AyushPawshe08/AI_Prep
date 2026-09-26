import os
from typing import TypedDict, Dict, Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END, START

load_dotenv()

# Define state schema
class PipelineState(TypedDict):
    topic: str
    learning_objectives: str
    explanation: str
    analogy: str
    technical_explanation: str
    code_example: str
    quiz: str
    answers: str
    revision_notes: str

# Initialize Groq LLM
llm = ChatGroq(
    model_name="openai/gpt-oss-120b",
    temperature=0.3
)

# Nodes
def generate_objectives(state: PipelineState) -> Dict[str, Any]:
    prompt = f"Generate clear, concise learning objectives for the topic: {state['topic']}"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"learning_objectives": res.content}

def generate_explanations(state: PipelineState) -> Dict[str, Any]:
    topic = state['topic']
    objectives = state['learning_objectives']
    
    exp_res = llm.invoke([HumanMessage(content=f"Topic: {topic}\nObjectives: {objectives}\n\nProvide a high-level explanation of the topic.")])
    analogy_res = llm.invoke([HumanMessage(content=f"Topic: {topic}\n\nProvide a clear real-world analogy to help understand this topic.")])
    tech_res = llm.invoke([HumanMessage(content=f"Topic: {topic}\n\nProvide a detailed technical explanation of how this works under the hood.")])
    code_res = llm.invoke([HumanMessage(content=f"Topic: {topic}\n\nProvide a clean, well-commented code example illustrating this topic.")])

    return {
        "explanation": exp_res.content,
        "analogy": analogy_res.content,
        "technical_explanation": tech_res.content,
        "code_example": code_res.content
    }

def generate_quiz(state: PipelineState) -> Dict[str, Any]:
    prompt = f"Topic: {state['topic']}\n\nBased on these learning objectives:\n{state['learning_objectives']}\n\nCreate a 3-5 question quiz to test comprehension."
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"quiz": res.content}

def generate_answers(state: PipelineState) -> Dict[str, Any]:
    prompt = f"Provide detailed answers and explanations for the following quiz questions:\n\n{state['quiz']}"
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"answers": res.content}

def generate_revision_notes(state: PipelineState) -> Dict[str, Any]:
    prompt = f"Topic: {state['topic']}\n\nSummarize the key takeaways, bullet points, and quick revision notes for this topic."
    res = llm.invoke([HumanMessage(content=prompt)])
    return {"revision_notes": res.content}

# Create graph
graph = StateGraph(PipelineState)

# Add nodes (using 'explanations' to match the edges)
graph.add_node("objectives", generate_objectives)
graph.add_node("explanations", generate_explanations)
graph.add_node("quiz", generate_quiz)
graph.add_node("answers", generate_answers)
graph.add_node("revision_notes", generate_revision_notes)

# Add edges
graph.add_edge(START, "objectives")
graph.add_edge("objectives", "explanations")
graph.add_edge("explanations", "quiz")
graph.add_edge("quiz", "answers")
graph.add_edge("answers", "revision_notes")
graph.add_edge("revision_notes", END)

# Compile the workflow graph
workflow_app = graph.compile()