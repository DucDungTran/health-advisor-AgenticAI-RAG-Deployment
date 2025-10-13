from pathlib import Path
import os
from dotenv import load_dotenv
import chromadb
from agents import Agent, WebSearchTool, function_tool
from agents.mcp import MCPServerStreamableHttp

# Load environment variables
load_dotenv()

# --- ChromaDB setup --------------------------------------------------------
CHROMA_DIR = Path(__file__).resolve().parent / "chroma"
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

collections = chroma_client.list_collections()
if not collections:
    raise RuntimeError(f"No Chroma collections found in {CHROMA_DIR}")

database = chroma_client.get_collection(name=collections[0].name)

# --- Tools -----------------------------------------------------------------
@function_tool
def get_calorie_info(query: str, top_k: int = 3) -> str:
    """
    Retrieve relevant calorie information from the RAG database for a given query.

    Args:
        query (str): The food item to search for.
        top_k (int): The maximum number of top relevant documents to retrieve.

    Returns:
        str: A formatted string containing the retrieved calorie information.
    """

    output = database.query(query_texts=[query], n_results=top_k)

    docs = output.get("documents", [[]])[0] if output else []
    metas = output.get("metadatas", [[]])[0] if output else []

    if not docs:
        return f"No relevant nutrition information found for: {query}."

    lines = []
    for m in metas:
        # Use .get to avoid KeyError if any field is missing
        food_item = m.get("food_item", "Unknown item")
        calories = m.get("calories_per_100g", "N/A")
        category = m.get("food_category", "Unknown category")
        lines.append(f"{food_item} ({category}): {calories} calories per 100g")

    return "Nutrition information:\n" + "\n".join(lines)

# --- MCP (Exa Search) ------------------------------------------------------
EXA_API_KEY = os.getenv("EXA_API_KEY")
if not EXA_API_KEY:
    print("Warning: EXA_API_KEY is not set. Exa MCP server will fail to authenticate.")

exa_mcp = MCPServerStreamableHttp(
    name="Exa Search",
    params={
        # Most Exa MCP deployments expect the api key as 'api_key' query param
        "url": f"https://mcp.exa.ai/mcp?api_key={EXA_API_KEY}" if EXA_API_KEY else "https://mcp.exa.ai/mcp",
        "timeout": 30,
    },
    client_session_timeout_seconds=30,
    cache_tools_list=True,
    max_retry_attempts=1,
)

async def init_mcp():
    await exa_mcp.connect()
    print("Connected to Exa MCP.")

# --- Agents ----------------------------------------------------------------
calorie_agent = Agent(
    name="Nutrition Assistant",
    instructions="""
    * You are a helpful nutrition assistant that provides concise and accurate calorie information.
    * You follow this workflow strictly:
        1) Use the get_calorie_info to find calorie data for the requested food. Only use the result if it exactly matches the query.
        2) If no exact match or ingredient details are needed, use Exa Search to find the precise recipe and ingredient list.
           Even if the search provides calorie data, always re-fetch ingredient calories using the get_calorie_info for consistency.
        3) After identifying the full ingredient list, use the get_calorie_info to get calorie information for each ingredient.
        4) For meal-related queries, output a list of ingredients with quantities and calories per single serving, and include the total calories.
        5) Don't use the get_calorie_info more than 10 times.
        6) Always be concise and factual in your answers.
    """,
    tools=[get_calorie_info],
    mcp_servers=[exa_mcp],
)

planner_agent = Agent(
    name="Meal Planner Assistant",
    instructions="""
    * You are a helpful assistant that suggests healthy breakfast options.
    * You provide concise answers tailored to the user's preferences.
    * Based on the user's input, suggest several healthy breakfast meals that are suitable for a busy person.
    * For each meal, explicitly mention its name and include one sentence explaining why it's a healthy choice.
    """,
)

calorie_calculator = calorie_agent.as_tool(
    tool_name="calorie_calculator",
    tool_description="Use this tool to calculate the calories of a meal and its ingredients",
)

meal_planner = planner_agent.as_tool(
    tool_name="meal_planner",
    tool_description="Use this tool to generate personalized healthy breakfast options based on dietary preferences and requirements.",
)

price_checker_agent = Agent(
    name="Price Checker Assistant",
    instructions="""
    * You are a helpful assistant that analyzes multiple breakfast meals. Each meal includes its ingredients and calorie values.
    * Your task is to find the approximate price of each ingredient and summarize the results clearly following this workflow:

    1) Use the web search tool to find approximate prices for each ingredient.
    2) In your final output, include the meal name and a list of ingredients with their calories and estimated prices.
    3) Format your response in concise Markdown for easy readability.
    """,
    tools=[WebSearchTool()],
)

meal_advisor = Agent(
    name="Meal Advisor",
    instructions="""
    * You are a Meal Advisor who creates personalized, healthy breakfast meal plans based on user preferences.
    * For each meal, you must include the meal name, a list of ingredients, and the calorie count for both the meal and its ingredients.

    Follow this workflow carefully:
    1) Use the meal_planner tool to generate several healthy breakfast options tailored to the user's preferences.
    2) Use the calorie_calculator tool to determine the calorie content of each meal and its ingredients.
    3) Once the meal plans and calorie data are ready, handoff this information to the Price Checker Assistant to include the corresponding prices.
    4) Ensure your final output is concise, factual, and formatted in Markdown for easy readability.

    """,
    tools=[meal_planner, calorie_calculator],
    handoff_description="""
    Create a concise breakfast recommendation based on the user's preferences. Use Markdown format.
    """,
    handoffs=[price_checker_agent],
)